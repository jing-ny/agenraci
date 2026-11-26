# GitHub verification contract (draft)

Status: **draft for maintainer review** (issue #78). Nothing here is implemented yet.
Today's `agenraci verify --target github` behaves as described in
[SPEC.md §8](../SPEC.md#8-adapters); this document defines what it *should* claim once
#79, #80 and #81 land. Sections marked **Decision** need a maintainer call before
implementation starts.

## 1. The question verify answers

For each gated action that the charter maps to GitHub, verify answers one question:

> Can a change covered by this action reach the protected branch without approval
> from someone the charter allows to approve it?

It answers with observed GitHub configuration only. It never changes the repository,
never watches individual pull requests, and never claims anything about runtime,
deployment or spending behaviour.

## 2. Terms

| Term | Meaning | Where it comes from |
| --- | --- | --- |
| Accountable owner | The humans in the action's `accountable` role. They own the outcome. | charter `actions.<a>.accountable` + `members` |
| Designated approver | The humans in the gate's `approver` role. Their approval is what the gate requires. | charter `actions.<a>.gate.approver` + `members` |
| Eligible approvers | The set whose approval satisfies the gate (see Decision D1). | derived |
| Break-glass holders | The humans in the gate's `break_glass.who` role. | charter `gate.break_glass` |
| Scope | The repository paths whose changes the action covers. | charter (new field, see Decision D3) |
| Identity evidence | The link between a charter member and a GitHub account. | member `name`, or a new optional `github` handle |
| Observed controls | What GitHub enforces on the branch: required reviews, code-owner review, the CODEOWNERS rule that applies to each path, and who can bypass. | classic branch protection, rulesets, CODEOWNERS, repo settings |

A charter identity is not proof of a GitHub identity or of its permissions. Verify
treats a member name (or its `github` handle) as a GitHub login by convention and
says so in its output.

## 3. Result for one action

Each in-scope gated action gets exactly one status.

| Status | Meaning |
| --- | --- |
| `verified` | Every control the action needs was observed, and nothing observed lets an ineligible person approve or skip approval. |
| `drift` | Observed configuration contradicts the charter: approval is not required, or someone ineligible can satisfy or skip it. |
| `incomplete` | Verify could not establish the guarantee: evidence is missing, unreadable, or outside what AgenRACI models. Never a pass. |
| `not-applicable` | The action has no GitHub mapping (for example a deploy, spending or runtime gate). Listed, never counted as verified. |

Precedence when several facts apply to one action: `drift` beats `incomplete` beats
`verified`. A contradiction is reported even if other evidence is missing.

### What `verified` requires

All of these, for every path in the action's scope:

1. The branch requires at least one approving review (classic protection or a
   ruleset; the union of both is used, as today).
2. The branch requires code-owner review.
3. The CODEOWNERS rule that applies to the path is the **last matching** rule, and it
   lists at least one owner.
4. **Every** owner listed on that rule is an eligible approver. GitHub accepts approval
   from any one listed owner, so one ineligible co-owner breaks the guarantee. More
   owners never means stronger protection.
5. Every listed owner resolves to an individual human login. A team or email owner is
   `incomplete` unless its members can be read and all are eligible.
6. Bypass evidence was read and shows no one outside the allowed set can skip the
   requirement (see §4).

### Auto-merge

Auto-merge is **not** a bypass. GitHub's auto-merge waits for required reviews and
checks. With sufficient review settings, `allow_auto_merge` alone never produces
drift (#81). Missing required reviews are still drift whether or not auto-merge is on.
Verify also never cites auto-merge being off as evidence of enforcement.

## 4. Bypass evidence

A requirement that someone can skip is not a requirement for that person. Verify
reads, where the token allows:

- classic protection `enforce_admins` (off means repository admins can merge without
  the review);
- classic `required_pull_request_reviews.bypass_pull_request_allowances` (users,
  teams, apps);
- ruleset `bypass_actors` (organization admins, repository roles, teams, apps, deploy
  keys) on every ruleset that targets the branch.

| Observed | Status |
| --- | --- |
| No bypass actors, admins enforced | contributes to `verified` |
| A bypass actor who is a break-glass holder | `verified`, with the bypass listed (Decision D4) |
| Any other bypass actor | `drift` |
| A bypass list that could not be read (common with the default workflow token) | `incomplete` |
| A role- or team-based bypass whose members could not be resolved | `incomplete` |

## 5. Evidence sources and failures

| Situation | Treatment |
| --- | --- |
| Repository itself unreadable (404/401/403 on `repos/{repo}`, no `gh`, network) | `could-not-check` for the whole repo, as today |
| One control unreadable (for example classic protection 403, ruleset bypass list omitted) | the actions that depend on it are `incomplete`, naming the control |
| Classic protection 404 | no classic protection (benign), as today |
| No CODEOWNERS file | `drift` for every in-scope action that needs code-owner review |
| Offline `--settings` export | each field must be stated; an **absent** field is missing evidence (`incomplete`), not a default of `0`/`false`. New fields: `codeowners` (the raw file text, so precedence can be evaluated), `enforce_admins`, `bypass_actors`. |
| Snapshot vs live | output always says which one it used; a snapshot is evidence about the moment it was taken |

## 6. Output and compatibility

### Exit codes

Today: `0` clean, `1` drift, `2` could-not-check. Proposed:

| Exit | When |
| --- | --- |
| `0` | every in-scope action is `verified` (or the charter has no gated actions) |
| `1` | any action is `drift` |
| `2` | no drift, but something is `incomplete` or `could-not-check` |

`not-applicable` actions never change the exit code. See Decision D2 for whether
`incomplete` should exit `2` and whether to offer an opt-out flag.

### JSON

Additive for one release, then the old keys are removed:

- New top-level `status` (`verified` / `drift` / `incomplete` / `could-not-check`),
  `evidence` (`live` or `snapshot`), and an `actions` array with one entry per gated
  action: `{action, status, scope, eligible_approvers, reasons[]}`.
- `ok` keeps its current meaning (no drift) for one release, marked deprecated.
- `findings` keeps drift findings. `unenforceable` is kept as an alias of the
  `incomplete` entries whose reason is `no-human-approver`, marked deprecated.

### GitHub Action

Propagates the exit code unchanged. With the default `GITHUB_TOKEN`, branch protection
and bypass lists are usually unreadable, so the expected result is exit `2` with the
unreadable controls named. The docs must say that an admin-scoped `GH_TOKEN` is needed
for a full result.

### Org sweep

Each repo gets one of `verified`, `drift`, `incomplete`, `could-not-check`. The sweep
exits with the worst repo result using the table above. A truncated listing makes the
whole sweep `incomplete`. SARIF keeps reporting drift as `error` and adds `incomplete`
as `warning`.

### Versioning

AgenRACI is pre-1.0. The exit-code and JSON changes ship together in the next minor
release (0.3.0) with a migration note in the release notes.

## 7. Examples

All examples use one gated action `merge_to_main`, a branch requiring one approving
review with code-owner review on, admins enforced and no bypass actors, unless the row
says otherwise. Alice is the designated approver; Carol is the accountable owner where
the row says so; Bob is neither.

| # | Setup | Today | Under this contract |
| --- | --- | --- | --- |
| 1 | CODEOWNERS `* @alice` | pass | `verified` |
| 2 | `* @alice`, then a later `* @bob` (later rule wins) | pass (false pass, #79) | `drift`: the last matching rule names only Bob |
| 3 | `* @alice @bob` | pass (false pass, #79) | `drift`: Bob can satisfy owner review |
| 4 | `* @alice`, then `/docs/` with no owner, action scope includes `docs/` | pass | `drift`: no owner on an in-scope path |
| 5 | Accountable Carol, approver Alice, `* @alice` | drift (Carol missing) | `verified` (under D1 option a) |
| 6 | Accountable Carol, approver Alice, `* @carol` | pass | `drift` (under D1 option a) |
| 7 | `* @alice @org/release`, team members unreadable | pass (team ignored) | `incomplete` |
| 8 | Accountable and approver roles have only agent members | `unenforceable`, exit 0 | `incomplete` (reason `no-human-approver`) |
| 9 | Auto-merge on, reviews required, gate `on_timeout: block` | drift (#81) | `verified` |
| 10 | Required reviews 0, auto-merge on | drift | `drift` |
| 11 | Ruleset bypass actor: repository admin role, admins not break-glass holders | pass | `drift` |
| 12 | Ruleset bypass actor is the break-glass holder | pass | `verified`, bypass listed (under D4 option a) |
| 13 | Live run with default `GITHUB_TOKEN`, protection endpoint 403 | could-not-check, exit 2 | `incomplete`, exit 2, names the control |
| 14 | Offline export with no bypass fields | pass | `incomplete` |
| 15 | A second gated action `deploy_prod` with no GitHub mapping | judged like a merge | `not-applicable` |

## 8. Out of scope

Runtime interception, deployment and spending enforcement, per-pull-request review
history, GitLab, automatic remediation, and a GitHub App. Owners who lack write access
are a known gap: GitHub ignores them as code owners, and verify does not yet read
collaborator permissions. Until it does, the output notes this limitation.

## 9. Decisions for the maintainer

- **D1 — Who must approve.** (a) the designated approver only (`gate.approver`), which
  matches what a gate means; (b) the accountable owner only, which is today's
  behaviour; (c) either, the union. Draft assumes (a).
- **D2 — Exit code for `incomplete`.** (a) exit `2`, with an `--allow-incomplete` flag
  that exits `0` instead; (b) exit `0` with a warning, which keeps today's green CI but
  can look like a guarantee; (c) a new exit code `3`. Draft assumes (a).
- **D3 — Which actions verify judges, and over which paths.** (a) a new optional
  per-action field `github: {paths: [...]}`; actions without it are `not-applicable`,
  except that a charter with no mapping at all falls back to today's "every gated
  action covers `*`" for one release, with a warning; (b) require the mapping
  immediately; (c) keep judging every gated action over `*`. Draft assumes (a).
- **D4 — Break-glass bypass.** (a) a bypass actor who holds the gate's break-glass role
  is allowed and listed; (b) any bypass actor is drift. Draft assumes (a).
