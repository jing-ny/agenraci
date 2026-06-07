# Agent-review gate — a tiny approval flow

**Agent-review-gate** shows the smallest real approval loop in one place.
One agent implements the work, one agent reviews, and one human owner coordinates
and can trigger a break-glass path if the review times out.

Validate it:

```bash
nextraci validate examples/agent-review-gate/charter.yaml
```

## The team: 1 human + 2 agents

| Member | Type | Role | Notes |
|--------|------|------|-------|
| **you** | human | owner | defines scope, owns release |
| **agent** | agent | builder | writes code |
| **auditor** | agent | reviewer | holds merge authority |

## The actions

| # | Action type | Accountable | Notes |
|---|-------------|:----------:|-------|
| A1 | Plan work | owner | Owner defines intended change |
| A2 | Implement change | builder | Agent executes the implementation |
| A3 | Review and merge | reviewer | Reviewer holds the approval gate |
| A4 | Release notes | owner | Owner sends completion note |
