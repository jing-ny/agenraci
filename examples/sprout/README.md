# Sprout — the worked example

**Sprout** is a houseplant-care reminder app. It reminds users to water their
plants, tracks streaks, and sends push notifications. It's simple enough to hold
in your head, but complete enough to exercise every AgenRACI role: it needs
**coding** (the app), **research** (which push service, which framework),
**domain expertise** (correct watering science per species — getting this wrong
hurts users' plants, so it's a real accountability), **monitoring** (are users
logging waterings? retention? crash rate?), and **incident handling**
(notifications silently failing).

Validate it:

```bash
agenraci validate examples/sprout/charter.yaml
```

## The team: 2 humans, 6 agents

| Member | Type | Role | Notes |
|--------|------|------|-------|
| **you** | human | orchestrator (O) | breaks ties, owns the roadmap |
| Atlas | agent | researcher (R) | investigates, recommends |
| Fern | agent | domain_expert (X) | horticulture truth; **cannot touch code** |
| Pulse | agent | monitor (M) | watches usage + health |
| **dev** | human | engineer (E) | owns merge & deploy |
| Cody | agent | engineer | coder sub-actor under E |
| Vera | agent | reviewer (V) | independent of Cody on purpose |
| Otto | agent | engineer | ops/incident sub-actor under E |

Note the deliberate **separation of powers**: Vera (Reviewer) is not the same
agent as Cody (Coder), and on the "merge to main" action Vera **outranks** even
the Orchestrator. The builder never approves their own merge.

## The RACI matrix

> R = does the work · A = answerable / final owner · C = consulted before · I = informed after

| # | Action type | O (you) | E (dev) | X (Fern) | R (Atlas) | V (Vera) | M (Pulse) |
|---|-------------|:------:|:------:|:-------:|:--------:|:-------:|:--------:|
| A1 | Set roadmap / pick next feature | **A·R** | C | C | C | – | C |
| A2 | Choose a *technical* approach | I | **A** | C | R | C | – |
| A3 | Establish a *domain* fact (watering interval) | I | I | **A·R** | C | – | – |
| A4 | Write / modify code | I | **A·R** | C | – | – | – |
| A5 | Merge to main | I | R | – | – | **A** | – |
| A6 | Deploy to production | I | **A·R** | – | – | C | I |
| A7 | Triage & fix a production incident | I | **A·R** | – | – | C | I |
| A8 | Interpret usage analytics / flag a problem | **A** | I | C | – | – | R |
| A9 | Communicate with users | **A·R** | – | C | – | – | – |
| A10 | Spend money (paid infra / API) | **A** | C | – | – | – | – |

## The interesting rows

- **A3 vs A4** — Fern (Expert) is *Accountable* for the watering fact (A3) but
  only *Consulted* on the code that uses it (A4). Her power over code is real but
  **indirect**: she can't push a commit, but she files a `correction_request`
  (`suggestion_route` on A4) that the engineer must clear before A5 can pass.
  This is exactly the "blocked-but-confident actor" case that **R4** guards.

- **A5** — `accountable: reviewer`. Vera owns what enters `main`; dev is merely
  *Responsible* for doing the merge. This is the "reviewer beats the
  orchestrator" rule, encoded as authority-via-`accountable` (v0.1).

- **A6 / A7** — Vera is *Consulted* but **denied** `deploy`, so each carries a
  `suggestion_route` from the reviewer (a `deploy_objection` / `fix_objection`)
  — her objection has somewhere to go instead of being silently dropped. A7 also
  declares a `break_glass` so engineering can hotfix during a SEV-1.

- **A8** — the **only** action tagged `low_risk: true`, and therefore the only
  one allowed to use `on_timeout: proceed_if_low_risk` (reading/flagging
  analytics is non-destructive). **R5** rejects that timeout mode anywhere else.

- **A9 / A10** — agents may *draft* the email or *request* the spend, but a named
  human (you) is Accountable, enforced by a gate with `on_timeout: block`. These
  never auto-proceed, because they are not `low_risk`.

## Which rules each row exercises

- **R1** — every row has exactly one bold **A**.
- **R2** — every declared capability (`edit_code`, `merge`, `deploy`, `spend`,
  `contact_users`, `read_analytics`, `block_merge`) is touched by some action,
  and no action touches an undeclared one.
- **R3** — no role grants and denies the same capability.
- **R4** — every gate (A5, A7, A8, A9, A10) has `on_timeout` + `break_glass`;
  every consulted-but-denied role (Fern on A4, Vera on A6/A7) has a
  `suggestion_route`.
- **R5** — only A8 uses `proceed_if_low_risk`, and only A8 is `low_risk: true`.
