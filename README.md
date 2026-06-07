# nextRACI — who's allowed to do what, and who's accountable, on a team of humans and AI agents

[![CI](https://github.com/jing-ny/nextraci/actions/workflows/ci.yml/badge.svg)](https://github.com/jing-ny/nextraci/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/nextraci.svg)](https://pypi.org/project/nextraci/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> When an AI agent does something on your team — ships code, sends a message,
> spends money — and no human pressed the button, **who is accountable?**
> nextRACI is one plain-language file that answers that up front, for every kind
> of action: who may do it, who signs off, and who owns the outcome.

For decades, teams have used **RACI** — a simple chart of who is *Responsible,
Accountable, Consulted, and Informed* for each kind of work. RACI quietly assumes
a person starts every task. AI agents break that assumption: they can act on
their own, but someone human must still answer for what they do.

**nextRACI brings RACI into the age of AI agents.** You write one file — a
*charter* — that lists, for each type of action on your team:

- who **does** it (Responsible),
- who is **accountable** (exactly one person or role),
- who must be **consulted** or kept **informed**,
- who has to **approve** it first, and
- what happens if the one who should act is **unavailable**.

A built-in checker reads the charter and flags the gaps before they bite: an
action with no one accountable, two people who both think they're in charge, or
an approval step that could quietly stall forever.

```bash
pip install nextraci
nextraci init                    # writes a commented charter.yaml to edit
nextraci validate charter.yaml   # check it holds together
```

Cloned the repo instead? Validate a bundled example directly:
`nextraci validate examples/sprout/charter.yaml`.

New here? Start with the essay: [**Why nextRACI**](docs/why-nextraci.md) — the
accountability gap, why classic RACI breaks under agentic AI, and how this fits
ISO/IEC 42001 and the EU AI Act.

## See it catch a gap

A charter where two roles both think they're accountable for shipping code — the
checker catches it (rule **R1**), and the one-line fix passes:

<!-- demo-gif: after `vhs docs/demo/demo.tape`, embed ![demo](docs/demo/demo.gif) here -->

```text
$ nextraci validate docs/demo/charter-broken.yaml
✗ R1 single accountable
    - A2_ship_code: has 2 accountable roles (builder, reviewer) — exactly one is required.
FAIL — 1 issue(s) found.

$ nextraci validate docs/demo/charter-fixed.yaml
✓ R1 single accountable
PASS — charter is a valid operating constitution.
```

Full walkthrough + a recordable GIF script: [`docs/demo/`](docs/demo/).

## What nextRACI is (and isn't) yet

**Today, nextRACI helps you write the charter and checks that it holds together.**
You get:

- a clear format for the charter file,
- an automatic checker that catches gaps, conflicts, and approval steps that could
  deadlock,
- a worked example and a blank template to start from.

**nextRACI does not run your team — yet.** It doesn't (today) intercept actions or
enforce approvals at the moment they happen. Tools like LangGraph, CrewAI, and
HumanLayer already handle *running* agents and pausing them for sign-off. nextRACI
sits one level up and answers what they don't: *on this specific team, who is
allowed to do what, and who breaks a tie.* Turning the charter into live, enforced
approvals is the next milestone on the roadmap — not a claim about today.

## The gap we fill

Today, RACI is mostly applied at the *governance* level — the boardroom and
compliance question of "who answers for the AI system as a whole" (the concern
behind standards like ISO/IEC 42001 and the EU AI Act). What's missing is the
*operating* level: a precise, machine-checkable charter for the day-to-day, where
the AI agents themselves hold real roles and the rules can be verified by a tool
instead of living in a slide deck. That everyday accountability — for the exact
moment an agent acts on its own — is what nextRACI covers.

## The core model (three independent questions)

Most "who does what" confusion comes from mixing up three different questions.
nextRACI keeps them separate:

| Question        | What it asks                      | Example |
|-----------------|-----------------------------------|---------|
| **Function**    | What do you *do*?                 | Orchestrate, Build, Advise, Investigate, Review, Watch |
| **Permission**  | What may you *touch*?             | `edit_code`, `merge`, `deploy`, `spend`, … granted **or explicitly denied** |
| **Authority**   | Whose call *wins* in a conflict?  | Each action's `accountable`, plus gate `escalate_to` for timeouts |

The proof they're separate: a **domain expert can be _accountable_ for a fact,
_denied_ the right to touch code, yet able to _block_ a merge on correctness
grounds** — all at once, none implying the others.

### Roles are defined once; members are assigned

You don't rewrite the rules for every agent. Define a small **set of roles**
(orchestrator, engineer, domain expert, researcher, reviewer, monitor) once, then
*assign* humans and agents to them. Adding an agent is a one-line appointment, not
a new rulebook.

### One accountable per action — no gaps, no turf wars

List the **types of action** in your project (not individual tasks), and require
each to have exactly one accountable role. Nobody accountable = a gap; two people
accountable = a turf war. The checker catches both.

### Escape hatches so the rules never deadlock

People aren't always online — and neither are agents. So every approval step must
say what happens on timeout (`block`, `escalate to someone`, or, only for
explicitly low-risk actions, `proceed`), and must have a `break_glass` emergency
path. Any blocked-but-confident actor gets a `suggestion_route` so their input
isn't silently dropped. `proceed` on timeout is a guarded opt-in — allowed only on
an action explicitly marked low-risk — so "low risk" can never become a quiet
backdoor for an agent to act unsupervised.

## The checker (v0.1)

| Rule | Checks |
|------|--------|
| **R1** | single accountable — every action type has exactly one `accountable` |
| **R2** | coverage — no unused permissions; no action uses an undeclared permission |
| **R3** | no contradiction — no role both grants and denies the same permission |
| **R4** | gate completeness — every approval step has a timeout rule + emergency path; every blocking `deny` has a `suggestion_route` |
| **R5** | low-risk gating — `proceed` on timeout only on an action marked low-risk |
| **R6** | acyclic authority — gate `escalate_to` timeouts never form a loop, so a decision can't escalate forever without anyone able to settle it |

## CLI

```bash
nextraci init [path]                             # write a commented starter charter (default: charter.yaml)
nextraci validate <charter.yaml>                 # parse + check, with a per-rule report
nextraci compile --target humanlayer <charter>   # placeholder in v0.1
nextraci compile --target langgraph  <charter>   # placeholder in v0.1
```

## Repository layout

```
nextraci/
├── README.md            # this file
├── SPEC.md              # the three questions, RACI rules, file format, checker rules
├── nextraci/            # the Python package (schema, checker, cli, connectors,
│                        #   and the starter template `nextraci init` writes)
├── governance/             # nextRACI's own charter — the project governs itself
├── examples/hello-world/   # a minimal worked example (1 human + 1 agent)
├── examples/agent-review-gate/ # a minimal approval-flow example (1 human + 2 agents)
├── examples/sprout/        # a complete worked example (2 humans + 6 agents)
├── examples/relay/         # an all-agent worked example (5 agents, 0 humans)
└── tests/                  # one test per rule + known-good / known-bad charters
```

## Roadmap

- **v0.1 — write it and check it.** The charter format, the checker (R1–R6), the
  Sprout example, and a template. ← you are here
- **v0.2 — first live connector.** A working HumanLayer connector that turns a
  charter into real approval gates, plus a richer authority graph beyond gate
  `escalate_to` edges (standing veto relations).
- **v0.3 — LangGraph connector** + a small web view that renders the chart so
  non-engineers can read it.
- **v0.4 — `nextraci lint --explain`** that names each gap or conflict in plain
  language and suggests a fix.

## FAQ

**Isn't this just RBAC?**
No. Permission ("what may you touch") is only *one* of nextRACI's three axes.
Role-based access control answers that one question and stops there. nextRACI also
separates **Function** (what you do) and **Authority** (whose call wins in a
conflict), and — the part RBAC has no concept of — it centers a single
**accountable** owner for each *type* of action. RBAC can tell you an agent is
allowed to call `deploy`; it can't tell you who answers for the deploy, who had to
sign off first, or what should happen if that approver goes dark. A charter can be
denied a permission yet still be accountable for the outcome — those are different
axes, and conflating them is exactly the gap nextRACI exists to close.

**Why not just use HumanLayer / LangGraph / CrewAI?**
Use them — they're solving a different layer. Those frameworks *run* agents and can
pause them to wait for a human sign-off. nextRACI sits one level up: it's the file
that says, *for this specific team*, who is allowed to do what, who owns each
outcome, and who breaks a tie — independent of which runtime you use. The charter
is framework-agnostic on purpose. Turning a charter into the live gates those tools
enforce (starting with a HumanLayer connector) is on the roadmap; today nextRACI
defines and checks the rules those runtimes would enforce.

**Is this vaporware?**
No. v0.1 *writes and checks* a charter today: a real file format, an automatic
checker with rules R1–R5, four worked examples, and a template — all of which you
can run from a clone of this repo (`pip install -e .` then
`nextraci validate examples/sprout/charter.yaml`). What it does
*not* do yet is intercept actions or enforce approvals at runtime; that's stated
plainly in [What nextRACI is (and isn't) yet](#what-nextraci-is-and-isnt-yet)
above and tracked on the roadmap, not dressed up as a current capability.

## License

MIT — see [LICENSE](LICENSE).
