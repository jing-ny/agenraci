# AgenRACI v0.2.1 — "audit the whole org"

A small follow-on to the v0.2.0 GitHub enforcement loop. Same honest scope:
**verify, don't intercept** — AgenRACI reads and reports on your repos' settings;
it never POSTs, PUTs, or applies anything, and it never intercepts at runtime.

## What changed

- **`agenraci verify --target github --org ORG`** — verify **every repo in a
  GitHub org** (or user account) against one charter and aggregate into a single
  report. The governance-audit case: *"does the whole org enforce our
  accountability rules?"* A repo that can't be read is isolated as
  `could-not-check` (it never aborts the sweep and is never read as drift); the
  overall exit is `1` if **any** repo drifts, `0` otherwise. To keep a clean
  verdict from being mistaken for a complete audit, the org listing is capped
  (1000) and the report is flagged `truncated` with a loud warning when the cap
  is hit. `--format json` emits one object with a per-repo breakdown.

- **Packaging: PEP 639 SPDX license metadata.** `pyproject.toml` now uses
  `license = "MIT"` + `license-files = ["LICENSE"]` (dropping the deprecated
  license table and classifier), so `python -m build` is warning-free and the
  wheel carries `License-Expression: MIT`. No runtime change.

```bash
pip install --upgrade agenraci
```

Full diff: <https://github.com/jing-ny/agenraci/compare/v0.2.0...v0.2.1>. MIT-licensed.
