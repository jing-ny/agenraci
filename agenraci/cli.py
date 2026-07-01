"""The ``agenraci`` command-line interface.

* ``agenraci init [path]`` — write a starter charter to edit.
* ``agenraci rules`` — list each checker rule (R1-R6) and what it checks.
* ``agenraci validate <charter.yaml>`` — parse + lint, with a per-rule report.
* ``agenraci schema`` — print the charter JSON Schema.
* ``agenraci compile --target {claude,github,humanlayer,langgraph}`` — compile a
  validated charter into config for a target tool (claude/github are real;
  humanlayer/langgraph are stubs).
* ``agenraci verify --target github`` — check that a branch's protection enforces
  what the charter declares (read-only; live via ``--repo OWNER/REPO`` over
  ``gh api``, or offline via a ``--settings`` export).
"""

from __future__ import annotations

import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from importlib.resources import files
from pathlib import Path

import typer
from pydantic import ValidationError

from .adapters import STUB_TARGETS, TARGETS
from .adapters.github import (
    CouldNotCheck,
    fetch_live_protection,
    parse_protection,
    sweep_org,
    verify_github,
)
from .linter import EXPLANATIONS, RULES, lint
from .loader import load_charter

app = typer.Typer(
    add_completion=False,
    help="AgenRACI — validate and compile a team's operating constitution.",
)

# ANSI colour codes, blanked when colour is disabled (NO_COLOR / non-TTY /
# --no-color). The constants below are mutable module globals: `_set_color`
# flips them on or off, and the root callback re-evaluates the decision on every
# invocation so it honours --no-color and a per-run NO_COLOR.
_ANSI = {
    "_GREEN": "\033[32m",
    "_RED": "\033[31m",
    "_DIM": "\033[2m",
    "_BOLD": "\033[1m",
    "_RESET": "\033[0m",
}
_GREEN = _RED = _DIM = _BOLD = _RESET = ""


def _color_enabled(*, no_color: bool = False) -> bool:
    """Colour is on only when not suppressed and stdout is a real terminal.

    Honours the NO_COLOR convention (https://no-color.org/): any value of the
    NO_COLOR env var disables colour. An explicit --no-color wins too, and
    piped/redirected output (a non-TTY) is left plain so escape codes don't
    leak into files or CI logs.
    """
    if no_color or "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


def _set_color(enabled: bool) -> None:
    """Point the colour constants at real escapes (on) or empty strings (off)."""
    g = globals()
    for name, code in _ANSI.items():
        g[name] = code if enabled else ""


# Resolve once from the environment at import; the root callback refines it per run.
_set_color(_color_enabled())


def _echo(msg: str = "") -> None:
    typer.echo(msg)


def _agenraci_version() -> str:
    try:
        return _pkg_version("agenraci")
    except PackageNotFoundError:  # running from a source tree, not installed
        return "0.0.0+unknown"


def _version_callback(value: bool) -> None:
    if value:
        _echo(f"agenraci {_agenraci_version()}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show the AgenRACI version and exit.",
        is_eager=True, callback=_version_callback,
    ),
    no_color: bool = typer.Option(
        False, "--no-color",
        help="Disable ANSI colour (also honours NO_COLOR and auto-disables "
             "when output is not a terminal).",
    ),
) -> None:
    """AgenRACI — validate and compile a team's operating constitution."""
    _set_color(_color_enabled(no_color=no_color))


def _template_text() -> str:
    return (files("agenraci") / "templates" / "charter.template.yaml").read_text(
        encoding="utf-8"
    )


@app.command()
def init(
    charter_path: Path = typer.Argument(
        Path("charter.yaml"),
        help="Where to write the starter charter.",
    ),
    stdout: bool = typer.Option(
        False, "--stdout",
        help="Print the starter charter to stdout instead of writing a file.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite the file if it already exists.",
    ),
) -> None:
    """Write a commented starter charter you can edit, then validate."""
    if stdout:
        _echo(_template_text())
        return

    if charter_path.exists() and not force:
        _echo(f"{_RED}✗ {charter_path} already exists.{_RESET} "
              f"Pass {_BOLD}--force{_RESET} to overwrite, or choose another path.")
        raise typer.Exit(code=1)

    charter_path.parent.mkdir(parents=True, exist_ok=True)
    charter_path.write_text(_template_text(), encoding="utf-8")
    _echo(f"{_GREEN}✓{_RESET} wrote starter charter to {_BOLD}{charter_path}{_RESET}")
    _echo(f"  Edit it, then run: {_BOLD}agenraci validate {charter_path}{_RESET}")


