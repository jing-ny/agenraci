# From a running agent team to a charter

> You already have agents doing work — a LangGraph supervisor routing to workers,
> a CrewAI crew, a Claude Code subagent setup, a couple of cron bots. What you
> probably *don't* have is one written answer to: when one of them acts and no
> human pressed the button, **who is accountable, what was it allowed to touch,
> and who breaks a tie?** This guide turns what you already run into an AgenRACI
> charter in about 20 minutes. No runtime changes — a charter *describes and
> checks* your team; it doesn't intercept anything.

Start from a blank charter:

```bash
pip install agenraci
agenraci init charter.yaml
```

Then work through the five questions below, validating as you go
(`agenraci validate charter.yaml`).

---

## 1. Who are the actors? → `roles` and `members`

List every distinct actor in your system: each human, and each agent. Then group
them by **authority**, not by name — two researcher agents with identical
permissions are *one role*, while a supervisor and a worker are two.

A LangGraph supervisor graph usually maps cleanly:

| In your graph | In the charter |
| --- | --- |
| the supervisor / router node | a role like `orchestrator` |
| each distinct worker node (researcher, coder, …) | one role each |
| the human in a `interrupt()` / approval step | a human member |

```yaml
roles: [orchestrator, researcher, coder, reviewer]

members:
  - { name: alice,      type: human, role: orchestrator }
  - { name: research_agent, type: agent, role: researcher, model: claude-sonnet-4-6 }
  - { name: coding_agent,   type: agent, role: coder,      model: claude-opus-4-8 }
  - { name: review_agent,   type: agent, role: reviewer,   model: claude-opus-4-8 }
```

> **Rule of thumb:** if you'd give two agents the same answer to "what are they
> allowed to do and who do they answer to," they share a role.

## 2. What may each actor touch? → `capabilities`

For each role, list the capabilities it is **granted** and any it is explicitly
**denied**. Capabilities are just tokens you choose — they usually mirror the
*tools* each node can call (the tool list you bind to a LangGraph node, the
allowed tools of a Claude subagent).

```yaml
capabilities:
  coder:    { grant: [edit_code, merge] }
  reviewer: { grant: [block_merge], deny: [edit_code, merge] }
  researcher: { grant: [web_search] }
```

A `deny` is a statement of intent: "the reviewer must never edit code." The
checker (rule R3) will flag a charter that both grants and denies the same
capability to one role, and R2 flags a capability you grant but no action ever
uses (dead authority).

## 3. What *types* of action happen? → `actions`

This is the heart of it. Enumerate action **types**, not individual tasks —
"ship code," not "fix bug #42." For each, name the single **accountable** owner
(rule R1 enforces exactly one), who's responsible, consulted, informed, and the
capabilities it touches.

```yaml
actions:
  ship_code:
    responsible: coder
    accountable: coder
    consulted:   [reviewer]
    capabilities: [edit_code]
```

If you can't name a single accountable owner for an action type, that's not a
charter problem — it's a real gap in your team that was invisible until now.

## 4. Who approves, and what happens if they don't? → `gate`

Agents act on their own schedule, so the dangerous question is: **what happens
when the human approver is asleep?** A `gate` answers it explicitly. This is the
charter-level twin of a LangGraph `interrupt()` or a HumanLayer approval step.

```yaml
  merge_to_main:
    responsible: coder
    accountable: reviewer            # the reviewer outranks the coder here
    capabilities: [merge]
    gate:
      approver: reviewer
      on_timeout: block              # never auto-merge; the opposite would need
                                     # the action marked low-risk (rule R5)
      break_glass: { who: orchestrator, condition: maintainer_override, requires_after_review: true }
```

Rule R4 fails any gate with no defined timeout behavior (no silent deadlock), and
R5 only lets `on_timeout: proceed_if_low_risk` stand when the action is actually
marked low-risk.

## 5. Who *can't* act but must be heard? → `suggestion_route`

Often an actor is deliberately denied a capability but still needs a way to push
back — a reviewer who can't merge but can demand changes, a QA agent who can't
fix but must report a defect. A `suggestion_route` records that path so the
denial doesn't become a dead end.

```yaml
  independent_review:
    responsible: reviewer
    accountable: reviewer
    capabilities: [block_merge]
    suggestion_route: { from: reviewer, to: coder, as: change_request }
```

---

## A complete worked example: this repo governs itself

AgenRACI develops itself under a charter, and its five agents in
[`.claude/agents/`](../../.claude/agents) map 1:1 to the members in
[`governance/charter.yaml`](../../governance/charter.yaml):

| Agent file | Role | Accountable for | Notably *can't* |
| --- | --- | --- | --- |
| `orchestrator.md` | orchestrator | set roadmap, publish release | edit code |
| `coder.md` | coder | implement a change | approve its own merge |
| `qa.md` | qa | verify a change | edit or merge code |
| `reviewer.md` | reviewer | **the merge to main** | edit, merge, or publish |
| `writer.md` | writer | update docs | touch the package |

The interesting accountability call: in `A5_merge_to_main` the **coder** is
responsible (does the merge) but the **reviewer** is accountable — so a change
author never signs off on their own merge, and the gate blocks on timeout rather
than letting an unreviewed change slip through. That single rule is the whole
reason the charter exists, made machine-checkable.

Read the full file — it's only ~110 lines — then run:

```bash
agenraci validate governance/charter.yaml
```

and you'll see all six rules pass. Copy it, rename the roles to your team's, and
you have a starting point.

---

## Where this stops (honest scope)

A charter **declares and checks** who is accountable for what. It does **not**
intercept your agents' tool calls or enforce approvals at runtime — LangGraph,
CrewAI, and friends run the agents; HumanLayer adds the human approval step.
AgenRACI is the framework-agnostic file one level up, so the accountability map
survives when you swap runtimes. Compiling a charter into live gates is roadmap,
not a current claim.
