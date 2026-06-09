# AgenRACI — project instructions

AgenRACI is an open-source, machine-checkable RACI charter + linter for teams of
humans and AI agents: it declares who is Responsible / Accountable / Consulted /
Informed for each *type* of action — including when an AI agent acts with no human
trigger — and a checker flags the gaps before they bite.

## Language

**This project is English-only.** README, SPEC, CONTRIBUTING, code, comments,
commit messages, issues, and PR descriptions are all in English. (This overrides
any global default-to-Chinese reply rule for repo artifacts; conversation with the
maintainer may still be bilingual.)

## Voice & honesty

- Plain language for a broad audience — engineers *and* governance/compliance
  readers. Prefer "checker" over "linter", "format" over "schema". Gloss RACI on
  first use in standalone docs.
- **Never over-promise.** v0.1 *writes and checks* a charter. It does NOT intercept
  actions or enforce approvals at runtime. The runtime control plane and live
  connectors (HumanLayer/LangGraph) are roadmap, not current claims. Label future
  capability as roadmap. Honest scope boxes beat hype.
- Brand is **AgenRACI** (camelCase in prose; `agenraci` as the package/CLI token).

## We govern this project with its own charter

AgenRACI checks the operating constitution of human + AI-agent teams, so this repo
runs on one too: **`governance/charter.yaml`** is the constitution for developing
AgenRACI itself, and `agenraci validate governance/charter.yaml` must pass. It names
who is Responsible/Accountable/Consulted/Informed for each action type (set roadmap,
implement, QA, review, merge, docs, release) and who signs off at each gate. When a
process question comes up, the charter is the answer — not ad-hoc judgment.

## The project agents (orchestrator + four workers)

This repo defines five agents under `.claude/agents/`, mapped 1:1 to the members in
`governance/charter.yaml`:

- **orchestrator** — the entry point. Reads the charter, decides which agent does the
  work and who reviews it, sequences steps, breaks ties. Plans/routes; does not write.
- **writer** — all human-facing prose (README/SPEC/CONTRIBUTING/examples/essays,
  issue & PR text). Edits docs.
- **coder** — Python changes (schema/loader/linter/cli/adapters). Edits code.
- **reviewer** — independent, read-only review before merge/release. Reports only.
- **qa** — runs tests + CLI + packaging smoke, confirms each rule fires. Reports only.

**Start non-trivial work with the orchestrator.** It applies the charter: a code
change follows **coder → qa → reviewer**, with **writer** updating docs if behavior
changed. The charter makes the **reviewer** (not the coder) accountable for
`A5_merge_to_main`, so a change author never approves its own merge; the human
maintainer holds the break-glass authority. Keep reviewer and qa independent of the
change author.

## Checker rules (keep code ⇄ docs in sync)

R1 single accountable · R2 coverage · R3 no contradiction · R4 gate completeness ·
R5 low-risk gating · R6 acyclic authority (gate `escalate_to` edges form no cycle).
Rule behavior in `agenraci/linter.py` is the source of truth; README/SPEC must match
it. Each active rule should have a test (one test per rule is the norm).

## Dev quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
agenraci validate examples/sprout/charter.yaml
```
