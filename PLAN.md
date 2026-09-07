# AgenRACI — next-round plan

Drafted 2026-09-07. Status: planned; implementation has not started.
The [original launch plan](docs/planning/launch-plan-v0.1.md) is preserved as a
historical snapshot; local links have been adjusted for its archive location.

## Objective and investment limit

Determine whether AgenRACI reliably identifies meaningful gaps between intended human
approval and GitHub configuration, and whether maintainers keep using it. Focus on
changes entering a protected branch, including agent-created changes.

Use a four-week window starting when implementation and recruitment begin, with roughly
five focused maintainer engineering days. This is an investment cap, not a delivery
estimate or a deadline for volunteers. Unsupported guarantees must remain explicitly
incomplete. Choose a release version after assessing compatibility impact.

## Evidence and uncertainty

- Local assessment: 98 tests passed; overridden and optional CODEOWNERS both produced
  false passes for a designated-owner approval requirement.
- The comparison uses accountable humans, not the separately declared gate approver.
  Path precedence and bypass permissions are not represented.
- Auto-merge is treated as incompatible with blocking gates, although GitHub auto-merge
  waits for required reviews and checks.
- Maintainer-reported preceding 14-day traffic: 16 clones, 10 unique cloners, three views,
  three unique visitors. These and a positive Reddit comment do not establish adoption.
- Org-wide scanning shipped in v0.2.1; it is not a new deliverable.

## Sequence and acceptance criteria

### 1. Define the verification contract first

Distinguish accountable owner, designated approver, action/file scope, and observed
controls. Define verified, drift, and incomplete coverage with concrete examples.
Cover mixed reports, offline snapshots, live permission failures, CLI exit codes,
JSON, the Action, and org summaries. Preserve the existing 0/1/2 distinction or document
an explicit compatibility migration. A charter identity is not proof of a GitHub
identity or its permissions. Spending, deployment, and runtime gates must not acquire
an implied branch-protection guarantee.

Done when reviewers can classify supported, contradicted, and unknown cases, including
accountable and approver roles that differ. Resolve scope before implementation.

### 2. Correctness work — week one, bounded by the contract

- Respect CODEOWNERS file scope, last-match precedence, and ownerless overrides.
- Check required approvers; more eligible owners do not necessarily mean stronger policy.
- Establish relevant bypass behavior, or explicitly report incomplete evidence.
- Correct auto-merge handling in verifier, compiler guidance, tests, and docs.
- Keep generated configuration honest about guarantees it cannot express.

The auto-merge correction can start independently. Approval/scope and evidence-result
changes depend on the contract; fixture preparation can start earlier. If comprehensive
support exceeds the effort cap, conservatively report unsupported cases.

Done when regression tests cover the two reproduced false passes, differing roles,
unknown evidence, and safe auto-merge, alongside genuinely protected passing controls.
Run existing tests, validate project/example charters, and check CLI/Action/org reports.
Before release, exercise a maintainer-controlled test repository with deliberate drift
and insufficient permissions. Document this separately from offline tests. The planning
update does not change live repository settings.

### 3. Demonstration and onboarding — week two

Lead with one minimal policy and the CODEOWNERS override gap: intended approval,
observed settings, finding, and reviewed correction. Include runnable offline fixtures,
authentication requirements, and accurate exit behavior. Distinguish snapshots from
live evidence; future output must not be presented as shipped behavior.

Help trial users express one existing rule in a minimal charter. Do not build a
charter-free scanner before learning whether authoring is actually the obstacle.

### 4. Three independent maintainer trials — weeks two through four

The maintainer recruits roughly six to ten relevant contacts to obtain three completed
trials with teams that already require human review and use coding agents. Outreach is
not automatic. Contributor interest does not count as adoption without actual use.

Record intended approval, setup time, authentication friction, unsupported cases, useful
findings, false positives, recurring-check installation, and retention 7–14 days later.
Use the [trial worksheet](docs/planning/trial-worksheet.md); no telemetry service is needed.
Keep completed private worksheets outside this public repository. Share participant
identities or repository details only with their agreement.

### 5. End-of-cycle investment decision

| Evidence | Decision |
| --- | --- |
| Two independent maintainers retain recurring checks; one reports a meaningful finding or concrete ongoing value | Fund one narrow iteration around their needs |
| Repeated setup blocker prevents interested maintainers from trying it | Consider one bounded onboarding fix |
| Completed trials find little value and nobody retains the check | Maintain the small tool; pause expansion |
| Too few relevant people complete a trial | Demand remains unresolved; pause features and reassess recruitment |

These are practical rules, not statistical thresholds. Stars, clones, comments, and PRs
cannot substitute for continued use. Late trials receive the full follow-up interval;
an unobserved retention outcome is unknown, not success or failure.

## Contributor work items

| Issue | Dependency / starting point |
| --- | --- |
| [#78: Define the GitHub verification contract and incomplete-coverage behavior](https://github.com/jing-ny/agenraci/issues/78) | Start first; maintainer scope decision |
| [#79: Fix GitHub approval verification for CODEOWNERS precedence and designated approvers](https://github.com/jing-ny/agenraci/issues/79) | Depends on #78; fixtures can start now |
| [#80: Represent bypass and missing evidence without reporting complete verification](https://github.com/jing-ny/agenraci/issues/80) | Depends on #78; coordinate with #79 |
| [#81: Fix auto-merge being treated as bypassing a blocking approval gate](https://github.com/jing-ny/agenraci/issues/81) | Independent smaller fix |
| [#82: Add a reproducible approval-gap walkthrough and verify the release end to end](https://github.com/jing-ny/agenraci/issues/82) | Draft now; final output after #79–#81 |
| [#83: Validate usefulness with three maintainer trials and record an investment decision](https://github.com/jing-ny/agenraci/issues/83) | Maintainer-led; corrected release needed for retention evaluation |

Comment on an issue with your intended scope before substantial work to avoid duplication.
Issues are unassigned unless someone volunteers. Maintainer owns contract decisions,
recruitment, and the investment decision; contributors can own focused code/docs PRs.
Follow the project charter: independent QA and review before merge; maintainer approval
before release. No implementation, merge, release, or outreach is implied by this plan.

## Deferred scope

Runtime connectors, GitLab, dashboards, richer authority graphs, automatic remediation,
a charter-free scanner, and a GitHub App. Revisit authentication improvements only if
trials reveal a repeated blocker. See [TODOS.md](TODOS.md). No v0.3–v0.5 dates are promised.