def _gh_error(path: Path, title: str, message: str) -> None:
    """Emit a GitHub Actions ``::error`` workflow command (a file-level annotation).

    GitHub renders these in the PR "Files changed" tab, so a failing charter
    shows up where reviewers look instead of only in the run log. Newlines would
    break the command, so collapse them.
    """
    one_line = " ".join(message.split())
    _echo(f"::error file={path},title=AgenRACI {title}::{one_line}")


def _lint_result(charter_path: Path, *, explain: bool = False) -> dict:
    """Compute the canonical machine-readable result for one charter (no output).

    Shared by the ``json`` and ``sarif`` formats so the two never drift. Shape:
    ``{charter, project, ok, error, rules}`` on a charter that loads, where each
    rule carries ``passed`` and any ``findings``; on a charter that fails to load
    it is ``{charter, project: null, ok: false, error, rules: [], findings}``.
    """
    try:
        charter = load_charter(charter_path)
    except ValidationError as exc:
        return {
            "charter": str(charter_path),
            "project": None,
            "ok": False,
            "error": "schema error",
            "rules": [],
            "findings": [
                {"loc": ".".join(str(p) for p in err["loc"]) or "<root>",
                 "message": err["msg"]}
                for err in exc.errors()
            ],
        }
    except Exception as exc:  # malformed YAML, etc.
        return {
            "charter": str(charter_path),
            "project": None,
            "ok": False,
            "error": "could not load",
            "rules": [],
            "findings": [{"loc": None, "message": str(exc)}],
        }

    errors = lint(charter)
    by_rule: dict[str, list] = {}
    for e in errors:
        by_rule.setdefault(e.rule, []).append(e)
    return {
        "charter": str(charter_path),
        "project": charter.project,
        "ok": not errors,
        "error": None,
        "rules": [
            {
                "id": rule_id,
                "title": title,
                # Reserved for future stub rules; always false while R1-R6 are
                # all active (no RULES title carries a " (stub)" marker today).
                "stub": " (stub)" in title,
                "passed": not by_rule.get(rule_id),
                "findings": [
                    {
                        "target": e.target,
                        "message": e.message,
                        **(
                            {"explanation": EXPLANATIONS[rule_id]}
                            if explain and rule_id in EXPLANATIONS
                            else {}
                        ),
                    }
                    for e in by_rule.get(rule_id, [])
                ],
            }
            for rule_id, title, _fn in RULES
        ],
    }


def _sarif_result(rule_id: str, text: str, uri: str) -> dict:
    """One SARIF result object pinned to a charter file (file-level, no line)."""
    return {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": text},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}}}
        ],
    }


def _sarif_document(results: list[dict]) -> dict:
    """Build a single SARIF 2.1.0 run from per-charter results.

    Findings are file-level: AgenRACI's checker references a *target* (an action
    or role name), not a source line, so each result points at the charter file
    rather than a line within it. GitHub code-scanning ingests this directly.
    """
    rule_descriptors = [
        {
            "id": rule_id,
            "name": title,
            "shortDescription": {"text": title},
            **({"fullDescription": {"text": EXPLANATIONS[rule_id]}}
               if rule_id in EXPLANATIONS else {}),
        }
        for rule_id, title, _fn in RULES
    ] + [
        {"id": "schema-error", "name": "charter schema error",
         "shortDescription": {"text": "The charter does not match the AgenRACI schema."}},
        {"id": "load-error", "name": "charter load error",
         "shortDescription": {"text": "The charter file could not be parsed."}},
    ]

    sarif_results: list[dict] = []
    for r in results:
        uri = r["charter"]
        if r["error"] == "schema error":
            for f in r["findings"]:
                sarif_results.append(
                    _sarif_result("schema-error", f"{f['loc']}: {f['message']}", uri))
        elif r["error"] == "could not load":
            for f in r["findings"]:
                sarif_results.append(_sarif_result("load-error", f["message"], uri))
        else:
            for rule in r["rules"]:
                for f in rule["findings"]:
                    sarif_results.append(
                        _sarif_result(rule["id"], f"{f['target']}: {f['message']}", uri))

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AgenRACI",
                        "informationUri": "https://github.com/jing-ny/agenraci",
                        "version": _agenraci_version(),
                        "rules": rule_descriptors,
                    }
                },
                "results": sarif_results,
            }
        ],
    }


