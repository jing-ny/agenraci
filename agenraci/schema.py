"""Pydantic v2 models for a AgenRACI ``charter.yaml``.

The charter is the single human-readable file that declares the *operating
constitution* of a mixed human + AI-agent team. It answers, for every TYPE of
action in a project: who does it (Responsible), who owns it (Accountable), who
is Consulted / Informed, who must approve it, and what happens when the approver
is offline.

Design notes (v0.1):

* ``Role`` is a **first-class, standalone** model. In v0.1 roles are declared
  inline in the charter (as a list of names, with capabilities attached via the
  ``capabilities`` map), but modelling ``Role`` as its own object means a future
  version can load a shared role library from a separate file without a schema
  rewrite. ``Charter.get_roles()`` assembles the ``Role`` objects.
* Permissions (capabilities) attach to **roles**, never to individual members.
* ``accountable`` accepts either a single role name or a list, but is always
  normalised to a list internally. The "exactly one accountable" invariant is a
  *linter* rule (R1), not a schema constraint, so the linter can report 0- and
  2+-accountable charters with a helpful message instead of a raw parse error.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The special ``responsible`` value meaning "any member may carry this out".
ANY = "any"

# Legal literal values for a gate's ``on_timeout`` (besides ``escalate_to:<role>``).
_ON_TIMEOUT_LITERALS = {"block", "proceed_if_low_risk"}
_ESCALATE_PREFIX = "escalate_to:"


class CapabilitySet(BaseModel):
    """What a role may touch: capabilities granted and/or explicitly denied.

    A capability is just a string token (e.g. ``edit_code``, ``merge``,
    ``deploy``, ``spend``, ``contact_users``, ``read_analytics``,
    ``block_merge``). Denials are explicit and first-class — a role can be
    *denied* a capability it would otherwise be assumed to have.
    """

    model_config = ConfigDict(extra="forbid")

    grant: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class Role(BaseModel):
    """A first-class role in the team's constitution.

    Roles are defined once and members are *assigned* to them (RBAC), so the
    charter's size is fixed no matter how many agents you add.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    capabilities: CapabilitySet = Field(default_factory=CapabilitySet)


class Member(BaseModel):
    """A human or agent appointed to a role. Appointing a member is one line."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str  # "human" | "agent"
    role: str
    model: Optional[str] = None  # e.g. claude-opus-4-8 (agents only)

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in {"human", "agent"}:
            raise ValueError(f"member type must be 'human' or 'agent', got {v!r}")
        return v


class BreakGlass(BaseModel):
    """The emergency path around a gate, with a named owner and condition.

    e.g. an engineer may hotfix-deploy during a SEV-1 without the normal merge
    gate, with mandatory after-the-fact review.
    """

    model_config = ConfigDict(extra="forbid")

    who: str
    condition: str
    requires_after_review: bool = False


class Gate(BaseModel):
    """An approval gate on an action.

    Every gate must declare ``on_timeout`` and ``break_glass`` (enforced by
    linter rule R4) so a safety rule can never silently deadlock the team.
    """

    model_config = ConfigDict(extra="forbid")

    approver: str
    on_timeout: str
    # Optional at the schema level so the linter (R4) can report a missing
    # break_glass with a helpful message rather than a raw parse error.
    break_glass: Optional[BreakGlass] = None

    @field_validator("on_timeout")
    @classmethod
    def _check_on_timeout(cls, v: str) -> str:
        if v in _ON_TIMEOUT_LITERALS:
            return v
        if v.startswith(_ESCALATE_PREFIX) and v[len(_ESCALATE_PREFIX):].strip():
            return v
        raise ValueError(
            "on_timeout must be 'block', 'proceed_if_low_risk', or "
            f"'escalate_to:<role>', got {v!r}"
        )

    @property
    def is_proceed_if_low_risk(self) -> bool:
        return self.on_timeout == "proceed_if_low_risk"

    @property
    def escalate_target(self) -> Optional[str]:
        if self.on_timeout.startswith(_ESCALATE_PREFIX):
            return self.on_timeout[len(_ESCALATE_PREFIX):].strip()
        return None


class SuggestionRoute(BaseModel):
    """Where a blocked-but-confident actor's input goes so it isn't dropped.

    e.g. the Domain Expert who can't touch code files a ``correction_request``
    the Engineer must clear before the Reviewer can approve the merge.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    as_: str = Field(alias="as")


