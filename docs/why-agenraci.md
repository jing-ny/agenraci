# Why AgenRACI

*An AI agent on your team just shipped code, sent a message, or spent money — and no human pressed the button. Who owns the outcome?*

## The accountability gap

Software teams used to have a useful property: behind every meaningful action, there was a person who chose to take it.

A deploy happened because an engineer ran it.
A refund went out because support approved it.
A vendor payment was made because finance released it.

When something went wrong, the first question was simple:

*Who did this?*

Usually, there was a name.

AI agents weaken that assumption. An agent can now open a pull request, reply to a customer, reconcile an invoice, escalate an incident, or trigger a workflow on its own schedule. No human may be present at the moment the action happens. That is often the point of using agents.

The work still gets done. But the ownership chain becomes ambiguous.

The agent may be the immediate **doer**.
The tool may hold the **permission**.
The team may bear the **consequence**.
But the human **owner** may never have been named.

That is the accountability gap.

It is invisible until something fails: a bad merge, a wrong customer response, an unauthorized spend, a missed escalation, or an incident where everyone agrees the agent acted — but nobody can say who was accountable for allowing, approving, blocking, or overriding that action.

## Why classic RACI is not enough

For decades, teams have used **RACI** to clarify ownership:

* **Responsible**: who does the work
* **Accountable**: who owns the outcome
* **Consulted**: who gives input
* **Informed**: who is kept aware

RACI is useful because it forces a hard rule: for each activity, there should be one clear accountable owner.

But classic RACI was built for human organizational workflows. It becomes ambiguous when the actor is no longer just a person, but an agent with delegated permissions and autonomous execution loops.

Agentic AI breaks the model in two practical ways.

First, the **doer may not be human**. An agent can be responsible for an action in the operational sense: it writes the code, drafts the message, files the ticket, updates the system, or calls the API. Classic RACI has no native way to describe a non-human actor with real permissions, real limits, and real failure modes.

Second, the **trigger may not be human**. The action may originate from the agent's own loop: a schedule, a monitor, an event, a plan, or a tool call. No one "pressed the button" at the moment of execution.

This creates a predictable failure pattern. Teams either:

1. skip the accountability map entirely, and discover the gap during an incident; or
2. create a slide-deck RACI that humans can read, but agents and CI systems cannot check.

Neither is enough once agents can act at 3 a.m.

## What AgenRACI is

AgenRACI is a machine-checkable accountability charter for teams that use both humans and AI agents.

It is one plain-language file that answers three separate questions for each class of action:

| Question       | What it asks                   | Example                                     |
| -------------- | ------------------------------ | ------------------------------------------- |
| **Function**   | What role do you play?         | Orchestrate, Build, Advise, Review, Watch   |
| **Permission** | What are you allowed to touch? | `edit_code`, `merge`, `deploy`, `spend`     |
| **Authority**  | Whose call wins?               | The single accountable role for that action |

The separation matters.

A domain expert may be accountable for whether a fact is correct, denied permission to edit code, and still able to block a merge on correctness grounds.

Those are three different axes:

* accountability is not permission;
* permission is not authority;
* authority is not the same as doing the work.

AgenRACI makes those distinctions explicit.

## What a charter contains

An AgenRACI charter defines a small set of roles once, such as:

* orchestrator
* engineer
* domain expert
* reviewer
* monitor

Then it appoints humans and agents to those roles.

Adding an agent should be a one-line appointment, not a new governance model.

For each type of action, the charter names:

* the action being governed;
* the role responsible for doing or initiating it;
* exactly one accountable role;
* who must be consulted;
* who must be informed;
* which permissions the action touches;
* what approval is required, if any;
* what happens if the approver is unavailable;
* whether a `break_glass` emergency path exists;
* what must be logged.

This avoids two common failure modes:

1. **silent deadlock** — an agent waits forever because approval rules have no timeout;
2. **silent escalation** — an agent treats "low risk" as a backdoor to act without a named owner.

Every action type must have an owner. Every approval path must say what happens when no one responds. Every emergency path must be explicit.

## Why this should be a file, not a diagram

A diagram can explain accountability.
A charter can be checked.

AgenRACI includes a checker that reads the charter and flags structural gaps, such as:

* an action with no accountable owner;
* an action with more than one accountable owner;
* a permission that is granted but never used;
* an approval path with no timeout behavior;
* a break-glass path with no named accountable role.

The point is not to create another policy document. The point is to create an artifact that can live in the repo, be reviewed in pull requests, and fail CI when the accountability model is internally inconsistent.

If agents are acting through code, the rules that govern them should be reviewable like code.

## What AgenRACI does today

Today, AgenRACI writes and checks the charter.

It provides:

* a clear charter format;
* validation rules;
* worked examples;
* a blank template;
* a checker that flags common accountability gaps.

That is the current product: a machine-checkable accountability map for mixed human + agent teams.

## What AgenRACI does not do yet

AgenRACI does not currently run your agents.

It does not intercept tool calls, enforce approvals at runtime, pause workflows, or decide whether a specific action should proceed in the moment.

Tools such as LangGraph and CrewAI can orchestrate agents, and HumanLayer can add human approval gates. AgenRACI sits one level above that. It answers the operating question those systems still need from the team:

*For this action, on this team, who is allowed to do what — and who owns the outcome?*

Runtime enforcement is the roadmap, not a current claim.

The next milestone is to compile an AgenRACI charter into live approval gates, starting with a HumanLayer connector. A later milestone is a team-wide authority graph that can detect impossible loops, circular escalation, and conflicting override rules.

## How AgenRACI relates to AI governance frameworks

There are two levels of AI accountability.

The first is the **governance level**: policies, management systems, risk classification, compliance obligations, audit evidence, and organizational responsibility.

That is the level addressed by frameworks and regulations such as ISO/IEC 42001 and the EU AI Act.

The second is the **operating level**: the day-to-day question of what happens when a specific agent takes a specific action with a specific permission inside a specific team.

AgenRACI lives at the operating level.

It does not replace governance frameworks. It gives teams a concrete artifact that can support what those frameworks call for but do not prescribe in detail: a machine-checkable declaration of who owns each class of agent action, what the agent may touch, who must be consulted, and what should happen when normal approval paths fail.

In an audit or incident review, AgenRACI should let a team point to a file and say:

*This is the charter that defined how that class of action was meant to be governed. It named the accountable owner, the agent's permissions, the required approval path, the timeout behavior, and the emergency override rule. The checker verified that the model was internally consistent.*

Governance frameworks tell organizations they need accountability.

AgenRACI is one practical way to make that accountability explicit, reviewable, and machine-checkable at the level where agents actually act.

## Get started

AgenRACI is open source under the MIT License.

Start with:

* [README](../README.md)
* the worked example in [`examples/sprout/`](../examples/sprout/)
* the format details in [SPEC.md](../SPEC.md)
