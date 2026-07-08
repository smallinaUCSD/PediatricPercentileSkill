# Releasing

This project has no automated release pipeline — releases are a manual,
checklist-driven process. This exists so that never changes silently:
the whole trust model here (see
[references/METHODOLOGY.md](references/METHODOLOGY.md) and
[EVALUATION.md](EVALUATION.md)) depends on every release being
deliberate and auditable, not a side effect of pushing to `main`.

## When to cut a release

Any user-visible change: a new adapter, an engine fix, a new indicator, a
`SKILL.md` behavior change, a new reference data file. Docs-only changes
(README wording, this file, etc.) don't need a version bump unless they
change something a user would act on differently.

## Checklist

1. **Confirm the working tree is clean and tests pass:**
   ```bash
   uv run pytest
   uv run evals/run_eval.py --all
   claude plugin validate .
   ```
2. **Bump the version in all four places it's declared** (they must
   agree — nothing enforces this automatically, so check by hand):
   - [`pyproject.toml`](pyproject.toml) — `version`
   - [`CITATION.cff`](CITATION.cff) — `version` and `date-released`
   - [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) — `version`
   - [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
     — the matching entry's `version`
3. **Update [`CHANGELOG.md`](CHANGELOG.md)**: rename `[Unreleased]` (or
   add a new heading) to `[X.Y.Z] - YYYY-MM-DD`, with a real, specific
   list of what shipped — not "misc fixes." Look at prior entries for the
   level of detail expected.
4. **Commit** all of the above together, in one commit, so a `git show`
   on the release commit tells the whole story.
5. **Tag**: `git tag -a vX.Y.Z -F <release-notes-file>` (annotated, not
   lightweight — the tag message is the release notes). Push the commit,
   then the tag:
   ```bash
   git push origin main
   git push origin vX.Y.Z
   ```
6. **Create the GitHub Release** from the pushed tag (via the GitHub UI,
   or the API/`gh` CLI if available) using the same notes as the tag
   message.
7. **Verify the plugin install path still works** post-tag:
   ```bash
   claude plugin marketplace add .
   claude plugin install growth-percentile@growth-percentile-skill
   claude plugin list
   claude plugin uninstall growth-percentile@growth-percentile-skill
   claude plugin marketplace remove growth-percentile-skill
   ```

## Versioning

Semantic versioning. Since this is pre-1.0: breaking changes to the
canonical schema, `GrowthResult` shape, or `SKILL.md`'s documented
behavior bump the minor version; everything else (new adapter, new
indicator, bug fix, doc change requiring a version bump at all) bumps the
patch version.