def _validate_one(charter_path: Path, *, explain: bool = False, github: bool = False) -> bool:
    """Validate a single charter, print its per-rule report, return True if clean."""
    try:
        charter = load_charter(charter_path)
    except ValidationError as exc:
        _echo(f"{_RED}{_BOLD}✗ schema error{_RESET} in {charter_path}")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<root>"
            _echo(f"  {_RED}-{_RESET} {loc}: {err['msg']}")
            if github:
                _gh_error(charter_path, "schema error", f"{loc}: {err['msg']}")
        return False
    except Exception as exc:  # malformed YAML, etc.
        _echo(f"{_RED}{_BOLD}✗ could not load{_RESET} {charter_path}: {exc}")
        if github:
            _gh_error(charter_path, "could not load", str(exc))
        return False

    errors = lint(charter)
    by_rule: dict[str, list] = {}
    for e in errors:
        by_rule.setdefault(e.rule, []).append(e)

    _echo(f"{_BOLD}AgenRACI charter:{_RESET} {charter.project}  "
          f"{_DIM}({charter_path}){_RESET}")
    _echo(f"{_DIM}{len(charter.roles)} roles · {len(charter.members)} members · "
          f"{len(charter.actions)} action types{_RESET}")
    _echo()

    for rule_id, title, _fn in RULES:
        rule_errors = by_rule.get(rule_id, [])
        stub = " (stub)" in title
        if rule_errors:
            _echo(f"{_RED}✗ {rule_id}{_RESET} {title}")
            for e in rule_errors:
                _echo(f"    {_RED}-{_RESET} {e.target}: {e.message}")
                if github:
                    _gh_error(charter_path, rule_id, f"{e.target}: {e.message}")
            if explain and rule_id in EXPLANATIONS:
                _echo(f"    {_DIM}↳ {EXPLANATIONS[rule_id]}{_RESET}")
        else:
            mark = f"{_DIM}-{_RESET}" if stub else f"{_GREEN}✓{_RESET}"
            _echo(f"{mark} {rule_id} {title}")

    _echo()
    if errors:
        _echo(f"{_RED}{_BOLD}FAIL{_RESET} — {len(errors)} issue(s) found.")
        return False
    _echo(f"{_GREEN}{_BOLD}PASS{_RESET} — charter is a valid operating constitution.")
    return True


@app.command()
def validate(
    charter_paths: list[Path] = typer.Argument(..., exists=True, readable=True,
                                               help="Path(s) to charter.yaml"),
    explain: bool = typer.Option(
        False, "--explain", "-e",
        help="After each failing rule, print a plain-language fix in one line.",
    ),
    output_format: str = typer.Option(
        "human", "--format",
        help="Output format: 'human' (default), 'github' (also emit ::error "
             "annotations for GitHub Actions), 'json' (one machine-readable "
             "object per charter), or 'sarif' (a single SARIF 2.1.0 document "
             "for GitHub code-scanning).",
    ),
) -> None:
    """Validate one or more charters against the schema and linter rules R1-R6.

    Accepting several paths lets a CI job or a pre-commit hook check every
    charter in a repo in one call; the command exits non-zero if any fail.
    Add --explain to turn each rule code into a plain-language fix,
    --format github to surface failures as PR annotations in GitHub Actions,
    --format json for machine-readable per-rule results, or --format sarif to
    upload findings to GitHub code-scanning.
    """
    if output_format not in ("human", "github", "json", "sarif"):
        _echo(f"{_RED}unknown --format {output_format!r}.{_RESET} "
              f"choose one of: human, github, json, sarif")
        raise typer.Exit(code=2)

    # SARIF aggregates every charter into ONE document (code-scanning uploads a
    # single file), so it is handled apart from the per-charter loop below.
    if output_format == "sarif":
        results = [_lint_result(p) for p in charter_paths]
        _echo(json.dumps(_sarif_document(results), indent=2))
        if not all(r["ok"] for r in results):
            raise typer.Exit(code=1)
        return

    github = output_format == "github"
    json_out = output_format == "json"

    ok = True
    for i, charter_path in enumerate(charter_paths):
        if json_out:
            result = _lint_result(charter_path, explain=explain)
            _echo(json.dumps(result))  # one object per line -> JSON Lines
            ok = result["ok"] and ok
            continue
        if i:
            _echo(f"{_DIM}{'─' * 60}{_RESET}")
        ok = _validate_one(charter_path, explain=explain, github=github) and ok

    if not ok:
        raise typer.Exit(code=1)


