# Contributing to AgenRACI

Thanks for your interest! AgenRACI is small and opinionated by design. The fastest
way to be useful is to keep the role library and capability list **minimal** —
flag anything you think is missing rather than inventing extra roles.

## Current contribution priorities

Start with the [active plan and issues](PLAN.md#contributor-work-items). We are focusing
on trustworthy GitHub approval verification. Each issue gives scope, dependencies,
acceptance criteria, and code entry points. The auto-merge correction is a smaller
independent task; approval semantics and bypass analysis require deeper GitHub knowledge.
Comment with your intended approach before substantial work to avoid duplication.

Regression fixtures and reviews are welcome. Unknown or unsupported guarantees must
remain visible. Broad feature work and runtime connectors are deferred this round.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
agenraci validate examples/sprout/charter.yaml
```

The Sprout charter must **PASS R1–R6** at all times — it's the
canonical known-good fixture and is checked by the test suite.

## Project shape

- `agenraci/schema.py` — pydantic v2 models (`Charter`, `Role`, `Member`,
  `CapabilitySet`, `Action`, `Gate`, `BreakGlass`, `SuggestionRoute`).
- `agenraci/linter.py` — one pure function per rule, registered in `RULES`.
- `agenraci/cli.py` — `validate`, `compile`, and `verify` commands and reporting.
- `agenraci/adapters/` — working GitHub and Claude Code adapters; HumanLayer/LangGraph placeholders.
- `tests/test_linter.py` — for each active rule, one passing case (Sprout) and
  one deliberately broken charter that trips exactly that rule.

## Adding or changing a linter rule

1. Add/modify the pure function in `agenraci/linter.py` and register it in `RULES`.
2. Make every `LintError` name the offending `action`/`role` and explain the fix.
3. Add a known-bad charter to `tests/test_linter.py` that trips **only** your
   rule, plus assert the Sprout charter still passes.
4. Update `SPEC.md` (§7) and the rules table in `README.md`.

## Style

- Python 3.11+, type-hinted, no clever metaprogramming.
- Keep `schema.py` free of I/O; loading lives in `agenraci/loader.py`.
- Match the surrounding comment density and naming.

## Commit / PR

- Keep PRs focused. One rule or one feature per PR where possible.
- Make sure `pytest` and `agenraci validate examples/sprout/charter.yaml` pass.

By contributing you agree your contributions are licensed under the MIT License.
