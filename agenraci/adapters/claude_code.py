"""Claude Code adapter — compile a charter into ``.claude/agents/`` files.

This target is **real**: it emits one agent definition per *agent member* of the
charter (the files Claude Code actually reads), plus a governance snippet for
``CLAUDE.md``. That makes the charter *operative* for a Claude Code team — both
humans on a two-person project compile the same charter and their agents carry
the same role boundaries — while staying honest: we generate static config the
runtime already consults; nothing is intercepted at runtime.

The emitted prompts are deliberately skeletons. Enrich them with project detail,
but when the charter changes, regenerate — the charter is the source of truth.

Output format: one string containing multiple documents separated by
``--- FILE: <relative path> ---`` marker lines; ``agenraci compile --out-dir``
splits and writes them.
"""

from __future__ import annotations

from ..schema import ANY, Charter

FILE_MARKER = "--- FILE: {path} ---"

# Claude Code agent frontmatter accepts these model tokens; map a member's
# declared model id (e.g. "claude-opus-4-8") onto one when it's unambiguous.
_MODEL_TOKENS = ("opus", "sonnet", "haiku")


def _model_token(model_id: str | None) -> str | None:
    if not model_id:
        return None
    lowered = model_id.lower()
    for token in _MODEL_TOKENS:
        if token in lowered:
            return token
    return None


def _join(names: list[str]) -> str:
    return ", ".join(names)


def _gate_summary(action_name: str, action, charter: Charter) -> list[str]:
    """Lines describing one gated action, reused by agent files and CLAUDE.md."""
    gate = action.gate
    lines = [f"- **{action_name}** — required approver: **{gate.approver}**."]
    if gate.on_timeout == "block":
        lines.append("  On approver timeout: **block** (never proceeds unreviewed).")
    elif gate.is_proceed_if_low_risk:
        lines.append("  On approver timeout: may proceed — the charter marks this "
                     "action low-risk.")
    elif gate.escalate_target:
        lines.append(f"  On approver timeout: escalate the decision to "
                     f"**{gate.escalate_target}**.")
    if gate.break_glass is not None:
        bg = gate.break_glass
        after = ", with mandatory after-the-fact review" if bg.requires_after_review else ""
        lines.append(f"  Break-glass: **{bg.who}** may override when "
                     f"*{bg.condition}*{after}.")
    return lines


