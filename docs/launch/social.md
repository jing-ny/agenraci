# Social copy — launch day

> Stagger these after the Show HN post lands. Keep every claim honest: v0.1 writes and
> checks a charter; it does not enforce approvals at runtime. Link the repo, the essay
> (`docs/why-agenraci.md`), or the playground depending on the audience.

---

## X / Twitter thread

**1/**
An AI agent on your team just shipped code, sent a message, or spent money — and no
human pressed the button.

Who's accountable?

On a lot of teams that answer isn't written down anywhere. So I built AgenRACI. 🧵

**2/**
RACI — Responsible, Accountable, Consulted, Informed — is the old chart for "who owns
what work."

It has no native slot for a machine actor, the permissions it holds, an approval
timeout, or an escalation path — exactly what you need once an agent acts on its own
schedule and still needs one named accountable owner.

**3/**
AgenRACI is one plain-language file — a charter — that says, for each *type* of action:

• who does it
• who's the single accountable owner
• who's consulted / informed
• what it's allowed to touch
• what approval is needed
• what the charter says to do if the approver never responds

**4/**
It keeps three questions separate that teams usually tangle:

• Function — what do you *do*?
• Permission — what may you *touch*?
• Authority — whose call *wins*?

A domain expert can own a decision, be denied edit access, and still be the required
sign-off on a merge. Three axes, not one.

**5/**
A checker reads the charter and flags the structural gaps that bite later — returning
nonzero so you can gate CI on it:

• nobody accountable
• two roles both claiming one action
• a permission granted but never used
• an approval path with no timeout
• an escalation chain that loops forever

**6/**
Honest scope: v0.1 **writes and checks** the charter. It does NOT enforce approvals at
runtime — LangGraph and CrewAI run agents; HumanLayer adds human approval steps.

AgenRACI sits one level up: the framework-agnostic file that declares *who's allowed to
do what, and who breaks a tie* — independent of your runtime.

**7/**
`pip install agenraci`, or try the browser playground (runs the real checker via Pyodide,
no install).

Open source, MIT. The project even governs itself with its own charter.

Feedback very welcome 👇
https://github.com/jing-ny/agenraci

---

## LinkedIn (governance angle)

Most AI-accountability conversations happen at the governance level — ISO/IEC 42001, the
EU AI Act, organizational responsibility for "the AI system as a whole."

There's a level below that, and it's where things actually break: the operating level.
What happens when a *specific* agent takes a *specific* action with a *specific*
permission — and no human triggered it?

AgenRACI is a small open-source tool for that level. You write one human-readable file —
a charter — that names, for each type of action: the single accountable owner, the
permissions it touches, who must be consulted, the approval path, and the declared
fallback when that approval times out. A checker verifies the model is internally
consistent and returns nonzero when it isn't, so teams can gate it in CI.

It doesn't replace ISO/IEC 42001 or the EU AI Act — it gives teams a concrete, reviewable
artifact that can support the accountability and documentation those frameworks call for:
a machine-checkable declaration of who owns each class of agent action.

v0.1 writes and checks the charter today; runtime enforcement is on the roadmap, not a
current claim. MIT-licensed.

→ https://github.com/jing-ny/agenraci

---

## Reddit

**Candidate subreddits** (read each one's self-promotion rules first; space them out,
don't blast all at once): r/programming, r/ExperiencedDevs, r/devops, r/LLMDevs,
r/AI_Agents. Lead with the problem, not the pitch — Reddit punishes marketing tone.

**Title:**
AgenRACI: a machine-checkable "who's accountable when an AI agent acts" charter for your repo

**Body:**
I kept hitting the same question on teams that use AI agents: when an agent ships code,
replies to a customer, or spends money on its own, who's actually accountable? Classic
RACI charts have no slot for a machine actor, its permissions, an approval timeout, or an
escalation path, so they don't quite fit.

AgenRACI is an open-source attempt at the operating-level answer. You write one file that
declares, per *type* of action: who does it, the single accountable owner, who's
consulted/informed, what permissions it touches, the approval path, and the declared
timeout + break-glass behavior. A checker flags structural gaps (no owner, two owners,
dead permissions, approval paths with no timeout, escalation loops) and returns nonzero,
so you can gate it in CI.

To be upfront about scope: it **writes and checks** the charter — it does not intercept
tool calls or enforce approvals at runtime (LangGraph/CrewAI run agents; HumanLayer adds
human approval steps). It's the framework-independent declaration layer those runtimes
could consume later.

There's a browser playground that runs the real checker (no install), worked examples,
and the project governs itself with its own charter. I'd genuinely like to hear where the
model is wrong or where the rules don't match how your team breaks.

Repo: https://github.com/jing-ny/agenraci
