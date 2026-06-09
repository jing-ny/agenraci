# Contributing to AgenRACI

Thanks for your interest! AgenRACI is small and opinionated by design. The fastest
way to be useful is to keep the role library and capability list **minimal** —
flag anything you think is missing rather than inventing extra roles.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
agenraci validate examples/sprout/charter.yaml
```

The Sprout charter must **PASS R1–R5** (R6 is a stub) at all times — it's the
canonical known-good fixture and is checked by the test suite.

## Project shape

- `agenraci/schema.py` — pydantic v2 models (`Charter`, `Role`, `Member`,
  `CapabilitySet`, `Action`, `Gate`, `BreakGlass`, `SuggestionRoute`).
- `agenraci/linter.py` — one pure function per rule, registered in `RULES`.
- `agenraci/cli.py` — `agenraci validate` / `agenraci compile`.
- `agenraci/adapters/` — stubs in v0.1.
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
