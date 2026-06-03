# nextRACI — launch plan & tracker

> Working tracker for the 0.1.0 launch (drafted 2026-06-03). Internal notes live in
> `~/.gstack/projects/nextraci/launch-plan-20260603.md`. Check items off as they ship.

**State:** name claimed · v0.1 code on `main` · PyPI `0.0.0` placeholder · 4 project
agents + CLAUDE.md merged · issues #1–#9 open.

**Goal of this window:** go from "code pushed" to a credible, launchable **0.1.0** with
one strong public moment — without over-promising the v0.2 runtime control plane.

---

## ⚠️ Decide before launch day
- [ ] **Brand permanence.** `next` sits under an IP / brand-neutralization gate (Next
  Core); nextRACI inherits it. Confirm `next` is safe, or switch to Plan B `agenraci`,
  **before** Show HN — renaming after launch is costly.

## Phase 0 — Pre-launch polish (Week 1)
- [ ] CI: GitHub Actions (pytest + validate) on 3.11/3.12 + README badge — [#1](https://github.com/jing-ny/nextraci/issues/1)
- [ ] All-agent worked example (every role-holder is an AI agent) — [#3](https://github.com/jing-ny/nextraci/issues/3)
- [ ] Demo asciinema/GIF of validate catching an R1 gap *(highest-leverage asset)* — [#4](https://github.com/jing-ny/nextraci/issues/4)
- [ ] README badges + GitHub topics & description — [#5](https://github.com/jing-ny/nextraci/issues/5)
- [ ] Seed 3-5 good first issues — [#6](https://github.com/jing-ny/nextraci/issues/6)

## Phase 1 — Essay + assets (Week 1-2)
- [ ] Launch essay `docs/why-nextraci.md` (~800-1200 words, broad audience) — [#7](https://github.com/jing-ny/nextraci/issues/7)
- [ ] FAQ: RBAC / HumanLayer / vaporware objections — [#9](https://github.com/jing-ny/nextraci/issues/9)
- [ ] Show HN draft + X / LinkedIn / Reddit copy

## Phase 2 — Launch day (Week 2, Tue-Thu AM ET)
- [ ] 0.1.0 release readiness checklist green — [#2](https://github.com/jing-ny/nextraci/issues/2)
- [ ] Publish real **0.1.0** to PyPI (replaces 0.0.0 placeholder)
- [ ] Post Show HN + essay; author present in comments first 6-8h
- [ ] Cross-post (staggered): X thread, LinkedIn (governance angle), relevant subreddits
- [ ] Share in LangChain/LangGraph Discord, HumanLayer community, AI-governance circles

## Phase 3 — Post-launch (Week 2-3)
- [ ] Triage issues/PRs/comments fast (sets whether contributors return)
- [ ] Ship R6 acyclic-authority check (de-stub) as first visible v0.2 increment — [#8](https://github.com/jing-ny/nextraci/issues/8)
- [ ] Write "what I learned launching" retro post
- [ ] Measure: stars, PyPI downloads, unique visitors — watch for *real adopters*, not vanity metrics

---

## Agents (in `.claude/agents/`)
- **writer** — prose: README/SPEC/CONTRIBUTING/examples/essays, issue & PR text.
- **coder** — Python: schema/loader/linter/cli/adapters.
- **reviewer** — independent, read-only review before merge/release.
- **qa** — runs tests + CLI + packaging smoke; confirms each rule fires.

Loop for a non-trivial change: **coder** → **qa** → **reviewer** → **writer** (docs).
Keep reviewer/qa independent of the change author.
