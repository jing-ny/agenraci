# AgenRACI — launch plan & tracker

> Working tracker for the 0.1.0 launch (drafted 2026-06-03). Internal notes live in
> `~/.gstack/projects/nextraci/launch-plan-20260603.md`. Check items off as they ship.

**State:** renamed to **AgenRACI** (sidesteps the `next` IP gate) · v0.1 code on `main` ·
PyPI name `agenraci` to be claimed · 4 project agents + CLAUDE.md merged · issues #1–#9 open.

**Goal of this window:** go from "code pushed" to a credible, launchable **0.1.0** with
one strong public moment — without over-promising the v0.2 runtime control plane.

---

## ⚠️ Decide before launch day
- [x] **Brand permanence.** The `next` prefix sat under an IP / brand-neutralization
  gate (Next Core). Resolved 2026-06-09 by renaming to **AgenRACI** (`agenraci` token),
  which sidesteps the `next` brand entirely — so no Next Core IP clearance is needed.
  PyPI name `agenraci` claimed 2026-06-09 (placeholder `0.1.0a0` reserves it; real
  `0.1.0` ships on launch day).

## Phase 0 — Pre-launch polish (Week 1) ✅ done
- [x] CI: GitHub Actions (pytest + validate) on 3.11/3.12 + README badge — [#1](https://github.com/jing-ny/agenraci/issues/1)
- [x] All-agent worked example (`examples/relay`, 5 agents 0 humans) — [#3](https://github.com/jing-ny/agenraci/issues/3)
- [x] Demo: charter pair + VHS tape + walkthrough in `docs/demo/` — [#4](https://github.com/jing-ny/agenraci/issues/4) · GIF rendered + embedded in README (PR [#27](https://github.com/jing-ny/agenraci/pull/27))
- [x] README badges + GitHub topics & description — [#5](https://github.com/jing-ny/agenraci/issues/5)
- [x] Seed good first issues — [#6](https://github.com/jing-ny/agenraci/issues/6) → opened [#10](https://github.com/jing-ny/agenraci/issues/10) [#11](https://github.com/jing-ny/agenraci/issues/11) [#12](https://github.com/jing-ny/agenraci/issues/12)

## Launch-impact adds (CEO-review picks) — shipped in PR [#27](https://github.com/jing-ny/agenraci/pull/27)
- [x] Flagship `examples/autopilot/` (autonomous coding team, 1 human + 4 agents) + demo GIF
- [x] GitHub Action (`action.yml`) + pre-commit hook (`.pre-commit-hooks.yaml`); `validate` takes many paths
- [x] `agenraci validate --explain` (plain-language fix per failing rule)
- [x] Browser playground (`docs/playground/`, Pyodide) + `vercel.json` to deploy it

## Phase 1 — Essay + assets (Week 1-2)
- [ ] Launch essay `docs/why-agenraci.md` (~800-1200 words, broad audience) — [#7](https://github.com/jing-ny/agenraci/issues/7)
- [ ] FAQ: RBAC / HumanLayer / vaporware objections — [#9](https://github.com/jing-ny/agenraci/issues/9)
- [ ] Show HN draft + X / LinkedIn / Reddit copy

## Phase 2 — Launch day (Week 2, Tue-Thu AM ET)
- [ ] 0.1.0 release readiness checklist green — [#2](https://github.com/jing-ny/agenraci/issues/2)
- [ ] Publish real **0.1.0** to PyPI (replaces 0.0.0 placeholder)
- [ ] Post Show HN + essay; author present in comments first 6-8h
- [ ] Cross-post (staggered): X thread, LinkedIn (governance angle), relevant subreddits
- [ ] Share in LangChain/LangGraph Discord, HumanLayer community, AI-governance circles

## Phase 3 — Post-launch (Week 2-3)
- [ ] Triage issues/PRs/comments fast (sets whether contributors return)
- [ ] Ship R6 acyclic-authority check (de-stub) as first visible v0.2 increment — [#8](https://github.com/jing-ny/agenraci/issues/8)
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
