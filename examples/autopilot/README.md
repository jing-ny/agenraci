# Autopilot — the flagship example

This is the case AgenRACI was built for. **Autopilot** is an autonomous coding
team: a planner picks the next unit of work, a coder writes it and opens the PR,
a reviewer owns the merge, and a monitor watches production — and *most of it
happens with no human pressing the button*. One human, the **maintainer**, sets
direction, approves large spend, and holds the emergency key.

That is exactly the situation classic RACI has no answer for: when an agent ships
code or spends money on its own, **who is accountable, and what stops it from
running away?** This charter answers both, up front, and the checker proves the
answer holds together.

Validate it:

```bash
agenraci validate examples/autopilot/charter.yaml
```

## The team: 1 human, 4 agents

| Member | Type | Role | Notes |
|--------|------|------|-------|
| **you** | human | maintainer | sets direction, approves big spend, holds break-glass |
| Nova | agent | planner | triages the backlog, picks work; **cannot touch code** |
| Forge | agent | coder | writes the change, opens the PR; **cannot merge or deploy** |
| Sentinel | agent | reviewer | owns the merge; can veto; **cannot write code or deploy** |
| Pulse | agent | monitor | watches production; raises issues; **touches nothing else** |

Note the deliberate **separation of powers**: Forge (Coder) writes the change but
Sentinel (Reviewer) owns whether it enters `main` — the builder never approves its
own merge. And no agent can deploy to production: that stays a human's call.

## The RACI matrix

> R = does the work · A = answerable / final owner · C = consulted before · I = informed after

| # | Action type | you (maintainer) | Nova (planner) | Forge (coder) | Sentinel (reviewer) | Pulse (monitor) |
|---|-------------|:----:|:----:|:----:|:----:|:----:|
| A1 | Triage & pick next work | C | **A·R** | – | – | – |
| A2 | Write the change | I | I | **A·R** | C | – |
| A3 | Open the PR | I | I | **A·R** | I | – |
| A4 | Run CI (costs money) | I | – | **A·R** | – | – |
| A5 | Merge to main | I | I | C | **A·R** | – |
| A6 | Deploy to production | **A·R** | I | – | C | I |
| A7 | Approve large spend | **A** | I | – | I | – |
| A8 | Watch production | I | I | – | I | **A·R** |

(A7 is `responsible: any` — *any* actor may request a large spend, but the
maintainer is the one Accountable for approving it.)

## The interesting rows

- **A1 / A4 / A8 — agents act with no human in the loop.** These three are the
  whole point. Each is tagged `low_risk: true` and uses
  `on_timeout: proceed_if_low_risk`, so the planner can pick work, the coder can
  run (and pay for) CI, and the monitor can keep watching even when no human is
  around. **R5** is what keeps this honest: `proceed_if_low_risk` is rejected on
  any action *not* explicitly marked low-risk, so "low risk" can never become a
  silent backdoor for an agent to act unsupervised.

- **A4 vs A7 — two kinds of spend.** A normal CI run (A4) is bounded, low-risk
  spend the coder owns and can incur on its own. A *large* spend (A7) — a new GPU
  box, a higher API tier — is gated with `on_timeout: block` and a human
  Accountable. Same capability (`spend`), two very different authority rules,
  because the risk is different.

- **A5 — the reviewer owns the merge.** `accountable: reviewer`. Sentinel owns
  what enters `main`; Forge is merely *Responsible* for doing the work. Forge
  can't merge its own change, so it files a `ready_to_merge` (`suggestion_route`)
  instead of being silently stuck — the "blocked-but-confident actor" case that
  **R4** guards. The gate's `on_timeout: escalate_to:maintainer` means that if
  Sentinel goes dark, the decision rises to the human rather than stalling — and
  **R6** proves that escalation chain never loops back on itself.

- **A6 — production stays human.** Deploy is `accountable: maintainer` with
  `on_timeout: block`: it never auto-proceeds. Sentinel is *Consulted* but
  **denied** `deploy`, so a `deploy_objection` (`suggestion_route`) gives its
  objection somewhere to go.

## Which rules each row exercises

- **R1** — every row has exactly one bold **A**.
- **R2** — every declared capability (`read_repo`, `edit_code`, `open_pr`,
  `merge`, `block_merge`, `deploy`, `spend`) is touched by some action, and no
  action touches an undeclared one.
- **R3** — no role grants and denies the same capability.
- **R4** — every gate (A1, A4, A5, A6, A7, A8) has `on_timeout` + `break_glass`;
  every consulted-but-denied role (Sentinel on A2/A6, Forge on A5) has a
  `suggestion_route`.
- **R5** — only A1, A4, and A8 use `proceed_if_low_risk`, and those are exactly
  the actions tagged `low_risk: true`.
- **R6** — the only escalation edge (A5: reviewer → maintainer) terminates; the
  authority graph has no cycle.
