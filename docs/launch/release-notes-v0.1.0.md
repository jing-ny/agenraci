# AgenRACI v0.1.0

*A machine-checkable accountability charter for teams of humans **and** AI agents.*

When an AI agent on your team ships code, sends a message, or spends money — and no
human pressed the button — who is accountable? AgenRACI is one human-readable file (a
**charter**) that answers that for each *type* of action, plus a checker that flags the
structural gaps before they bite.

This is the first public release. It **writes and checks** a charter.

## What's in 0.1.0

**The charter format.** One YAML file declares a small set of roles, appoints humans
and agents to them, and for each action type names the single accountable owner, who's
consulted/informed, the permissions it touches, the required approval gate, the timeout
behavior, and any break-glass path.

**The checker — rules R1–R6, all active:**
- **R1 single accountable** — exactly one accountable role per action.
- **R2 coverage** — declared permissions and the actions that use them line up (no dead grants, no undeclared use).
- **R3 no contradiction** — a role can't both grant and deny the same capability.
- **R4 gate completeness** — every approval gate has a defined timeout/break-glass path; no silent deadlock.
- **R5 low-risk gating** — "proceed on timeout" is only allowed when the action is explicitly marked low-risk.
- **R6 acyclic authority** — gate `escalate_to` edges form no cycle, so a decision can't escalate forever.

**The CLI (`agenraci`):**
- `agenraci init [path]` — write a commented starter charter.
- `agenraci validate <charter.yaml> …` — parse + check, with a per-rule report; takes many paths; exits non-zero on failure (gate it in CI).
- `agenraci validate --explain` — print a plain-language fix for each failing rule.
- `agenraci --version`.

**Ship it in your repo:**
- A **GitHub Action** (`action.yml`) and a **pre-commit hook** (`.pre-commit-hooks.yaml`) to fail CI when the charter is internally inconsistent.
- A **browser playground** (`docs/playground/`, runs the real checker via Pyodide — no install).

**Worked examples** — `examples/sprout/` (mixed human + agent), `examples/relay/`
(all-agent, 0 humans), `examples/autopilot/` (autonomous coding team), plus a blank
template. AgenRACI even governs its own development with a charter in `governance/`.

## Honest scope — what 0.1.0 does *not* do

AgenRACI **writes and checks** a charter. It does **not** intercept tool calls, enforce
approvals at runtime, or pause workflows. Tools like LangGraph and CrewAI run agents,
and HumanLayer adds human approval steps; AgenRACI sits one level up — the
framework-agnostic file that declares *who's allowed to do what, and who breaks a tie*.
The runtime adapters (`agenraci/adapters/`) are honest stubs in v0.1.

## Roadmap (not a current claim)

- Compile a charter into live approval gates, starting with a **HumanLayer connector**.
- A team-wide authority graph that detects impossible loops, circular escalation, and conflicting override rules beyond single-gate edges.

## Install

```bash
pip install agenraci
agenraci init charter.yaml
agenraci validate charter.yaml
```

MIT-licensed. Issues, examples, and the four seeded good-first-issues (#30–#33) welcome.
