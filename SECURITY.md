# Security policy

## Scope

This project computes growth percentiles from measurements the caller
supplies. It does not store patient data, make network calls at runtime,
or execute model-generated code — the calculation engine
(`scripts/growth.py`) is frozen, deterministic, and offline by design (see
`references/METHODOLOGY.md`).

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a
public issue. Open a GitHub security advisory on this repository, or
contact the maintainer directly.

## Skill-specific risks

This repository is distributed as an Agent Skill, meant to be installed
into an LLM agent's skill directory. Skills from untrusted sources are a
documented risk vector (a malicious `SKILL.md` or script could instruct an
agent to exfiltrate data or run unintended commands). Mitigations here:

- The engine and adapters are plain, readable Python with no dynamic code
  execution, `eval`, or network access.
- `tests/golden/` fixtures are protected by CODEOWNERS and a checksum gate
  (see `CONTRIBUTING.md`) so a compromised contribution can't silently
  alter expected clinical outputs.
- Review the diff of any release before upgrading, same as any dependency.
- Installed via `.claude-plugin/marketplace.json`, a plugin is pinned to
  the `version` string in `.claude-plugin/plugin.json` (bumped on
  `CHANGELOG.md`-worthy releases) — you only receive updates when that
  version changes, not on every commit to this repo.
