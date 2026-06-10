# Show HN post

> Draft for launch day. Keep it honest — v0.1 *writes and checks* a charter; it does
> not enforce anything at runtime. Post Tue–Thu morning ET. Author should be in the
> comments for the first 6–8 hours.

## Title

Show HN: AgenRACI – a machine-checkable RACI for human + AI-agent teams

<!-- Alternates, pick one:
- Show HN: AgenRACI – who's accountable when an AI agent acts on your team?
- Show HN: AgenRACI – a linter for "who's allowed to do what" on agent teams
-->

## URL

https://github.com/jing-ny/agenraci

## Body

When an AI agent on your team ships code, sends a message, or spends money — and no
human pressed the button — who is accountable? On a lot of teams that answer isn't
written down anywhere; it's scattered across code, access controls, and tribal knowledge.

RACI (Responsible / Accountable / Consulted / Informed) is the old chart teams used to
answer this. Classic RACI charts have no native slot for a machine actor, the permissions
it holds, an approval timeout, or an escalation path — the things that matter once an
agent can act on its own schedule.

AgenRACI is one human-readable file — a *charter* (YAML) — that states, for each *type*
of action: who does it, the single accountable owner, who's consulted/informed, what
permissions it touches, what approval is required, and what the charter says to do if the
approver never responds. A checker reads the charter and flags the structural gaps that
bite later — returning nonzero so you can gate CI on it: no accountable owner, two roles
both claiming one action, a permission granted but never used, an approval path with no
timeout, or an escalation chain that loops forever.

Honest scope: v0.1 **writes and checks** the charter. It does **not** intercept tool
calls or enforce approvals at runtime — tools like LangGraph and CrewAI run agents, and
HumanLayer adds human approval steps. AgenRACI sits one level up: the
framework-agnostic file that declares *who's allowed to do what, and who breaks a tie*,
independent of which runtime you use. A live HumanLayer connector is the next milestone,
not a current claim.

You can `pip install agenraci`, run `agenraci init` for a starter charter, and
`agenraci validate` it. There's a browser playground that runs the real checker via
Pyodide (no install), worked examples (including an all-agent team), and the project
governs itself with its own charter in `governance/`.

I'd love feedback on the model — especially the three-axis split (function vs. permission
vs. authority) and whether the checker rules match how your team actually breaks.