def _agent_file(member, charter: Charter) -> str:
    role = member.role
    actions = charter.actions

    does_and_owns: list[str] = []
    does_for_other: list[tuple[str, str]] = []       # (action, accountable)
    owns_done_by_other: list[tuple[str, str]] = []   # (action, responsible)
    consulted_on: list[str] = []
    informed_of: list[str] = []
    approves: list[str] = []
    routes_out: list[tuple[str, str, str]] = []      # (as, to, action)
    routes_in: list[tuple[str, str, str]] = []       # (as, from, action)

    for name, a in actions.items():
        accountable = a.accountable[0] if a.accountable else None
        if a.responsible == role and accountable == role:
            does_and_owns.append(name)
        elif a.responsible == role:
            does_for_other.append((name, accountable or "?"))
        elif accountable == role:
            resp = "any member" if a.responsible == ANY else a.responsible
            owns_done_by_other.append((name, resp))
        if role in a.consulted:
            consulted_on.append(name)
        if role in a.informed:
            informed_of.append(name)
        if a.gate is not None and a.gate.approver == role:
            approves.append(name)
        if a.suggestion_route is not None:
            r = a.suggestion_route
            if r.from_ == role:
                routes_out.append((r.as_, r.to, name))
            if r.to == role:
                routes_in.append((r.as_, r.from_, name))

    caps = charter.capabilities.get(role)
    grants = list(caps.grant) if caps else []
    denies = list(caps.deny) if caps else []

    humans = [m for m in charter.members if m.type == "human"]

    # --- frontmatter ---------------------------------------------------------
    desc_bits = []
    if does_and_owns or does_for_other:
        desc_bits.append("Responsible for: "
                         + _join(does_and_owns + [n for n, _ in does_for_other]) + ".")
    if owns_done_by_other:
        desc_bits.append("Accountable for: "
                         + _join([n for n, _ in owns_done_by_other]) + ".")
    if approves:
        desc_bits.append("Approves: " + _join(approves) + ".")
    if denies:
        desc_bits.append("Never: " + _join(denies) + ".")
    description = (f"{role} role for {charter.project}, generated from its "
                   f"AgenRACI charter. " + " ".join(desc_bits)).strip()

    fm = ["---", f"name: {member.name}", f"description: {description}"]
    token = _model_token(member.model)
    if token:
        fm.append(f"model: {token}")
    fm.append("---")

    # --- body ----------------------------------------------------------------
    b: list[str] = []
    b.append(f"<!-- Generated by `agenraci compile --target claude` from the "
             f"'{charter.project}' charter. Enrich this prompt with project "
             f"detail, but the charter stays the source of truth — when it "
             f"changes, regenerate and re-apply your edits. -->")
    b.append("")
    b.append(f"You are **{member.name}**, appointed to the **{role}** role in "
             f"**{charter.project}**'s operating charter.")
    b.append("")
    b.append("## Your actions")
    b.append("")
    for n in does_and_owns:
        b.append(f"- **{n}** — you do this, and you own the outcome.")
    for n, acct in does_for_other:
        b.append(f"- **{n}** — you do the work; **{acct}** is accountable and "
                 f"signs off. Don't approve your own work here.")
    for n, resp in owns_done_by_other:
        b.append(f"- **{n}** — {resp} does the work; **you are accountable** "
                 f"for the outcome.")
    if not (does_and_owns or does_for_other or owns_done_by_other):
        b.append("- (No action names this role as responsible or accountable.)")
    if consulted_on:
        b.append(f"- You are **consulted before**: {_join(consulted_on)}.")
    if informed_of:
        b.append(f"- You are **informed after**: {_join(informed_of)}.")
    b.append("")
    b.append("## Permissions (from the charter)")
    b.append("")
    if grants:
        b.append("- You may use: " + ", ".join(f"`{c}`" for c in grants) + ".")
    for c in denies:
        b.append(f"- **Never** exercise `{c}` — the charter denies it to your "
                 f"role. This denial is the point of your role, not an oversight.")
    if denies:
        b.append("- Operator note: restrict this agent's `tools:` frontmatter to "
                 "match (a role denied `edit_code` should not be handed Edit/Write).")
    if not grants and not denies:
        b.append("- (No capabilities declared for this role.)")
    if approves:
        b.append("")
        b.append("## Approvals you grant")
        b.append("")
        for n in approves:
            b.extend(_gate_summary(n, actions[n], charter))
    if routes_out or routes_in:
        b.append("")
        b.append("## When blocked, or when work arrives")
        b.append("")
        for as_, to, n in routes_out:
            b.append(f"- If you disagree or are blocked on **{n}**: file a "
                     f"**{as_}** to **{to}** — never silently drop it, never "
                     f"act past your denial.")
        for as_, frm, n in routes_in:
            b.append(f"- Expect **{as_}** items from **{frm}** (re: {n}) — "
                     f"clear them before proceeding.")
    if humans:
        b.append("")
        b.append("## Humans")
        b.append("")
        for h in humans:
            b.append(f"- **{h.name}** (human, {h.role} role).")
        b.append("- Anything beyond the charter's rules escalates to a human, "
                 "not to another agent.")

    return "\n".join(fm) + "\n\n" + "\n".join(b) + "\n"


def _governance_snippet(charter: Charter) -> str:
    agents = [m for m in charter.members if m.type == "agent"]
    humans = [m for m in charter.members if m.type == "human"]
    gated = {n: a for n, a in charter.actions.items() if a.gate is not None}

    s: list[str] = []
    s.append("<!-- Generated by `agenraci compile --target claude`. Paste this "
             "section into your project's CLAUDE.md and regenerate when the "
             "charter changes. -->")
    s.append("")
    s.append("## Team governance (from the AgenRACI charter)")
    s.append("")
    s.append(f"This project runs on an AgenRACI charter (project: "
             f"**{charter.project}**); `agenraci validate` on it must pass.")
    s.append("")
    s.append("Agents (definitions in `.claude/agents/`):")
    for m in agents:
        s.append(f"- **{m.name}** — {m.role}")
    s.append("")
    if gated:
        s.append("Gated actions — never bypass these approvals:")
        s.append("")
        for n, a in gated.items():
            s.extend(_gate_summary(n, a, charter))
        s.append("")
    if humans:
        s.append("Final authority rests with the human members: "
                 + ", ".join(f"**{h.name}**" for h in humans) + ".")
    return "\n".join(s) + "\n"


def compile(charter: Charter) -> str:  # noqa: A001 - mirror CLI "compile" verb
    """Emit .claude/agents/<member>.md files + a CLAUDE.md governance snippet."""
    agents = [m for m in charter.members if m.type == "agent"]
    if not agents:
        return ("# No agent members in this charter — nothing to generate.\n"
                "# (Agent files are emitted per member with `type: agent`.)\n")

    parts: list[str] = []
    for m in agents:
        parts.append(FILE_MARKER.format(path=f".claude/agents/{m.name}.md"))
        parts.append(_agent_file(m, charter))
    parts.append(FILE_MARKER.format(path="CLAUDE.governance.md"))
    parts.append(_governance_snippet(charter))
    return "\n".join(parts)
