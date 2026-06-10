# AgenRACI — launch plan & tracker

> Working tracker for the 0.1.0 launch (drafted 2026-06-03). Internal notes live in
> `~/.gstack/projects/nextraci/launch-plan-20260603.md`. Check items off as they ship.

**State:** renamed to **AgenRACI** (sidesteps the `next` IP gate) · v0.1 code on `main` ·
PyPI name `agenraci` **claimed** (placeholder `0.1.0a0`) · all launch assets merged to
`main` and **launch-ready**: essay + FAQ + R6 + tag-driven publish + launch-adds (#29) +
Phase 1 copy (#34) + GitHub templates (#35) + R6-active doc sweep (#37). Remaining work
is the human launch-day runbook below (PyPI Trusted Publishing → tag → Vercel → post).

**Goal of this window:** go from "code pushed" to a credible, launchable **0.1.0** with
one strong public moment — without over-promising the v0.2 runtime control plane.

---

## 🚀 Launch-day runbook (do these in order)

> Everything in the repo is ready. These are the human steps no agent can do for you —
> PyPI / Vercel / GitHub account actions and public posting. Check off as you go.

**1. Pre-flight (can do now, before launch morning)**
- [ ] Run the local build smoke test green (see `RELEASING.md` → Readiness checklist):
      `python -m build` · `twine check dist/*` · fresh-venv `pip install dist/agenraci-*.whl` · `agenraci --version` · `agenraci validate examples/sprout/charter.yaml`
- [ ] Confirm CI is green on `main` (Actions tab).
- [ ] **One-time PyPI Trusted Publishing setup** (OIDC, no token) per `RELEASING.md`:
      PyPI `agenraci` → Settings → Publishing → add Trusted Publisher (owner `jing-ny`,
      repo `agenraci`, workflow `publish.yml`, environment `pypi`); then create the
      `pypi` Environment in GitHub repo settings (optional: required reviewer to gate upload).

**2. Ship the package (launch morning, Tue–Thu AM ET)**
- [ ] Confirm `pyproject.toml` version is `0.1.0`, committed on `main`.
- [ ] Tag + push: `git tag v0.1.0 && git push origin v0.1.0` → `publish.yml` builds + uploads (supersedes the `0.1.0a0` placeholder).
- [ ] Verify live: <https://pypi.org/project/agenraci/> · `pip install agenraci` in a clean venv · `agenraci validate examples/sprout/charter.yaml`.
- [ ] **Cut GitHub Release `v0.1.0`** using the notes in `docs/launch/release-notes-v0.1.0.md`.

**3. Deploy the playground**
- [ ] Import the repo at `vercel.com/new` (one-time; `vercel.json` already points at `docs/playground/`). Confirm the deployed page runs the checker (Pyodide).

**4. Go public (author present in comments first 6–8h)**
- [ ] Post **Show HN** (`docs/launch/show-hn.md`) + link the essay.
- [ ] Staggered cross-post (`docs/launch/social.md`): X thread → LinkedIn (governance angle) → relevant subreddits (read each sub's self-promo rules first).
- [ ] Share in LangChain/LangGraph Discord, HumanLayer community, AI-governance circles.

**5. After**
- [ ] Triage issues/PRs/comments fast — point newcomers at the seeded good-first-issues (#30–#33).
- [ ] Bump `pyproject.toml` to the next dev version on `main`.

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

## Launch-impact adds (CEO-review picks) — ✅ on `main` via PR [#29](https://github.com/jing-ny/agenraci/pull/29)
> Built in PR #27 but stranded off `main` by a stacked-merge ordering bug ([#28](https://github.com/jing-ny/agenraci/issues/28)); #29 re-landed them.
- [x] Flagship `examples/autopilot/` (autonomous coding team, 1 human + 4 agents) + demo GIF
- [x] GitHub Action (`action.yml`) + pre-commit hook (`.pre-commit-hooks.yaml`); `validate` takes many paths
- [x] `agenraci validate --explain` (plain-language fix per failing rule)
- [x] Browser playground (`docs/playground/`, Pyodide) + `vercel.json` to deploy it

## Phase 1 — Essay + assets (Week 1-2)
- [x] Launch essay `docs/why-agenraci.md` (~800-1200 words, broad audience) — [#7](https://github.com/jing-ny/agenraci/issues/7) (merged; light polish in this PR)
- [x] FAQ: RBAC / HumanLayer / vaporware objections — [#9](https://github.com/jing-ny/agenraci/issues/9) (in README)
- [x] Show HN draft + X / LinkedIn / Reddit copy → `docs/launch/` (PR [#34](https://github.com/jing-ny/agenraci/pull/34))
- [x] GitHub issue & PR templates — [#22](https://github.com/jing-ny/agenraci/issues/22) (PR [#35](https://github.com/jing-ny/agenraci/pull/35))
- [x] R6-active doc sweep (CONTRIBUTING/RELEASING/agents) — [#36](https://github.com/jing-ny/agenraci/issues/36) (PR [#37](https://github.com/jing-ny/agenraci/pull/37))
- [x] v0.1.0 GitHub Release notes drafted → `docs/launch/release-notes-v0.1.0.md`
- [x] Reseed good-first-issues — [#23](https://github.com/jing-ny/agenraci/issues/23) → opened [#30](https://github.com/jing-ny/agenraci/issues/30) [#31](https://github.com/jing-ny/agenraci/issues/31) [#32](https://github.com/jing-ny/agenraci/issues/32) [#33](https://github.com/jing-ny/agenraci/issues/33)

## Phase 2 — Launch day
> Consolidated into the **🚀 Launch-day runbook** at the top of this file.

## Phase 3 — Post-launch (Week 2-3)
- [ ] Triage issues/PRs/comments fast (sets whether contributors return)
- [x] Ship R6 acyclic-authority check — [#8](https://github.com/jing-ny/agenraci/issues/8) (already active in `linter.py`); pick a fresh first v0.2 increment (e.g. HumanLayer connector spike)
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