def _split_compiled_files(text: str) -> list[tuple[str, str]]:
    """Split a multi-file compile output on ``--- FILE: <path> ---`` markers."""
    files: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("--- FILE: ") and line.endswith(" ---"):
            files.append((line[len("--- FILE: "):-len(" ---")].strip(), []))
        elif files:
            files[-1][1].append(line)
    return [(path, "\n".join(body).strip() + "\n") for path, body in files]


@app.command()
def compile(  # noqa: A001 - this is the user-facing verb
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option(..., "--target", "-t",
                               help="claude | github | humanlayer | langgraph"),
    out_dir: Path = typer.Option(
        None, "--out-dir", "-o",
        help="For multi-file targets (claude): write the emitted files under "
             "this directory instead of printing them.",
    ),
) -> None:
    """Compile a validated charter into config for a target tool.

    `claude` is real — it emits .claude/agents/ definitions (+ a CLAUDE.md
    governance snippet) so Claude Code agents carry the charter's role
    boundaries. `github` is real — CODEOWNERS + branch-protection guidance from
    the charter's gates. `humanlayer` and `langgraph` are stubs. Either way
    AgenRACI emits config a human reviews and applies; it never enforces at
    runtime.
    """
    if target not in TARGETS:
        _echo(f"{_RED}unknown target {target!r}.{_RESET} "
              f"choose one of: {', '.join(sorted(TARGETS))}")
        raise typer.Exit(code=2)

    try:
        charter = load_charter(charter_path)
    except Exception as exc:  # noqa: BLE001 - schema error, malformed YAML, etc.
        _echo(f"{_RED}✗ could not load {charter_path}:{_RESET} {exc}")
        raise typer.Exit(code=1)

    # Validate before compiling: never emit config from a broken constitution.
    errors = lint(charter)
    if errors:
        _echo(f"{_RED}✗ refusing to compile:{_RESET} charter fails "
              f"{len(errors)} linter rule(s). Run `agenraci validate` first.")
        raise typer.Exit(code=1)

    if target in STUB_TARGETS:
        _echo(f"{_DIM}# agenraci compile --target {target} (STUB){_RESET}")
    output = TARGETS[target](charter)

    if out_dir is None:
        _echo(output)
        return

    files = _split_compiled_files(output)
    if not files:
        _echo(f"{_RED}✗ target {target!r} emits a single document{_RESET} — "
              f"drop --out-dir and redirect stdout instead.")
        raise typer.Exit(code=2)
    for rel, content in files:
        rel_path = Path(rel)
        # Refuse path escapes: everything must land under --out-dir.
        if rel_path.is_absolute() or ".." in rel_path.parts:
            _echo(f"{_RED}✗ refusing to write outside --out-dir:{_RESET} {rel}")
            raise typer.Exit(code=1)
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        _echo(f"{_GREEN}✓{_RESET} wrote {dest}")


