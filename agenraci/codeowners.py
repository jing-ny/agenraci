"""CODEOWNERS rules as path languages (#79).

GitHub picks the owners of a file from the **last** CODEOWNERS rule that matches
it, and accepts an approval from any one owner listed on that rule. To judge an
action honestly, verify has to know which rule wins for every file the action
covers, including files a pull request could add. This module turns each
pattern into a small automaton over path strings, so verify can ask exact
questions such as "is there any path that matches the action's pattern, matches
rule 3, and matches no later rule?" and get back an example path when the answer
is yes.

Pattern semantics follow GitHub's CODEOWNERS documentation (gitignore syntax,
without ``!`` negation, ``[ ]`` ranges or ``\\`` escapes, which are rejected as
unsupported):

* a pattern with a ``/`` at the start or in the middle is anchored to the repo
  root; otherwise it matches at any depth;
* a trailing ``/`` means "everything inside this directory";
* ``*`` matches within one path segment, ``?`` one character in a segment;
* ``**`` as a whole segment matches any number of directories (leading
  ``**/``, middle ``/**/``) or everything inside (trailing ``/**``);
* a pattern whose last segment is a plain name also matches everything inside
  a directory of that name (``/apps/github`` covers ``apps/github/x``); a last
  segment with a wildcard matches only at that level (GitHub documents that
  ``docs/*`` does not match ``docs/build-app/troubleshooting.md``).

Matching is case-sensitive, as GitHub's is.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

# ── Automata ────────────────────────────────────────────────────────────────
#
# A pattern compiles to a Thompson NFA whose edges carry one of three labels:
#   ("c", ch)  the literal character ch
#   ("ns",)    any one character except "/"
#   ("any",)   any one character
# Epsilon edges are kept separately. The same NFA is used both to match a real
# path and to search for an example path, so the two can never disagree.


class UnsupportedPattern(ValueError):
    """A CODEOWNERS pattern uses syntax GitHub does not support (or we can't model)."""


class TooComplex(RuntimeError):
    """The example-path search exceeded its state budget."""


@dataclass
class NFA:
    start: int
    accept: int
    edges: list[list[tuple[tuple, int]]] = field(default_factory=list)
    eps: list[list[int]] = field(default_factory=list)
    _memo: dict = field(default_factory=dict, repr=False, compare=False)

    def _new(self) -> int:
        self.edges.append([])
        self.eps.append([])
        return len(self.edges) - 1

    def closure(self, states) -> frozenset[int]:
        seen = set(states)
        stack = list(states)
        while stack:
            s = stack.pop()
            for t in self.eps[s]:
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return frozenset(seen)

    def step(self, states: frozenset[int], ch: str) -> frozenset[int]:
        key = (states, ch)
        hit = self._memo.get(key)
        if hit is None:
            hit = self._memo[key] = self._step(states, ch)
        return hit

    def _step(self, states: frozenset[int], ch: str) -> frozenset[int]:
        nxt = set()
        for s in states:
            for label, t in self.edges[s]:
                if _label_matches(label, ch):
                    nxt.add(t)
        return self.closure(nxt) if nxt else frozenset()

    def literals(self) -> set[str]:
        return {label[1] for row in self.edges for label, _ in row if label[0] == "c"}

    def matches(self, path: str) -> bool:
        cur = self.closure([self.start])
        for ch in path:
            cur = self.step(cur, ch)
            if not cur:
                return False
        return self.accept in cur


def _label_matches(label: tuple, ch: str) -> bool:
    kind = label[0]
    if kind == "c":
        return label[1] == ch
    if kind == "ns":
        return ch != "/"
    return True  # "any"


# AST nodes: ("lit", ch) | ("ns",) | ("any",) | ("star_ns",) | ("star_any",)
#            | ("seq", [nodes]) | ("opt", node)
def _build(nfa: NFA, node: tuple, start: int) -> int:
    kind = node[0]
    if kind == "lit":
        end = nfa._new()
        nfa.edges[start].append((("c", node[1]), end))
        return end
    if kind in ("ns", "any"):
        end = nfa._new()
        nfa.edges[start].append(((kind,), end))
        return end
    if kind in ("star_ns", "star_any"):
        label = ("ns",) if kind == "star_ns" else ("any",)
        loop = nfa._new()
        end = nfa._new()
        nfa.eps[start].append(loop)
        nfa.edges[loop].append((label, loop))
        nfa.eps[loop].append(end)  # a separate exit, so an enclosing "opt" can't
        return end                 # skip straight into the loop
    if kind == "seq":
        cur = start
        for child in node[1]:
            cur = _build(nfa, child, cur)
        return cur
    if kind == "opt":
        end = _build(nfa, node[1], start)
        nfa.eps[start].append(end)
        return end
    raise AssertionError(f"unknown node {kind}")


def _compile_ast(ast: tuple) -> NFA:
    nfa = NFA(start=0, accept=0)
    nfa._new()
    nfa.accept = _build(nfa, ast, 0)
    return nfa


_ANY_DIRS = ("opt", ("seq", [("star_any",), ("lit", "/")]))   # (.*/)?
_INSIDE = ("seq", [("lit", "/"), ("any",), ("star_any",)])      # /.+


def _segment(seg: str) -> list[tuple]:
    out: list[tuple] = []
    for ch in seg:
        if ch == "*":
            if not out or out[-1] != ("star_ns",):  # "a**b" behaves like "a*b"
                out.append(("star_ns",))
        elif ch == "?":
            out.append(("ns",))
        else:
            out.append(("lit", ch))
    return out


def pattern_ast(pattern: str) -> tuple:
    """Translate one CODEOWNERS-style pattern into an AST over file paths."""
    p = pattern.strip()
    if not p:
        raise UnsupportedPattern("empty pattern")
    if p.startswith("!"):
        raise UnsupportedPattern(f"{pattern!r}: negation (!) is not supported by GitHub")
    if any(c in p for c in "[]\\"):
        raise UnsupportedPattern(
            f"{pattern!r}: character ranges and escapes are not supported by GitHub")
    dir_only = p.endswith("/")
    core = p.rstrip("/")
    if not core:
        raise UnsupportedPattern(f"{pattern!r}: no path")
    anchored = core.startswith("/") or "/" in core
    core = core.lstrip("/")
    segs = core.split("/")
    if "" in segs:
        raise UnsupportedPattern(f"{pattern!r}: empty path segment")

    items: list[tuple] = []
    if segs[0] == "**":
        if len(segs) == 1:  # "**" alone: everything
            return ("seq", [("any",), ("star_any",)])
        items.append(_ANY_DIRS)
        segs = segs[1:]
    elif not anchored:
        items.append(_ANY_DIRS)

    trailing_inside = False
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        prev_was_dirs = i > 0 and segs[i - 1] == "**"
        if seg == "**":
            if last:
                items.append(_INSIDE)
                trailing_inside = True
            else:
                if i > 0 and not prev_was_dirs:
                    items.append(("lit", "/"))
                items.append(_ANY_DIRS)
            continue
        if i > 0 and not prev_was_dirs:
            items.append(("lit", "/"))
        items.extend(_segment(seg))

    if not trailing_inside:
        last_seg = segs[-1]
        if dir_only:
            items.append(_INSIDE)
        elif "*" not in last_seg and "?" not in last_seg:
            items.append(("opt", _INSIDE))
    return ("seq", items)


def compile_pattern(pattern: str) -> NFA:
    return _compile_ast(pattern_ast(pattern))


# ── CODEOWNERS file ─────────────────────────────────────────────────────────


@dataclass
class Rule:
    line: int            # 1-based line number in the file
    pattern: str
    owners: list[str]    # raw tokens, e.g. "@alice", "@org/team", "a@b.com"
    nfa: NFA | None = None
    unsupported: str | None = None  # why the pattern could not be modelled


def parse_rules(text: str) -> list[Rule]:
    """Every rule in a CODEOWNERS file, in file order.

    Blank lines and ``#`` comments are skipped; a ``#`` token ends a line. A rule
    with no owners is kept: it removes ownership from the paths it matches.
    """
    rules: list[Rule] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        tokens: list[str] = []
        for tok in raw.split():
            if tok.startswith("#"):
                break
            tokens.append(tok)
        if not tokens:
            continue
        rule = Rule(line=lineno, pattern=tokens[0], owners=tokens[1:])
        try:
            rule.nfa = compile_pattern(rule.pattern)
        except UnsupportedPattern as exc:
            rule.unsupported = str(exc)
        rules.append(rule)
    return rules


def last_match(rules: list[Rule], path: str) -> Rule | None:
    """The rule GitHub applies to ``path``: the last supported rule that matches."""
    found = None
    for rule in rules:
        if rule.nfa is not None and rule.nfa.matches(path):
            found = rule
    return found


# ── Example-path search ─────────────────────────────────────────────────────

# A tiny DFA for well-formed repo file paths: non-empty, no leading or trailing
# "/", no "//". States: 0 start, 1 inside a segment (accepting), 2 just after "/",
# -1 dead.
def _path_step(state: int, ch: str) -> int:
    if ch == "/":
        return 2 if state == 1 else -1
    return 1


def find_example(include: list[NFA], exclude: list[NFA] = (),
                 *, budget: int = 200_000) -> str | None:
    """Shortest file path accepted by every ``include`` and by no ``exclude``.

    Returns None when no such path exists. Raises TooComplex if the search would
    exceed ``budget`` states, so callers can report "could not decide" instead of
    guessing.
    """
    exclude = list(exclude)
    lits: set[str] = {"/"}
    for nfa in (*include, *exclude):
        lits |= nfa.literals()
    other = next((c for c in "xyzqjkwvb0123456789" if c not in lits), "\u00e9")
    alphabet = [other] + sorted(lits)  # try the neutral character first

    start = (
        0,
        tuple(n.closure([n.start]) for n in include),
        tuple(n.closure([n.start]) for n in exclude),
    )
    parent: dict = {start: None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        v, inc, exc = state
        if (v == 1 and all(n.accept in s for n, s in zip(include, inc))
                and not any(n.accept in s for n, s in zip(exclude, exc))):
            chars = []
            while parent[state] is not None:
                state, ch = parent[state]
                chars.append(ch)
            return "".join(reversed(chars))
        for ch in alphabet:
            nv = _path_step(v, ch)
            if nv < 0:
                continue
            ninc = tuple(n.step(s, ch) for n, s in zip(include, inc))
            if any(not s for s in ninc):
                continue
            nexc = tuple(n.step(s, ch) if s else s for n, s in zip(exclude, exc))
            nxt = (nv, ninc, nexc)
            if nxt in parent:
                continue
            if len(parent) >= budget:
                raise TooComplex("example-path search exceeded its budget")
            parent[nxt] = (state, ch)
            queue.append(nxt)
    return None
