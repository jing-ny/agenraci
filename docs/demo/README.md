# Demo — the checker catching a real gap

A 20-second story: a charter where two roles both think they're accountable for
shipping code, the checker catching it (rule **R1**), and the one-line fix passing.

## Files
- `charter-broken.yaml` — one deliberate mistake: `A2_ship_code` has **two**
  accountable roles.
- `charter-fixed.yaml` — the same charter with exactly one accountable.
- `demo.tape` — a [VHS](https://github.com/charmbracelet/vhs) script that records the GIF.

## Run it yourself
```bash
pip install -e .
agenraci validate docs/demo/charter-broken.yaml   # FAIL — R1
agenraci validate docs/demo/charter-fixed.yaml    # PASS
```

## What you see

```text
$ agenraci validate docs/demo/charter-broken.yaml
AgenRACI charter: demo  (docs/demo/charter-broken.yaml)
3 roles · 3 members · 2 action types

✗ R1 single accountable
    - A2_ship_code: has 2 accountable roles (builder, reviewer) — exactly one is required (conflict: two roles each think they own it).
✓ R2 coverage
✓ R3 no contradiction
✓ R4 gate completeness
✓ R5 low-risk gating
✓ R6 acyclic authority

FAIL — 1 issue(s) found.

$ agenraci validate docs/demo/charter-fixed.yaml
AgenRACI charter: demo  (docs/demo/charter-fixed.yaml)
3 roles · 3 members · 2 action types

✓ R1 single accountable
✓ R2 coverage
✓ R3 no contradiction
✓ R4 gate completeness
✓ R5 low-risk gating
✓ R6 acyclic authority

PASS — charter is a valid operating constitution.
```

## Rendering the GIF
Recording the animated GIF needs a terminal recorder (not run in CI):
```bash
# install VHS once: https://github.com/charmbracelet/vhs#installation
vhs docs/demo/demo.tape      # writes docs/demo/demo.gif
```
Then embed it near the top of the root `README.md` (a placeholder comment marks the spot).
