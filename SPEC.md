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
  - { name: <string>, type: human|agent, role: <role-name>, model: <optional>,
      github: <optional GitHub login, if it differs from name> }

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
    github:                          # optional; what `verify --target github` judges
      paths: [<CODEOWNERS pattern>, ...]   # or `github: none` (not a repo change)
```

`github.paths` uses CODEOWNERS pattern syntax; `!` negation, `[ ]` ranges and `\`
escapes are rejected, as GitHub does not support them. See
[docs/verification-contract.md](docs/verification-contract.md) for how verify uses it.

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
- uses an `on_timeout` value that is not one of the three legal forms,
- gives a `github.paths` pattern GitHub's CODEOWNERS syntax does not support, or a
  member `github` handle that is not a single login.

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

- `claude` — **real**. Emits one `.claude/agents/<member>.md` per *agent member*
  (frontmatter + a system-prompt skeleton derived from the charter: the actions
  the role is responsible/accountable for, capability grants and explicit
  "never do X" denials, the gates it approves, its suggestion routes, and the
  human escalation contacts) plus a `CLAUDE.governance.md` snippet to paste into
  `CLAUDE.md`. Multi-file output uses `--- FILE: <path> ---` markers;
  `compile --out-dir DIR` splits and writes them (with path-escape protection).
  Members' `model:` ids map onto Claude Code's model tokens when unambiguous.
- `github` — **real**. Emits three things in one pass:

  1. **CODEOWNERS scaffold** — for each gated action with `github.paths`, one rule
     per pattern owned by that action's human *approvers*, in charter order, then a
     last rule giving `/.github/CODEOWNERS` to the people who approve every mapped
     action. A gated action with no `github` key gets a note asking for a mapping;
     one whose approver role has no human member is flagged (GitHub code owners must
     be people) and gets no rule; `github: none` actions are skipped. When two
     actions with different approvers cover the same files, a note says so, since
     GitHub applies only the later rule there.

  2. **Branch-protection checklist** — a commented, human-readable summary of each
     gated action that maps to GitHub: required approver, whether timeout may
     auto-proceed (low-risk only), and the break-glass condition.

  3. **Applyable branch-protection JSON** — the real GitHub classic branch-protection
     PUT body, delimited by `# --- BEGIN protection.json ---` and
     `# --- END protection.json ---`. Fields emitted: `required_status_checks`,
     `enforce_admins`, `required_pull_request_reviews` (with
     `required_approving_review_count`, `require_code_owner_reviews` and
     `dismiss_stale_reviews`), and `restrictions`. Values are the charter floor:
     `required_approving_review_count` is always `1`; `dismiss_stale_reviews` is
     always `true` (otherwise commits pushed after an approval merge on it);
     `require_code_owner_reviews` is `true` only when a gated action that is not
     `github: none` has a human approver (set to `false` with a note otherwise,
     because GitHub code owners must be human and reviews are still required). Immediately below the JSON, the output
     includes a ready-to-run `gh api` apply command and an `agenraci verify`
     round-trip step:

     ```
     gh api repos/OWNER/REPO/branches/BRANCH/protection \
       --method PUT --input protection.json
     agenraci verify CHARTER.yaml --repo OWNER/REPO   # should report no drift
     ```

     No auto-merge hint is emitted: GitHub auto-merge waits for required reviews
     and checks, so it does not bypass a blocking gate (#81).

  **Scope:** AgenRACI prints the JSON and the `gh api` command; the human runs them.
  AgenRACI never POSTs, PUTs, or applies anything to GitHub.
- `humanlayer` — **stub**: approval-gate routing (real emit: v0.3).
- `langgraph` — **stub**: interrupt/checkpoint nodes (real emit: v0.4).

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
- `agenraci validate --format json` prints one machine-readable object per
  charter instead of the human report — `{charter, project, ok, error, rules}`,
  where each rule carries `passed` and any `findings` — so a CI step or dashboard
  can consume per-rule results without scraping coloured text. When a charter
  fails to even load (a schema or YAML error), `error` is non-null, `rules` is
  empty, and the load-level problems appear under a top-level `findings` array
  instead; consumers branch on `error`. With several charters it emits one JSON
  object per line (JSON Lines). When `--explain` is also passed, each rule
  finding additionally carries an `explanation` string with the same
  plain-language fix used by the human report. Exit codes are unchanged:
  non-zero if any charter fails.
- `agenraci validate --format sarif` prints a single SARIF 2.1.0 document
  aggregating findings from every charter passed (code-scanning uploads one
  file), so failures can surface as GitHub code-scanning alerts. Findings are
  file-level — the checker references a *target* (an action or role name), not a
  source line — so each result points at the charter file. Exit codes are
  unchanged.
- `agenraci verify --target github` checks that a branch's protection actually
  enforces what the charter declares (read-only — AgenRACI never changes the
  repo), as defined in [docs/verification-contract.md](docs/verification-contract.md).
  For each gated action it asks whether a change in the action's `github.paths` can
  merge without approval from a human in the gate's `approver` role. It reads
  CODEOWNERS the way GitHub does (the last matching rule applies, any one owner on it
  can approve, owners without write access are ignored, teams count by their
  members) and judges every path the patterns can match, including files a pull
  request could add, by an exact search over the patterns; it does not list the
  branch's files. It also requires one approving review, code-owner review and
  stale-review dismissal on the branch, checks GitHub's CODEOWNERS error list, and
  checks who owns the CODEOWNERS file itself. Each action is `verified`, `drift`,
  `incomplete` (could not be established: missing or unreadable evidence, an
  unsupported pattern, an approver role with no human, no `github` key; never a
  pass) or `not-applicable` (`github: none`); drift beats incomplete beats verified.
  Bypass permissions are not judged yet (#80): live mode does not read them, so a
  live run is `incomplete`, and an offline export that lists any bypass is
  `incomplete`. Enabled auto-merge is not drift: GitHub auto-merge waits for
  required reviews and checks (#81). Exit codes: `0` verified or nothing to
  verify, `1` drift, `2` incomplete or could-not-check; `--allow-incomplete`
  turns `2` into `0` with a warning and never hides drift. `--format json` adds a
  top-level `status`, `evidence` (`live` or `snapshot`) and per-action results
  (`ok`, `findings` and `unenforceable` are kept, deprecated); `--format sarif`
  reports drift as `error` and incomplete as `warning`. The branch settings come
  either live via `gh api` (`--repo OWNER/REPO`, reading and unioning GitHub's
  classic branch-protection and ruleset shapes) or from an offline export
  (`--settings <json>`, in which an absent field is missing evidence, never a
  default). Only GitHub's "Branch not protected" 404 means "no classic
  protection"; any other failure to read a control makes the actions that need it
  `incomplete`. A repo-level 404/401/403 or a missing `gh` is could-not-check,
  never drift.
  - `--org ORG` sweeps **every repo in an org** (or a user account) against one
    charter (the governance-audit case: "does the whole org enforce our
    accountability rules?"), aggregating into one report. A single repo that
    can't be read is isolated as `could-not-check` so it never crashes the sweep;
    the sweep's status is the worst repo status, so it exits `1` if **any** repo
    drifts and `2` if any repo is incomplete or could-not-check. Exactly one of
    `--settings`, `--repo`, or `--org` is required. The sweep is sequential (~4
    `gh api` calls per repo), so large orgs are slow and may hit rate limits (a
    rate-limited repo surfaces as `could-not-check`). The org listing is capped
    (1000 repos; `--limit N` changes it); beyond that the report is flagged
    `truncated` and is at least `incomplete`, so it is never mistaken for a
    complete audit.

  A **composite GitHub Action** at `verify/action.yml` wraps this command for
  CI use (referenced as `jing-ny/agenraci/verify@<ref>`). It accepts six
  inputs — `charter` (default `charter.yaml`), `repo` (default
  `${{ github.repository }}`), `branch` (default `main`), `token` (default
  `${{ github.token }}`, passed to `gh` as `GH_TOKEN`), `allow-incomplete`
  (default `"false"`) and `python-version` (default `"3.12"`) — and propagates the
  `agenraci verify` exit code directly, so drift and an incomplete check fail the
  CI job. **Auth note:** the default `GITHUB_TOKEN` does not have admin permission
  on the repo, so it usually cannot read branch protection and the check exits 2
  (incomplete) rather than 1 (drift). Callers who need a full check must pass an
  admin-scoped token in `token`. The Action is
  read-only and never modifies the repo or intercepts actions at runtime.

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

### Still open (revisit at v0.3)

- Whether `low_risk` should attach to **capabilities** rather than whole actions.
- A richer authority graph beyond gate `escalate_to` edges (e.g. standing veto
  relations independent of any single gate).
- Shared role-library import mechanics (a `roles.yaml` referenced by many charters).
