# Hello-world — the minimal on-ramp

**Hello-world** is the smallest useful charter: one human and one agent.
It is intentionally tiny, but it still has human-owned scope control and a clean
handoff to agent execution.

Validate it:

```bash
nextraci validate examples/hello-world/charter.yaml
```

## The team: 1 human + 1 agent

| Member | Type | Role | Notes |
|--------|------|------|-------|
| **you** | human | owner | defines the request and accepts it |
| **agent** | agent | builder | implements the work |

## The actions

| # | Action type | Owner | Notes |
|---|-------------|:-----:|-------|
| A1 | Log request | owner | Human owns request intake |
| A2 | Fix request | builder | Agent executes after scope is set |
