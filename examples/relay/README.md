# Relay — the all-agent worked example

**Relay** is an autonomous customer-support triage team. Tickets come in; the team
classifies them, researches the answer, drafts a reply, checks it for correctness and
safety, sends it, and escalates the hard ones. What makes it a useful example is that
**every role-holder is an AI agent** — there are no humans in the member list. It shows
the strong form of AgenRACI's central claim: agents are first-class role-holders, an
agent can be the single **Accountable** party for an action, and an agent can even hold
the break-glass key.

> In production you would usually keep a human as the *ultimate* break-glass authority.
> Relay deliberately shows the all-agent extreme so the model is unambiguous.

Validate it:

```bash
agenraci validate examples/relay/charter.yaml
```

## The team: 5 agents, 0 humans

| Member | Type | Role | Notes |
|--------|------|------|-------|
| Atlas | agent | lead (L) | sets policy, breaks ties, owns escalation |
| Sortie | agent | triager (T) | classifies & prioritizes tickets |
| Quill | agent | responder (P) | drafts and sends replies |
| Sage | agent | researcher (R) | pulls KB facts; **cannot send or classify** |
| Vera | agent | auditor (V) | correctness/safety gate; **cannot send** |

The same **separation of powers** as the human-in-the-loop example, held entirely by
agents: Vera (Auditor) is not Quill (Responder), and on "send a reply" Vera
**outranks** Quill. The actor who writes the reply never approves their own send.

## The RACI matrix

> R = does the work · A = answerable / final owner · C = consulted before · I = informed after

| # | Action type | L (Atlas) | T (Sortie) | P (Quill) | R (Sage) | V (Vera) |
|---|-------------|:--------:|:---------:|:--------:|:-------:|:-------:|
| B1 | Set support policy | **A·R** | I | I | C | C |
| B2 | Classify / prioritize a ticket | I | **A·R** | – | C | – |
| B3 | Research the answer (KB lookup) | – | – | I | **A·R** | – |
| B4 | Draft & send a reply | I | – | R | C | **A** |
| B5 | Escalate to a human | **A·R** | I | I | – | C |

## The interesting rows

- **B4** — `accountable: auditor`. Quill is *Responsible* for writing and sending,
  but Vera owns whether it goes out, via a gate with `on_timeout: block` (an
  unreviewed reply never auto-sends). Sage is *Consulted* but **denied** `send_reply`,
  so the charter declares a `suggestion_route` — a `fact_correction` from researcher
  to responder — so a known-wrong fact isn't silently dropped. This is the
  "blocked-but-confident actor" case that **R4** guards.

- **B2** — Sortie owns triage outright (`A·R`). Sage is *Consulted* but **denied**
  `classify`, so a `reclassify_hint` `suggestion_route` carries its input back to the
  triager instead of vanishing.

- **B5** — an *agent* (Atlas) is Accountable for deciding when to pull in a human, and
  holds the `break_glass` for legal/safety cases. Accountability sitting on an agent is
  the whole point of this example.

## Which rules each row exercises

- **R1** — every row has exactly one **A**.
- **R2** — every declared capability (`set_policy`, `escalate`, `classify`,
  `read_kb`, `send_reply`, `block_send`) is touched by some action, and no action
  touches an undeclared one.
- **R3** — no role grants and denies the same capability.
- **R4** — every gate (B4, B5) has `on_timeout` + `break_glass`; every
  consulted-but-denied role (Sage on B2 and B4) has a `suggestion_route`.
- **R5** — no action uses `proceed_if_low_risk`, so none needs `low_risk: true`.
  (See the Sprout example for an action that does.)
