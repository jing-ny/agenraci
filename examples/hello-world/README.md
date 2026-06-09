# hello-world — the smallest meaningful charter

One human, one AI agent, two actions. This is the 30-second introduction to
AgenRACI; for the full picture see [`examples/blog/`](../blog/) (one step up) or
the deep dives in [`examples/sprout/`](../sprout/) and [`examples/relay/`](../relay/).

```bash
agenraci validate examples/hello-world/charter.yaml
```

## The team: 1 human, 1 agent

| Member | Type | Role | Does |
|--------|------|------|------|
| **you** | human | maintainer | own the project; put code on main |
| Ada | agent | assistant | write code changes |

## The one idea

| Action | Responsible (does it) | Accountable (owns it) |
|--------|:---------------------:|:---------------------:|
| `write_code` | Ada (agent) | **you** (human) |
| `merge_code` | you | **you** |

The agent **does** the work, but a human still **answers** for it. *Responsible*
and *Accountable* are different questions — RACI has always kept them apart, and
AgenRACI is what lets an AI agent hold one of them while a human holds the other.

That's the whole charter. No gates, no escalation — those appear the moment an
action needs a sign-off, which is what the [blog example](../blog/) adds next.
