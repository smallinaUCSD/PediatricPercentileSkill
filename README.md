# Growth Percentile Skill

[![CI](https://github.com/smallinaUCSD/growth-percentile-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/smallinaUCSD/growth-percentile-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![v0.2.0](https://img.shields.io/badge/version-0.2.0-informational.svg)](CHANGELOG.md)

An open-source **Agent Skill** that computes pediatric growth percentiles
and z-scores from patient measurements, against the CDC and WHO growth
standards, using a frozen, tested, deterministic engine, not model
arithmetic. 

> Hand any agent a patient's measurements, in a FHIR bundle, a
> spreadsheet, or just typed into the chat, and it returns auditable
> growth percentiles with full provenance back to the source data.

![Example growth chart: weight, length/height, BMI, and head-circumference-for-age percentile curves with a patient's trajectory plotted on top](assets/growth-chart-example.png)

## Install

| Agent | Install |
|---|---|
| Claude Code | `/plugin marketplace add smallinaUCSD/growth-percentile-skill` then `/plugin install growth-percentile@growth-percentile-skill` |
| Codex | `$skill-installer install https://github.com/smallinaUCSD/growth-percentile-skill` |
| Hermes | `hermes skills install smallinaUCSD/growth-percentile-skill` |
| OpenClaw | `openclaw skills install git:smallinaUCSD/growth-percentile-skill` |
| OpenCode, Grok Build, Cursor, or any other agent | Clone this repo and point the agent at `SKILL.md` (each has its own skills directory, e.g. `.opencode/skills/`, `.grok/skills/`, `.cursor/rules/`) |

## Getting started

Ask your agent, in plain English:

> Using the growth-percentile skill, what percentile is a 9-month-old
> boy at 9.7 kg?

The agent reads `SKILL.md`, runs the numbers through the deterministic engine, 
and replies with a percentile,a z-score, which reference standard it used, 
and any data-quality flags.

## What it can also do

Hand it real patient data in almost any shape:

> I have this patient's records in a <FHIR bundle, CSV File, other data format> at
> `~/data/filename`. Calculate their growth percentiles.

and it comes back with something like:

| Age | Indicator | Value | Percentile | Reference | Flags |
|---|---|---|---|---|---|
| 0.0mo | Weight-for-age | 3.6 kg | 75.8th | WHO | |
| 0.0mo | Length-for-age | 54.3 cm | 99.7th | WHO | |
| 29.2mo | Weight-for-age | 12.3 kg | 34.0th | CDC | |
| 29.2mo | Height-for-age | 93.5 cm | 86.6th | CDC | |

plus a plain-English summary, and, on request, an interactive chart like
the one at the top of this page.

It handles:

- **Weight, length/height, BMI, and head-circumference percentiles and
  z-scores**, ages 0-20
- **Automatic WHO/CDC selection** as a patient crosses 24 months, mid-record
  if needed
- **Data-quality flags**: likely data-entry errors, missing reference
  charts for a given age/metric, prematurity considerations, derived BMI
- **Interactive growth charts**, one per patient, opened in any browser,
  no server or account needed

See [demo/warren_synthea.md](demo/warren_synthea.md) for a full
walkthrough on a complete patient record, including the WHO to CDC
handoff partway through.

## Bring your own data

Known formats, a FHIR R4 bundle or Synthea's CSV export, are read
directly and deterministically. Anything else (messy data) your agent reads it, 
converts weights/heights to kg/cm and ages to months, and figures out sex from 
whatever column and values your data uses (`sex` or `gender`, `M`/`F` or `male`/`female`). 
If sex is  missing, your agent will ask rather than guess, since it
changes which reference chart applies.

If your data doesn't fit cleanly into any of this, just tell your agent
and it can usually still work it out.

## How it works

The math is [Cole's LMS method](references/METHODOLOGY.md), the same
transform the CDC and WHO use to publish their own growth charts. 
WHO's 2006 standards are used for ages 0 to under 24 months,
CDC's 2000 charts for 24 months to 20 years, matching CDC/AAP guidance, selected
automatically from the patient's age.

## Learn more

- What this doesn't do yet, and clinical-use caveats:
  [TRUST_AND_LIMITATIONS.md](TRUST_AND_LIMITATIONS.md)
- Full formulas and citations:
  [references/METHODOLOGY.md](references/METHODOLOGY.md)
- Contributing, testing, and the adapter architecture:
  [CONTRIBUTING.md](CONTRIBUTING.md)
- Citation: [CITATION.cff](CITATION.cff)
- License: MIT, see [LICENSE](LICENSE)
