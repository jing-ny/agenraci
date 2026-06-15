# TODOS

Deferred work, with enough context to pick up cold. Roadmap-level scope lives in
the README "Roadmap" section and in GitHub issues; this file tracks deferred
items that came out of planning/review sessions.

## Deferred from the v0.2 scope decision ([#58](https://github.com/jing-ny/agenraci/issues/58))

The v0.2 "GitHub enforcement loop" deliberately ships a **read-only** core
(`agenraci verify --target github` + applyable `compile` artifacts + a verify
Action). These were considered and deferred to keep that core stable first.

### Drift auto-remediation (write-path)
- **What:** When `verify` finds drift, optionally open a PR (or emit `gh api`
  commands) to bring the live repo back into compliance with the charter.
- **Why:** Turns detection into a one-click fix — "detect → remediate" closes the
  loop further and demos well.
- **Why deferred:** Write-path against the GitHub API is a larger risk surface than
  the read-only verifier, and it blurs the honest-scope line. Add it only once the
  read-only loop is stable and trusted.
- **Effort:** M (human ~1wk / CC ~3-4h). **Priority:** P2. **Depends on:** v0.2 verifier.

### Multi-repo / org-wide governance sweep
- **What:** Run `verify` across many repos (an org-wide audit) and emit one
  "which repos have drifted" report.
- **Why:** The killer scenario for governance/compliance readers — they own
  "who's accountable across the whole org," not a single repo. Strongest pull for
  the non-engineer audience.
- **Why deferred:** Depends on a stable single-repo verifier first; adds API
  rate-limit, pagination, and permission complexity that would slow the core.
- **Effort:** M (human ~1wk / CC ~2-3h). **Priority:** P2 (target v0.2.1). **Depends on:** v0.2 verifier.

### GitLab parity
- **What:** A `gitlab` target + verifier covering push rules and merge-request
  approval rules, mirroring the GitHub loop.
- **Why:** Not everyone is on GitHub; parity broadens reach.
- **Why deferred:** Revisit once the GitHub loop has shipped and the comparison
  model has proven out on one platform.
- **Effort:** M-L. **Priority:** P3. **Depends on:** v0.2 GitHub loop.

### GitHub App / live-API auth UX
- **What:** A smoother auth story for reading live repo settings (beyond a CI
  runner token), e.g. a GitHub App.
- **Why:** Lowers friction for local/interactive `verify` runs.
- **Why deferred:** The Action runner token is enough for the v0.2 CI path; the
  nicer auth UX is not on the critical path.
- **Effort:** M. **Priority:** P3. **Depends on:** v0.2 verifier.
