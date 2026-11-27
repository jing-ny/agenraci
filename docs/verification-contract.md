# GitHub verification contract

Status: **accepted by the maintainer** (issue #78) and **implemented on main except §4**
(bypass evidence, #80). #79 (approval and scope) and #81 (auto-merge) follow it. Until
#80 lands, bypass is never judged: a live run does not read it and reports `incomplete`,
and an offline export that lists any bypass is `incomplete`. "Today" in this document
means the v0.2.1 release, before these changes. The decisions in §9 are settled.

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
| Eligible approvers | The designated approvers (D1). Accountable owners are not eligible unless they are also in the approver role. | derived |
| Break-glass holders | The humans in the gate's `break_glass.who` role. | charter `gate.break_glass` |
| GitHub mapping | A new optional per-action field: `github: {paths: [<CODEOWNERS-style patterns>]}` to judge the action over those paths, or `github: none` to say the action is not a GitHub change (D3). | charter (new field) |
| Identity evidence | The link between a charter member and a GitHub account. | member `name`, or a new optional `github` handle |
| Observed controls | What GitHub enforces on the branch: required reviews, code-owner review, stale-review dismissal, the CODEOWNERS rule that applies to each file in scope, owner write access, and who can bypass. | classic branch protection, rulesets, CODEOWNERS, repo settings |

A charter identity is not proof of a GitHub identity or of its permissions. Verify
treats a member name (or its `github` handle) as a GitHub login by convention and
says so in its output.

## 3. Result for one action

Each gated action gets exactly one status.

| Status | Meaning |
| --- | --- |
| `verified` | Every control the action needs was observed, and nothing observed lets an ineligible person approve or skip approval. |
| `drift` | Observed configuration contradicts the charter: approval is not required, or someone ineligible can satisfy or skip it. |
| `incomplete` | Verify could not establish the guarantee: evidence is missing, unreadable, or outside what AgenRACI models. Never a pass. |
| `not-applicable` | The action declares `github: none`. Listed, never counted as verified. |

A gated action with **no** `github` key is `incomplete` with reason
`no-github-mapping`. Verify cannot tell whether a deploy, release or spending gate is
meant to be a GitHub change, so it never gives such an action an implied
branch-protection guarantee. The output suggests adding `github.paths` or
`github: none`.

Precedence when several facts apply to one action: `drift` beats `incomplete` beats
`verified`. A contradiction is reported even if other evidence is missing.

### What `verified` requires

**Scope.** An action's scope is every file path that matches a pattern in
`github.paths`, whether the file exists on the branch or a pull request could add it.
Each path is judged against the **last** CODEOWNERS rule that matches it. Verify does
not list the branch's files: it treats each pattern as the set of paths it can match
and searches that set exactly, so for each CODEOWNERS rule it can tell whether some
in-scope path ends up owned by that rule, and names the shortest such path in the
output. A rule that applies only to paths no file would ever have cannot cause drift.
If the search would grow too large, or a pattern uses syntax verify does not model,
the action is `incomplete`. (An earlier draft read the branch tree with
`repos/{repo}/git/trees/{branch}?recursive=1`; judging the patterns covers the same
files plus the ones a pull request could add, without a truncated-listing case.)

All of these, for every file in scope:

1. The branch requires at least one approving review (classic protection or a
   ruleset; the union of both is used, as today).
2. The branch requires code-owner review.
3. The branch dismisses stale approvals when new commits are pushed (classic
   `dismiss_stale_reviews`, ruleset `dismiss_stale_reviews_on_push`). Without it, commits
   pushed after an eligible approval can merge unreviewed, so it is `drift`.
   `require_last_push_approval` is recorded in the output but not required.
4. The CODEOWNERS rule that applies to the file is the **last matching** rule, and it
   lists at least one owner.
5. **Every** owner listed on that rule is an eligible approver. GitHub accepts approval
   from any one listed owner, so one ineligible co-owner breaks the guarantee. More
   owners never means stronger protection.
6. Every listed owner resolves to an individual human login. A team or email owner is
   `incomplete` unless its members can be read and all are eligible.
7. Every listed owner has write access (`repos/{repo}/collaborators/{user}/permission`
   for a user, `teams/{org}/{team}/repos/{repo}` for a team).
   GitHub ignores an owner without write access, which can leave the path with no
   effective owner (`drift`). Access that could not be read is `incomplete`.
8. GitHub reports no CODEOWNERS errors on a rule that applies to a file in scope
   (`repos/{repo}/codeowners/errors?ref={branch}`). GitHub skips invalid lines, so an error there is
   `incomplete`, as is an error list that could not be read.
9. The CODEOWNERS file itself is owned only by eligible approvers. Otherwise an
   ineligible owner of that file can approve a change to ownership (`drift`).
10. Bypass evidence was read and shows no one outside the allowed set can skip the
    requirement (see §4).

`verified` describes the configuration at the moment it was read. Admins can change it
later, and it says nothing about changes merged before the check.

The top-level status is the worst action status by the precedence above, ignoring
`not-applicable`. If no action is judged (no gated actions, or every gated action is
`not-applicable`), the top-level status is `nothing-to-verify` and the output says
that nothing was verified. It exits `0`, which keeps today's behaviour for a charter
with no gates; this choice was made in the review fixes and is not one of D1 to D4.

### Auto-merge

Auto-merge is **not** a bypass. GitHub's auto-merge waits for required reviews and
checks. With sufficient review settings, `allow_auto_merge` alone never produces
drift (#81). Missing required reviews are still drift whether or not auto-merge is on.
Verify also never cites auto-merge being off as evidence of enforcement. The
`compile --target github` checklist line "Do NOT enable auto-merge" and the
`allow_auto_merge=false` hint are removed in the same change (#81).

## 4. Bypass evidence

A requirement that someone can skip is not a requirement for that person. Verify
reads, where the token allows:

- classic protection `enforce_admins` (off means repository admins can merge without
  the review) and `required_pull_request_reviews.bypass_pull_request_allowances`
  (users, teams, apps). Reading classic protection needs admin access;
- ruleset `bypass_actors` (organization admins, repository roles, teams, apps, deploy
  keys) on every active ruleset that applies to the branch. `rules/branches/{branch}`
  returns the active rules with their `ruleset_id` but no bypass actors, so verify reads
  each of those rulesets with `repos/{repo}/rulesets/{id}` (which should also cover
  rulesets inherited from the org; if it does not, the org ruleset is read separately
  and may need org access). GitHub may omit `bypass_actors` for a token that cannot edit
  the ruleset; an omitted list counts as unread.

Bypass is judged per requirement. Classic protection and rulesets are combined as a
union, so a requirement holds for an actor if at least one source that enforces it
cannot be bypassed by that actor.

| Observed | Status |
| --- | --- |
| Classic protection: admins enforced, no bypass allowances | contributes to `verified` |
| Classic protection: `enforce_admins` off | repository admins are bypass actors: `drift` unless every admin is a break-glass holder, `incomplete` if the admin list cannot be read |
| Ruleset-only branch: bypass list read and empty (`enforce_admins` does not apply to rulesets; admins bypass only if listed) | contributes to `verified` |
| A bypass actor who is a break-glass holder | `verified` with a caveat: GitHub enforces neither the charter's break-glass `condition` nor `requires_after_review`, so the holder can bypass at any time (D4) |
| Any other bypass actor, in any bypass mode | `drift` |
| A bypass list that could not be read (common with the default workflow token) | `incomplete` |
| A role- or team-based bypass whose members could not be resolved | `incomplete` |

## 5. Evidence sources and failures

| Situation | Treatment |
| --- | --- |
| Repository itself unreadable (404/401/403 on `repos/{repo}`, no `gh`, network) | `could-not-check` for the whole repo, as today |
| One control unreadable (for example classic protection 403, ruleset bypass list omitted) | the actions that depend on it are `incomplete`, naming the control |
| Classic protection 404 with the message "Branch not protected" (or `branches/{branch}` reports `protected: false`) | no classic protection (benign). Any other 404 on that endpoint is treated as unreadable (`incomplete`), because GitHub can return 404 where it means "not allowed". Today any 404 counts as benign. |
| No CODEOWNERS file | `drift` for every judged action, since code-owner review then enforces nothing |
| Offline `--settings` export | each field must be stated; an **absent** field is missing evidence (`incomplete`), not a default of `0`/`false`. New fields: `codeowners` (the raw file text, so precedence can be evaluated; `null` means no file), `codeowners_path` (where it lives, so its own owners can be judged), `codeowners_errors`, `dismiss_stale_reviews`, `owner_permissions`, `teams` (members and access of team owners), `enforce_admins`, `bypass_actors`. No file list is needed, since scope comes from the patterns (§3). |
| Snapshot vs live | output always says which one it used; a snapshot is evidence about the moment it was taken |

## 6. Output and compatibility

### Exit codes

Today a single-repo or offline run exits `0` clean, `1` drift, `2` could-not-check.
Any live `gh api` failure aborts the run as could-not-check (exit `2`), except that on
the branch-protection, `rules/branches` and CODEOWNERS-contents calls an error whose text
contains "404" or "not found" is silently treated as "nothing configured". An `--org` sweep today exits `1` only on
drift; unreadable repos and a truncated listing still exit `0`.

Proposed, for single-repo, offline and org runs alike:

| Exit | When |
| --- | --- |
| `0` | top-level status is `verified` or `nothing-to-verify` |
| `1` | any action, or any repo in a sweep, is `drift` |
| `2` | no drift, but something is `incomplete` or `could-not-check` |

`--allow-incomplete` turns exit `2` into `0` and prints a warning; it never hides drift
(D2). `not-applicable` actions never change the exit code.

### JSON

Additive for one release, then the old keys are removed:

- New top-level `status` (`verified` / `drift` / `incomplete` / `could-not-check` /
  `nothing-to-verify`), `evidence` (`live` or `snapshot`), and an `actions` array with
  one entry per gated action: `{action, status, paths, eligible_approvers, reasons[]}`.
- `ok` keeps its current meaning (no drift) for one release, marked deprecated.
- `findings` keeps drift findings. `unenforceable` is kept as an alias of the
  `incomplete` entries whose reason is `no-human-approver`, marked deprecated. Its
  meaning changes: today it means the *accountable* role has no human; the new reason
  means the *approver* role has no human.

### Charter schema

The `github` fields are new. `schema.py` uses `extra="forbid"`, so a charter that uses
them is rejected by AgenRACI 0.2.x and earlier. The release notes must say so, and the
docs should tell teams to upgrade before adding the fields.

### GitHub Action

Propagates the exit code unchanged. The Action has a `token` input (default
`${{ github.token }}`) passed through as `GH_TOKEN`, so a caller can supply an
admin-scoped token, and an `allow-incomplete` input that passes `--allow-incomplete`. The same
applies to this repo's own `charter.yml` workflow, whose comment suggests granting a
token. With the default token, branch protection and bypass lists are usually
unreadable, so the expected result is exit `2` with the unreadable controls named.

### Org sweep

Each repo gets one of `verified`, `drift`, `incomplete`, `could-not-check`,
`nothing-to-verify`. The sweep exits with the worst repo result using the table above.
A truncated listing makes the sweep at least `incomplete`; truncated plus any drift
exits `1`. SARIF keeps reporting drift as `error` and adds `incomplete` as `warning`.

### Versioning

AgenRACI is pre-1.0. The exit-code, JSON and schema changes ship together in the next
minor release (0.3.0) with a migration note in the release notes.

## 7. Examples

Unless a row says otherwise: one gated action `merge_to_main` with
`github: {paths: ["*"]}`; **Alice holds both the accountable and the approver role**
and has write access; the branch requires one approving review, code-owner review and
stale-review dismissal; admins are enforced, there are no bypass actors, and every
control is readable. Carol and Bob are humans who hold neither role unless the row
says so.

| # | Setup | Today | Under this contract |
| --- | --- | --- | --- |
| 1 | CODEOWNERS `* @alice` | pass | `verified` |
| 2 | `* @alice`, then a later `* @bob` (later rule wins) | pass (false pass, #79) | `drift`: the last matching rule names only Bob |
| 3 | `* @alice @bob` | pass (false pass, #79) | `drift`: Bob can satisfy owner review |
| 4 | `* @alice`, then `/docs/` with no owner | pass | `drift`: no owner on an in-scope path |
| 5 | Accountable Carol, approver Alice, `* @alice` | drift (Carol missing) | `verified` |
| 6 | Accountable Carol, approver Alice, `* @carol` | pass | `drift`: Carol is not an eligible approver |
| 7 | `* @alice @org/release`, team members unreadable | pass (team ignored) | `incomplete` |
| 8 | Accountable and approver roles have only agent members | `unenforceable`, exit 0 | `incomplete` (reason `no-human-approver`) |
| 9 | Auto-merge on, gate `on_timeout: block` | drift before #81, pass after | `verified` |
| 10 | Required reviews 0, auto-merge on | drift | `drift` |
| 11 | Ruleset bypass actor: repository admin role, admins are not break-glass holders | pass | `drift` |
| 12 | Ruleset bypass actor is the break-glass holder | pass | `verified`, bypass listed with the D4 caveat |
| 13 | Live run with default `GITHUB_TOKEN`, protection endpoint 403 | could-not-check, exit 2 (whole run aborts) | `incomplete`, exit 2, names the control |
| 14 | Offline export with no bypass fields | pass | `incomplete` |
| 15 | A second gated action `deploy_prod` with no `github` key | judged like a merge | `incomplete` (reason `no-github-mapping`) |
| 16 | `deploy_prod` declares `github: none` | charter rejected, exit 2 | `not-applicable` |
| 17 | `* @alice`, Alice lacks write access | pass | `drift`: GitHub ignores Alice, so the path has no effective owner |
| 18 | Stale-review dismissal off | pass | `drift`: later commits can merge on an earlier approval |
| 19 | Ruleset-only branch, bypass list read and empty | pass | `verified` |

The Today column assumes the same charter without the new `github` keys, since
today's schema rejects them (row 16 shows that case).

### This repository's own charter

`governance/charter.yaml` has two gated actions. `A5_merge_to_main` names the
`reviewer` role as approver, whose only member is an agent, and has no `github` key,
so it is `incomplete` for both reasons (`no-human-approver`, `no-github-mapping`). `A7_publish_release` has no `github` key, so it is `incomplete`
(`no-github-mapping`); publishing to PyPI is not a GitHub branch change, so the right
fix is `github: none`. With no other changes, this repo's own verify run exits `2`; the `charter.yml`
workflow runs verify with `continue-on-error`, so CI shows that as a warning, not a
failure.
The maintainer's break-glass role (`orchestrator`) would be listed with the D4 caveat
if it appears as a bypass actor.

## 8. Out of scope

Runtime interception, deployment and spending enforcement, per-pull-request review
history, GitLab, automatic remediation, and a GitHub App.

## 9. Decisions (settled by the maintainer)

- **D1 — Who must approve:** the designated approver only (`gate.approver`).
- **D2 — Exit code for `incomplete`:** `2`, with `--allow-incomplete` to exit `0`
  instead.
- **D3 — Which actions verify judges:** actions with `github.paths`. An action with
  `github: none` is `not-applicable`. An action with no `github` key is `incomplete`.
  The first draft fell back to judging unmapped actions over `*`; the review showed
  that gives deploy, release and spending gates an implied branch-protection guarantee,
  so the fallback was dropped.
- **D4 — Break-glass bypass:** a bypass actor who holds the gate's break-glass role is
  allowed, listed, and flagged with the caveat in §4.
