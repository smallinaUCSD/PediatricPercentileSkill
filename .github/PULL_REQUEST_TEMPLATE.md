## What this changes and why

<!-- One or two sentences. Link an issue if there is one. -->

## Checklist

- [ ] `uv run pytest` passes locally
- [ ] If this touches `tests/golden/` or `references/data/`: a CODEOWNER
      is tagged, and each changed value has a citation (see
      `CONTRIBUTING.md`)
- [ ] If this changes `scripts/growth.py` or `adapters/`: no new network
      calls, randomness, or reliance on system time/locale
- [ ] If this adds/changes an eval scenario: a real captured response is
      committed under `evals/responses/` (see `EVALUATION.md`)
- [ ] `CHANGELOG.md` updated for anything user-visible

## How you tested this

<!-- Commands you ran, or the manual steps you took. -->
