# blog — one step up from hello-world

A small newsletter team: a human editor, an AI writer, and an AI fact-checker.
It's still tiny, but it introduces the machinery that
[`hello-world`](../hello-world/) leaves out — an approval **gate**, an
**emergency path**, a route for blocked input, and a **separation of powers** —
without the depth of [`sprout`](../sprout/) or [`relay`](../relay/).

```bash
agenraci validate examples/blog/charter.yaml
```

## The team: 1 human, 2 agents

| Member | Type | Role | Notes |
|--------|------|------|-------|
| **you** | human | editor | run the newsletter; press publish |
| Iris | agent | writer | drafts posts |
| Cite | agent | factchecker | checks claims; **cannot write**, can **block** a publish |

## The RACI matrix

> R = does the work · A = answerable / final owner · C = consulted before

| Action | editor (you) | writer (Iris) | factchecker (Cite) |
|--------|:------------:|:-------------:|:------------------:|
| `draft_post` | **A** | R | C |
| `publish_post` | R | – | **A** |

## What's new versus hello-world

- **A gate.** `publish_post` has a gate whose approver is the fact-checker, with
  `on_timeout: block` — an unchecked post **never auto-publishes**. This is the
  approval step AgenRACI exists to make explicit (rule **R4**).
- **An emergency path.** The same gate declares a `break_glass`: you (the editor)
  can pull a live post for a `legal_takedown`, with mandatory after-the-fact
  review. Every gate must have one, so a safety rule can't deadlock the team.
- **A route for blocked input.** Cite is *consulted* on `draft_post` but **denied**
  the `draft` capability, so the charter gives its objection a `suggestion_route`
  (a `correction` back to the writer) instead of letting it vanish — also **R4**.
- **Separation of powers.** On `publish_post` the fact-checker is *Accountable*,
  not the editor: the person who presses publish is not the one who owns whether
  the claims hold up. The writer never signs off on their own facts.

## Which rules each row exercises

- **R1** — every action has exactly one **A**.
- **R2** — every declared capability (`draft`, `publish`, `block_publish`) is used
  by some action, and no action uses an undeclared one.
- **R3** — no role both grants and denies the same capability.
- **R4** — the `publish_post` gate has `on_timeout` + `break_glass`; the
  consulted-but-denied fact-checker has a `suggestion_route`.
- **R5** — no action uses `proceed_if_low_risk`, so none needs `low_risk: true`.
  (See [`sprout`](../sprout/) for an action that does.)
