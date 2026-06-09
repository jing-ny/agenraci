# Releasing AgenRACI

The 0.1.0 release replaces the `0.0.0` PyPI placeholder with the first real
package. Publishing is **tag-driven and reproducible**: a maintainer pushes a
`vX.Y.Z` tag, and the [`publish.yml`](.github/workflows/publish.yml) workflow
builds, checks, and uploads to PyPI. No one runs `twine upload` by hand, and no
API token is stored in the repo (PyPI Trusted Publishing is used instead).

## One-time setup (PyPI Trusted Publishing)

Do this once, before the first tag-driven release. It lets GitHub Actions publish
without any long-lived token.

1. On PyPI, create (or claim) the `agenraci` project — the `0.0.0` placeholder
   already reserves the name.
2. In the project's **Settings → Publishing**, add a **Trusted Publisher**:
   - Owner: `jing-ny`
   - Repository: `agenraci`
   - Workflow name: `publish.yml`
   - Environment: `pypi`
3. In the GitHub repo, create an **Environment** named `pypi`
   (Settings → Environments). Optionally add required reviewers so a release
   pauses for human approval before the upload step runs.

> Token fallback (only if you choose not to use Trusted Publishing): create a
> PyPI API token, store it as the `PYPI_API_TOKEN` repo secret, and pass
> `password: ${{ secrets.PYPI_API_TOKEN }}` to the publish step. Trusted
> Publishing is preferred because there is no secret to leak or rotate.

## Readiness checklist (gate before tagging)

Everything here must be true on `main` before you cut the tag.

- [ ] **CI is green** on `main` (tests on 3.11 + 3.12; example/template/governance
      charters validate).
- [ ] **README and SPEC agree** — the checker table, the roadmap, and the
      "what it is / isn't yet" scope box all describe the same active rule set,
      with nothing labelled "planned/stub" that has actually shipped.
- [ ] **A second worked example is merged** (`examples/relay/` alongside
      `examples/sprout/`).
- [ ] **A demo asset is linked from the README** (the `docs/demo/` walkthrough;
      render the GIF with `vhs docs/demo/demo.tape` if shipping the animation).
- [ ] **Version is bumped** in `pyproject.toml` to the release version (the
      publish workflow refuses to run if the tag and `pyproject` version differ).
- [ ] **The build is clean locally:**
      ```bash
      python -m build
      twine check dist/*
      ```
      Both artifacts must report `PASSED`.
- [ ] **A fresh install works from the built wheel:**
      ```bash
      python -m venv /tmp/agenraci-rc && source /tmp/agenraci-rc/bin/activate
      pip install dist/agenraci-*.whl
      agenraci --version
      agenraci validate examples/sprout/charter.yaml
      deactivate
      ```

## Cutting the release

Once every box above is checked:

```bash
# 1. Make sure you are on an up-to-date main with the version bump committed.
git checkout main && git pull

# 2. Tag the release. The tag MUST be v<version> matching pyproject.toml.
git tag v0.1.0
git push origin v0.1.0
```

Pushing the tag triggers [`publish.yml`](.github/workflows/publish.yml):

1. **build** — verifies the tag matches the `pyproject` version, builds the sdist
   and wheel, and runs `twine check`.
2. **publish** — uploads to PyPI via Trusted Publishing under the `pypi`
   environment (this is the step a required reviewer can gate).

## After publishing

- [ ] Confirm the release is live: <https://pypi.org/project/agenraci/>.
- [ ] `pip install agenraci` in a clean environment and run
      `agenraci validate examples/sprout/charter.yaml`.
- [ ] Create a GitHub Release for the tag with notes (what shipped, the active
      rule set, known limitations).
- [ ] Bump `pyproject.toml` to the next dev version on `main`.

## Yanking a bad release

If a published version is broken, **do not delete it** (deleting frees the
version number and breaks reproducibility). Instead, `yank` it on PyPI so it stops
being installed by default while remaining available for anyone who pinned it,
then fix forward with a new patch version.
