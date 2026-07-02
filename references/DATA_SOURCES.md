# Data sources

Provenance for every LMS reference table shipped in `references/data/`.
All files below were retrieved **2026-07-01**.

## License / usage terms

CDC growth chart data files are US government works in the public domain.
WHO Child Growth Standards data are freely distributed by WHO for
unrestricted use in child health monitoring; WHO requests attribution
(satisfied by the citations in `METHODOLOGY.md`) but does not restrict
use. Neither source requires a license file beyond this attribution.

## CDC files (2 to 20 years, and birth to 36 months)

Source: CDC Growth Charts data file downloads
(https://www.cdc.gov/growthcharts/cdc-data-files.htm), CSV format, "LMS
parameters and selected smoothed... percentiles."

| File in repo | Indicator | Age/length range | Original filename | sha256 |
|---|---|---|---|---|
| `cdc_wtage.csv` | weight-for-age | 24-240mo | `wtage.csv` | `3406c9d125bcb69c062a9e84eb8c0209bfe9346542bdc1d308643750dcc241b7` |
| `cdc_statage.csv` | stature-for-age | 24-240mo | `statage.csv` | `45130d2a9d7c50c54a47e7ba626b66c61d4554bc2d901198cedd9419a53f7251` |
| `cdc_bmiagerev.csv` | BMI-for-age | 24-240mo | `bmiagerev.csv` | `cbeea0e8d500ee15c652f3fdc45bcd02cb9c15d4d1e86f4d8048bbfea8d166e5` |
| `cdc_wtageinf.csv` | weight-for-age | 0-36mo | `wtageinf.csv` | `73221dd4de82eb9a70c1e6dd45c9b9e285fa1a3d7fff4971c3b85c1be6e5feed` |
| `cdc_lenageinf.csv` | length-for-age | 0-36mo | `lenageinf.csv` | `a334b86bc0ecde80d12cdc172dde17b4390ca53ac372b26dd0d72d8502ac2687` |
| `cdc_wtleninf.csv` | weight-for-recumbent-length | 45-103.5cm | `wtleninf.csv` | `3dd616c8d11ad8ad5470929477609e6fc44cb2e5f7b95494061e1413a0034249` |
| `cdc_hcageinf.csv` | head-circumference-for-age | 0-36mo | `hcageinf.csv` | `bf7e2d7af8fdb336f0b159e480414842136da960ea6a730b7e73d1060b4549e9` |
| `cdc_wtstat.csv` | weight-for-stature | 77-121cm | `wtstat.csv` | `0f75b6ef7ac725c311bd3ff9d50c5b3b415b7faa00c99126b04f4f9a1c773db3` |

**Extended BMI-for-age**, source: CDC Extended BMI-for-Age Growth Charts
data file (https://www.cdc.gov/growthcharts/extended-bmi-data-files.htm).

| File in repo | Indicator | Age range | Original filename | sha256 |
|---|---|---|---|---|
| `cdc_bmi_extended.csv` | extended BMI-for-age (L, M, S, sigma, P95, selected percentiles/z-scores) | 24-240mo | `bmi-age-2022.csv` | `7f416a213157a5209bb6cbfd1b19292510248f3f31fe43c9ff63f6d8e39f7890` |

The extended-BMI half-normal formula implemented in the engine was
reverse-derived from this file's own tabulated Z2/Z2.5/Z3 columns and
verified to reproduce them to 4+ decimal places — see `METHODOLOGY.md` §4.

CDC does not publish a stature-for-age or head-circumference-for-age
chart beyond 36 months in the 2000 growth chart set; the engine treats
head-circumference as out-of-range beyond what `cdc_hcageinf.csv` /
`who_head_circumference_for_age.csv` cover (see `METHODOLOGY.md`).

## WHO files (0 to <24 months, used per the WHO/CDC age split)

Source: WHO Child Growth Standards "Expanded tables for constructing
national health cards" (z-score expanded tables), .xlsx, per indicator
and sex, from `cdn.who.int`. Raw originals are kept in
`references/data/who_raw/` for audit; the engine reads the normalized
CSVs produced from them (see "Processing" below).

| Raw file (`who_raw/`) | Indicator | Sex | sha256 |
|---|---|---|---|
| `who_wfa_boys.xlsx` | weight-for-age | male | `b5b4748c6bfa5230e2eddafa1767629c349178b08d457f400b59422b8bfef86c` |
| `who_wfa_girls.xlsx` | weight-for-age | female | `ee3ae12cb96c6c5541cdf43665c03ce6c984f877859a183a5f6104eb06a49a6e` |
| `who_lhfa_boys.xlsx` | length-for-age | male | `c4b1c9029ab9751a5f0888e32f35c7c0287a16d361885cf911ecf23b3f7f6b4f` |
| `who_lhfa_girls.xlsx` | length-for-age | female | `6aa2876319449a6b1f4d825848128902114ff53c67b92b86a0c5140846013059` |
| `who_wfl_boys.xlsx` | weight-for-length | male | `1a6e9a002d2692d038161bc6572a10f8b9fa0657163808141d2981a2132c59cc` |
| `who_wfl_girls.xlsx` | weight-for-length | female | `ec116b8e618ad311d34a87231346badf16c75f5c4f82222ec846e05c582bf16a` |
| `who_hcfa_boys.xlsx` | head-circumference-for-age | male | `89a657bc466e85f6c8f2e5e7f4635e969bdcf982bb71e519273e43896a1c3314` |
| `who_hcfa_girls.xlsx` | head-circumference-for-age | female | `8eec3770d1027ce1b3b96a7b89fd1e77070558a7791b17b4462cda8a813324a3` |
| `who_bfa_boys.xlsx` | BMI-for-age | male | `58dcb2abea0e04b1c4f8ad3511d05ec1bea03741f230ac127b93f929e4cc6fc8` |
| `who_bfa_girls.xlsx` | BMI-for-age | female | `d3817262a383cdd02553b004f1c6110527d30b729c70501d032e71caadc17529` |

Note: WHO's "weight-for-height" expanded table (2-5yr, standing height)
was intentionally **not** downloaded/kept — v1's reference-selection rule
only ever uses WHO standards below 24 months, and children under 24
months are always measured by recumbent length, never standing height,
so that table would never be reached by the engine.

### Processing

`who_raw/*.xlsx` files have one sheet each with columns `Day` (or
`Length`), `L`, `M`, `S`, `SD4neg`...`SD4`. These were converted with
`references/data/convert_who.py` (`uv run --group data python3
references/data/convert_who.py`, re-run only when re-syncing from WHO)
into normalized CSVs matching the CDC files' `Sex` column convention
(`1`=male, `2`=female), keeping only `L`, `M`, `S`:

| Processed file | Indicator | Axis | sha256 |
|---|---|---|---|
| `who_weight_for_age.csv` | weight-for-age | `age_days` (0-1856) | `219f486b97c7059280db81f20b15127650dec18fdf5796b0ed3efc86467d9131` |
| `who_length_for_age.csv` | length-for-age | `age_days` (0-1856) | `34d3369a537574b00afa434b9c1ef4bbcf5662764746835205e799aa680ee243` |
| `who_head_circumference_for_age.csv` | head-circumference-for-age | `age_days` (0-1856) | `7155f09ce400872150e3754b4c18a6318ab04f38a986370d3722888f8cedcaa4` |
| `who_bmi_for_age.csv` | BMI-for-age | `age_days` (0-1856) | `c404b581932180a789a39809376abe9e3d9a7c2144a0a9d7fae4dda3cfd5c1a4` |
| `who_weight_for_length.csv` | weight-for-length | `length_cm` (45-110) | `763954cd444f93f1e5b1c2297da931af2bc1e1d619285a6e3b4f520e5464040b` |

`age_days` uses WHO's convention of 30.4375 days/month (365.25/12) for
converting to/from `age_months` (see `METHODOLOGY.md` §5).

## Update policy

Any change to a file in `references/data/` (raw or processed) must update
its row in this table (new checksum, retrieval date) in the same commit,
and must be reviewed by a CODEOWNER (see `tests/golden/` protection in
`CONTRIBUTING.md`) since it can silently change every downstream
percentile.
