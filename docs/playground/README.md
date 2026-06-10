# AgenRACI playground

A single static page that runs the **real** AgenRACI checker (rules R1–R6) in
the browser: paste a charter, hit Check, see the per-rule report. Nothing is
uploaded — [Pyodide](https://pyodide.org) runs the Python package client-side.

It loads the actual `agenraci/*.py` modules at runtime (from the site root), so
the playground can never drift from the package the CLI ships.

## Run it locally

The page fetches `/agenraci/*.py`, so serve the **repo root** (not this folder):

```bash
python3 -m http.server 8000        # from the repo root
# then open http://localhost:8000/docs/playground/
```

## Deploy it

`vercel.json` at the repo root serves the whole repo statically and rewrites
`/` to this page. Import the repo once at https://vercel.com/new; every push to
the default branch then redeploys. (The page needs `/agenraci/*.py` reachable at
the site root — the default static deploy provides exactly that.)
