# AgenRACI specification (v0.1)

This document defines the AgenRACI data model, the `charter.yaml` schema, and the
linter rules. It is the authoritative reference for implementations.

---

## 1. Scope

AgenRACI is a **specification + linter + adapters**, not an orchestration runtime.
A `charter.yaml` declares the *operating constitution* of a mixed human +
AI-agent team. The linter validates it; adapters compile it into runtime config
for tools that already exist (HumanLayer, LangGraph, …).

---

## 2. The three axes

A charter keeps three concerns independent. Collapsing them is the source of most
"who does what" confusion.

| Axis | Question it answers | Where it lives in the schema |
|------|---------------------|------------------------------|
| **Function** | What do you *do*? | the `roles` library + each action's R/A/C/I |
| **Permission** | What may you *touch*? | `capabilities` (per role: `grant` / `deny`) |
| **Authority** | Whose call *wins* on conflict? | each action's `accountable`, plus gate `on_timeout: escalate_to:<role>` |

They are independent: a role can be **Accountable** for a fact, **denied** code
access, yet able to **block** a merge (by being the `accountable`/approver on the
merge action). Authority lives in each action's `accountable` and in the
`escalate_to` edges of gates; R6 checks that those escalation edges never form a
cycle (no infinite tie-break loop).

---

## 3. RBAC: roles defined once, members assigned

`Role` is a **first-class, standalone** object. Permissions attach to roles,
never to individual members. Members (humans or agents) are *assigned* to roles,
so the charter's size is fixed no matter how many agents you add — adding an
agent is a one-line appointment.

The default role library (keep it minimal; merge roles before adding them):

| Code | Role | Function | Typically held by |
|------|------|----------|-------------------|
| O | orchestrator | Plans, sequences, breaks ties, owns the roadmap | a human |
| E | engineer | Writes/changes code; owns merge & deploy | a human + coder agent(s) |
| X | domain_expert | Provides domain truth; cannot touch code; blocks via review | an agent or human advisor |
| R | researcher | Investigates unknowns; produces options + a recommendation; does not decide | an agent |
| V | reviewer | Quality/correctness gate; can veto a merge; on some decisions outranks O | an agent (+ human spot-checks) |
| M | monitor | Watches usage + tech health; raises issues; does not fix | an agent |

> **Why `monitor` is its own role:** its permission profile (`read_analytics`
> only, everything else denied) and its "watch-but-never-fix" function are
> distinct enough to be worth separating. Collapse it later if it proves
> redundant.

---

## 4. RACI per action type

Enumerate **action types** that can occur in the project — not individual tasks.
Each action declares:

- `responsible` — who does the work (a role name, or `any`)
- `accountable` — the single role that owns it (this is also the authority signal)
- `consulted` — roles consulted *before* (list)
- `informed` — roles informed *after* (list)
- `capabilities` — the capability tokens this action touches (list)
- `low_risk` — boolean (default `false`)
- `gate` — optional approval gate
- `suggestion_route` — optional route for a blocked-but-confident actor's input

**Exactly one Accountable** per action is the operational meaning of "complete
but not duplicated" (MECE): 0 → a gap, 2+ → a conflict. Enforced by R1.

---

## 5. Async escape hatches

Every **gate** and every **deny** that blocks a downstream action must declare
its async behavior, or the charter is rejected:

1. **`on_timeout`** — if the approver doesn't respond in time:
   - `block` (default),
   - `escalate_to: <role>`, or
   - `proceed_if_low_risk` — **only** legal on an action tagged `low_risk: true`.
2. **`break_glass`** — the emergency path (`who`, `condition`,
   `requires_after_review`), e.g. an engineer may hotfix-deploy during a SEV-1
   without the normal gate, with mandatory after-the-fact review.
3. **`suggestion_route`** (`from`, `to`, `as`) — where a blocked-but-confident
   actor's input goes so it isn't silently dropped (e.g. the Expert files a
   `correction_request` the Coder must clear before the Reviewer can approve).

This is what stops your own safety rules from deadlocking the team, and prevents
"ghost completions" where an agent *thinks* it finished but the real system
didn't move.

---

## 6. The `charter.yaml` schema

```yaml
project: <string>

roles: [<role-name>, ...]            # the role library (declared inline in v0.1)

members:
  - { name: <string>, type: human|agent, role: <role-name>, model: <optional> }

capabilities:                        # per role; a role may be omitted (no caps)
  <role-name>: { grant: [<cap>, ...], deny: [<cap>, ...] }

actions:
  <action-id>:
    responsible: <role-name>|any
    accountable: <role-name>         # or a list; R1 requires exactly one
    consulted:   [<role-name>, ...]  # optional
    informed:    [<role-name>, ...]  # optional
    capabilities: [<cap>, ...]       # optional; the caps this action touches
    low_risk: <bool>                 # optional, default false
    gate:                            # optional
      approver: <role-name>
      on_timeout: block | proceed_if_low_risk | escalate_to:<role-name>
      break_glass: { who: <role-name>, condition: <string>, requires_after_review: <bool> }
    suggestion_route:                # optional
      from: <role-name>
      to:   <role-name>
      as:   <string>
```