def _verify_org(charter, charter_path: Path, org: str, branch: str,
                output_format: str, *, limit: int = 1000) -> None:
    """Sweep every repo in an org against the charter and render the result."""
    try:
        sweep = sweep_org(charter, org, branch=branch, limit=limit)
    except CouldNotCheck as exc:
        _echo(f"{_RED}✗ could not sweep org {org}:{_RESET} {exc}")
        raise typer.Exit(code=2)

    drifted = [r for r in sweep.results if r.status == "drift"]
    unreadable = [r for r in sweep.results if r.status == "could-not-check"]

    if output_format == "json":
        _echo(json.dumps({
            "charter": str(charter_path),
            "project": charter.project,
            "target": "github",
            "org": sweep.org,
            "branch": sweep.branch,
            "ok": sweep.ok,
            "truncated": sweep.truncated,
            "repos": [
                {
                    "repo": r.repo,
                    "status": r.status,
                    "error": r.error,
                    "note": r.report.note if r.report else None,
                    "findings": [
                        {"target": f.target, "kind": f.kind, "message": f.message}
                        for f in (r.report.findings if r.report else [])
                    ],
                    "unenforceable": [
                        {"target": f.target, "kind": f.kind, "message": f.message}
                        for f in (r.report.unenforceable if r.report else [])
                    ],
                }
                for r in sweep.results
            ],
        }))
        if not sweep.ok:
            raise typer.Exit(code=1)
        return

    # human
    _echo(f"{_BOLD}AgenRACI verify (github):{_RESET} {charter.project}  "
          f"{_DIM}(org {sweep.org}, branch {sweep.branch}, "
          f"{len(sweep.results)} repos){_RESET}")
    if not sweep.results:
        _echo(f"{_DIM}0 repos found for org {sweep.org} — nothing to verify.{_RESET}")
        return
    if sweep.truncated:
        _echo(f"{_RED}warning: the org has more repos than the listing limit; "
              f"this audit is INCOMPLETE.{_RESET}")
    for r in sweep.results:
        if r.status == "clean":
            extra = (f" {_DIM}({len(r.report.unenforceable)} unenforceable){_RESET}"
                     if r.report and r.report.unenforceable else "")
            _echo(f"  {_GREEN}✓{_RESET} {r.repo}{extra}")
        elif r.status == "drift":
            n = len(r.report.findings) if r.report else 0
            _echo(f"  {_RED}✗ {r.repo}{_RESET} — {n} drift")
        else:  # could-not-check
            _echo(f"  {_DIM}? {r.repo} — could not check: {r.error}{_RESET}")
    _echo()
    tail = f"; {len(unreadable)} could not be checked" if unreadable else ""
    if drifted:
        _echo(f"{_RED}{_BOLD}DRIFT{_RESET} — {len(drifted)} of {len(sweep.results)} "
              f"repo(s) drift from the charter{tail}.")
        raise typer.Exit(code=1)
    _echo(f"{_GREEN}{_BOLD}OK{_RESET} — all {len(sweep.results)} repo(s) enforce "
          f"the charter{tail}.")