class Action(BaseModel):
    """One TYPE of action that can occur in the project, with its RACI + gate.

    Enumerate action *types*, not individual tasks. Each must map to exactly one
    Accountable role (R1).
    """

    model_config = ConfigDict(extra="forbid")

    responsible: str
    accountable: list[str]
    consulted: list[str] = Field(default_factory=list)
    informed: list[str] = Field(default_factory=list)
    # Capabilities this action touches/exercises (used by R2 coverage).
    capabilities: list[str] = Field(default_factory=list)
    low_risk: bool = False
    gate: Optional[Gate] = None
    suggestion_route: Optional[SuggestionRoute] = None

    @field_validator("accountable", mode="before")
    @classmethod
    def _normalise_accountable(cls, v):
        # Accept a single role name or a list; always store a list so R1 can
        # check the "exactly one" invariant.
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class Charter(BaseModel):
    """The whole operating constitution for one project."""

    model_config = ConfigDict(extra="forbid")

    project: str
    roles: list[str]
    members: list[Member] = Field(default_factory=list)
    capabilities: dict[str, CapabilitySet] = Field(default_factory=dict)
    actions: dict[str, Action] = Field(default_factory=dict)

    # ----- referential integrity (structural; distinct from linter rules) -----

    @model_validator(mode="after")
    def _check_references(self) -> "Charter":
        roles = set(self.roles)
        if len(self.roles) != len(roles):
            dupes = sorted({r for r in self.roles if self.roles.count(r) > 1})
            raise ValueError(f"duplicate role(s) declared: {', '.join(dupes)}")

        problems: list[str] = []

        for cap_role in self.capabilities:
            if cap_role not in roles:
                problems.append(
                    f"capabilities block references undeclared role {cap_role!r}"
                )

        for m in self.members:
            if m.role not in roles:
                problems.append(
                    f"member {m.name!r} assigned to undeclared role {m.role!r}"
                )

        def _require_role(ref: str, where: str, *, allow_any: bool = False) -> None:
            if allow_any and ref == ANY:
                return
            if ref not in roles:
                problems.append(f"{where} references undeclared role {ref!r}")

        for name, action in self.actions.items():
            _require_role(action.responsible, f"action {name!r} responsible", allow_any=True)
            for r in action.accountable:
                _require_role(r, f"action {name!r} accountable")
            for r in action.consulted:
                _require_role(r, f"action {name!r} consulted")
            for r in action.informed:
                _require_role(r, f"action {name!r} informed")
            if action.gate is not None:
                _require_role(action.gate.approver, f"action {name!r} gate.approver")
                target = action.gate.escalate_target
                if target is not None:
                    _require_role(target, f"action {name!r} gate.on_timeout escalate_to")
            if action.suggestion_route is not None:
                _require_role(
                    action.suggestion_route.from_, f"action {name!r} suggestion_route.from"
                )
                _require_role(
                    action.suggestion_route.to, f"action {name!r} suggestion_route.to"
                )

        if problems:
            raise ValueError("; ".join(problems))
        return self

    # ----- helpers -----

    def get_role(self, name: str) -> Role:
        """Assemble the first-class ``Role`` object for ``name``."""
        return Role(
            name=name,
            capabilities=self.capabilities.get(name, CapabilitySet()),
        )

    def get_roles(self) -> list[Role]:
        return [self.get_role(n) for n in self.roles]

    def declared_capabilities(self) -> set[str]:
        """Every capability token mentioned in any role's grant/deny."""
        caps: set[str] = set()
        for cap_set in self.capabilities.values():
            caps.update(cap_set.grant)
            caps.update(cap_set.deny)
        return caps