> **Modelling note.** `Role` is a standalone object so a future version can load
> a shared role library from a separate file without a schema rewrite. For v0.1
> roles are declared inline (names in `roles`, permissions in `capabilities`);
> `Charter.get_roles()` assembles the `Role` objects.

### Structural (referential) validation

Before the semantic rules run, the schema enforces referential integrity and
will reject a charter that:

- declares a duplicate role,
- assigns a member to an undeclared role,
- references an undeclared role in any of `responsible` (except `any`),
  `accountable`, `consulted`, `informed`, `gate.approver`,
  `gate.on_timeout: escalate_to:<role>`, `suggestion_route.from/to`,
- attaches a `capabilities` block to an undeclared role,
- uses an `on_timeout` value that is not one of the three legal forms.

Capability *references* in actions are intentionally **not** checked here —
that's R2's job, so the linter can report dead/undeclared capabilities with a
helpful message.

The loader also rejects a charter with a **duplicate YAML key** (for example two
`actions:` blocks, or two actions of the same name in one block). Standard YAML
silently keeps the last value; for a file that is a team's source of truth, a
silently dropped rule is a correctness hazard, so the load fails with a
line-numbered error instead. YAML anchors and merge keys (`<<: *anchor`) are
still supported.

---

## 7. Linter rules

Each rule is a pure function returning structured errors that name the offending
action/role.

- **R1 — single accountable.** Every action type has exactly one `accountable`
  role. 0 → gap; 2+ → conflict.
- **R2 — coverage.** No capability is declared (in any role's grant/deny) but
  unused by any action ("dead permission"); no action touches a capability that
  is not declared.
- **R3 — no contradiction.** No role both grants and denies the same capability.
- **R4 — gate completeness.** Every `gate` declares `on_timeout` (schema-required)
  **and** `break_glass`; every role that is `consulted` on an action but `deny`-ed
  a capability that action touches must have a `suggestion_route` *from* it.
- **R5 — low-risk gating.** An action may use `on_timeout: proceed_if_low_risk`
  **only if** it is tagged `low_risk: true`; otherwise it's an error.
- **R6 — acyclic authority.** The escalation graph has no cycles. Every gate
  whose `on_timeout` is `escalate_to:<role>` adds an edge `approver → <role>`
  ("if the approver stalls, the decision passes up to this role"). Following those
  edges must always terminate; if escalation can return to a role already on the
  path — including a gate that escalates to its own approver — no decision can
  ever be finally settled, and R6 reports the loop. Charters that express
  authority only via `accountable` (no `escalate_to`) contribute no edges and so
  always pass.

---

## 8. Adapters

`agenraci compile --target <t> <charter.yaml>` compiles a *validated* charter into
config for an existing tool. The emit is config a human reviews and applies — not
runtime enforcement.

- `github` — **real**. Emits a CODEOWNERS starting point (humans accountable for
  gated actions) and a branch-protection checklist derived from each gate
  (required approver, whether timeout may auto-proceed, break-glass). Because a
  charter governs action *types*, not file paths, the CODEOWNERS lines are a
  scaffold to scope; a gate whose approver role has no human member is flagged.
- `humanlayer` — **stub**: approval-gate routing (real emit: v0.2).
- `langgraph` — **stub**: interrupt/checkpoint nodes (real emit: v0.3).

The CLI refuses to compile a charter that fails any linter rule, and labels the
stub targets `(STUB)` in their output.

### Other CLI surfaces

- `agenraci schema` prints the charter JSON Schema, generated from the same
  pydantic models the checker uses (so it never drifts). The `init` template
  carries a `# yaml-language-server: $schema=` line, giving editor autocomplete
  and inline validation against that schema.
- `agenraci validate --format github` additionally emits `::error` workflow
  commands, so the GitHub Action surfaces failures as PR file annotations. The
  default `human` format is unchanged.

---

## 9. Resolved design decisions (v0.1)

1. **Monitor is its own role** — kept, not merged into Engineer.
2. **Authority via per-action `accountable`, with `escalate_to` for timeouts** —
   one escalation case ("reviewer beats orchestrator on merge") is
   `accountable: reviewer`; gate timeouts may escalate via `escalate_to:<role>`,
   and R6 checks the resulting escalation graph is acyclic.
3. **`proceed_if_low_risk` is a guarded opt-in** — legal only with
   `low_risk: true` (R5). Default is `block`.
4. **Roles are first-class, standalone** — inline for v0.1, but modelled for a
   future shared/imported role library.

### Still open (revisit at v0.2)

- Whether `low_risk` should attach to **capabilities** rather than whole actions.
- A richer authority graph beyond gate `escalate_to` edges (e.g. standing veto
  relations independent of any single gate).
- Shared role-library import mechanics (a `roles.yaml` referenced by many charters).