@app.command()
def verify(
    charter_path: Path = typer.Argument(..., exists=True, readable=True,
                                        help="Path to charter.yaml"),
    target: str = typer.Option("github", "--target", "-t",
                               help="Enforcement target to verify against (github)."),
    settings: Path = typer.Option(
        None, "--settings", "-s", exists=True, readable=True,
        help="Offline mode: a branch-protection export (JSON) to verify against.",
    ),
    repo: str = typer.Option(
        None, "--repo",
        help="Live mode: OWNER/REPO to read protection from via `gh api`.",
    ),
    org: str = typer.Option(
        None, "--org",
        help="Sweep mode: verify every repo in a GitHub org (or user account) "
             "against the charter.",
    ),
    branch: str = typer.Option("main", "--branch",
                               help="The protected branch the charter governs."),
    limit: int = typer.Option(
        None, "--limit",
        help="With --org: cap how many repos to list (default 1000). Raise it "
             "to audit an org with >1000 repos, or lower it to sample.",
    ),
    output_format: str = typer.Option(
        "human", "--format",
        help="Output format: 'human' (default) or 'json'.",
    ),
) -> None:
    """Check that a live repo actually enforces what the charter declares.

    Read-only: AgenRACI compares the charter against a branch's protection
    settings and reports drift. It never changes the repo. The charter is a
    *floor* — a repo whose settings are stricter passes. Pass `--repo OWNER/REPO`
    to read one repo live via `gh api`, `--org ORG` to sweep every repo in an
    org, or `--settings export.json` to verify offline. Exit codes: 0 clean,
    1 drift, 2 could-not-check (bad input/repo/auth).
    """
    if target != "github":
        _echo(f"{_RED}unknown --target {target!r}.{_RESET} "
              f"verify currently supports: github")
        raise typer.Exit(code=2)
    if output_format not in ("human", "json"):
        _echo(f"{_RED}unknown --format {output_format!r}.{_RESET} "
              f"choose one of: human, json")
        raise typer.Exit(code=2)
    if sum(x is not None for x in (settings, repo, org)) != 1:
        _echo(f"{_RED}✗ pass exactly one of --settings (offline), --repo (one "
              f"live repo), or --org (sweep an org){_RESET}.")
        raise typer.Exit(code=2)
    if limit is not None and org is None:
        _echo(f"{_RED}✗ --limit only applies to --org (sweep mode){_RESET}.")
        raise typer.Exit(code=2)

    try:
        charter = load_charter(charter_path)
    except Exception as exc:  # noqa: BLE001 - schema error, malformed YAML, etc.
        _echo(f"{_RED}✗ could not load {charter_path}:{_RESET} {exc}")
        raise typer.Exit(code=2)  # could-not-check, distinct from drift

    if org is not None:
        _verify_org(charter, charter_path, org, branch, output_format,
                    limit=1000 if limit is None else limit)
        return

    if repo is not None:
        if "/" not in repo:
            _echo(f"{_RED}✗ --repo expects OWNER/REPO{_RESET}, got {repo!r}.")
            raise typer.Exit(code=2)
        try:
            protection = fetch_live_protection(repo, branch)
        except CouldNotCheck as exc:
            _echo(f"{_RED}✗ could not check {repo}@{branch}:{_RESET} {exc}")
            raise typer.Exit(code=2)
    else:
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - malformed JSON, etc.
            _echo(f"{_RED}✗ could not read settings {settings}:{_RESET} {exc}")
            raise typer.Exit(code=2)
        # Surface a silent mismatch: the export may declare a different branch
        # than the one we're verifying. Warn, don't fail — the user picked it.
        exported = data.get("branch")
        if exported is not None and str(exported) != branch:
            _echo(f"{_DIM}note: settings export is for branch {exported!r}, "
                  f"but verifying against {branch!r}.{_RESET}")
        protection = parse_protection(data, branch=branch)

    report = verify_github(charter, protection, branch=branch)

    if output_format == "json":
        _echo(json.dumps({
            "charter": str(charter_path),
            "project": report.project,
            "target": "github",
            "branch": report.branch,
            "ok": report.ok,
            "note": report.note,
            "findings": [
                {"target": f.target, "kind": f.kind, "message": f.message}
                for f in report.findings
            ],
            "unenforceable": [
                {"target": f.target, "kind": f.kind, "message": f.message}
                for f in report.unenforceable
            ],
        }))
        if not report.ok:
            raise typer.Exit(code=1)
        return

    # human
    source = f"repo {repo}" if repo is not None else f"settings {settings}"
    _echo(f"{_BOLD}AgenRACI verify (github):{_RESET} {report.project}  "
          f"{_DIM}(branch {report.branch}, {source}){_RESET}")
    if report.note:
        _echo(f"{_DIM}{report.note}{_RESET}")
    for f in report.findings:
        _echo(f"  {_RED}✗ drift{_RESET} {f.target}: {f.message}")
    for f in report.unenforceable:
        _echo(f"  {_DIM}- unenforceable{_RESET} {f.target}: {f.message}")
    _echo()
    if report.findings:
        _echo(f"{_RED}{_BOLD}DRIFT{_RESET} — {len(report.findings)} mismatch(es) "
              f"between the charter and the live branch protection.")
        raise typer.Exit(code=1)
    _echo(f"{_GREEN}{_BOLD}OK{_RESET} — the branch enforces what the charter declares"
          + (f" ({len(report.unenforceable)} action(s) unenforceable, see above)"
             if report.unenforceable else "") + ".")


@app.command()
def schema() -> None:
    """Print the charter JSON Schema (for editor autocomplete / external tools).

    The schema is generated from the same pydantic models the checker uses, so
    it never drifts from what `agenraci validate` accepts. Editors with the YAML
    language server pick it up automatically from the `# yaml-language-server:
    $schema=` line that `agenraci init` writes at the top of a new charter.
    """
    import json

    from .schema import Charter

    _echo(json.dumps(Charter.model_json_schema(), indent=2))


@app.command()
def rules() -> None:
    """List each checker rule (R1-R6) and what it checks, in order.

    Makes the checker self-documenting: when someone hits a rule code in a
    `validate` report and wants its plain-language meaning, `agenraci rules`
    prints every rule's id, short title, and one-line gloss without needing a
    charter to run against. Reads the same RULES/EXPLANATIONS the checker uses,
    so it never drifts from what the rules actually do.
    """
    for rule_id, title, _fn in RULES:
        _echo(f"{_BOLD}{rule_id}{_RESET}  {title}")
        gloss = EXPLANATIONS.get(rule_id)
        if gloss:
            _echo(f"    {_DIM}{gloss}{_RESET}")
        _echo()


def main() -> None:  # console-script entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
