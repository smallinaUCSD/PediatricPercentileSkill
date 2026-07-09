# Methodology

This document specifies the exact math and decision rules the engine
(`scripts/growth.py`, Phase 1) implements. It is the reference the golden
test vectors in `tests/golden/` are checked against, and the citation trail
for anyone auditing a result.

## 1. LMS transform (Cole's method)

For a measurement `X`, and reference parameters `L`, `M`, `S` (looked up by
sex, indicator, and age or length/height):

```
z = ((X / M)^L - 1) / (L * S)      for L != 0
z = ln(X / M) / S                   for L == 0
percentile = Phi(z) * 100           (standard normal CDF, via math.erf -- see growth._norm_cdf)
```

This is the same transform used to generate the published CDC and WHO
growth charts.

## 2. Reference standard selection

| Age | Standard | Rationale |
|---|---|---|
| 0 to < 24 months | WHO (2006 Child Growth Standards) | CDC/AAP recommendation: WHO standards describe *how children should grow* under optimal conditions and are preferred for infants and toddlers in the US. |
| 24 months to 20 years | CDC (2000 Growth Charts, + 2022 extended BMI-for-age) | CDC references describe *how US children have grown*; used once WHO standards no longer apply. |

The engine selects automatically from `age_months`; callers may override
explicitly (e.g., to reproduce a chart computed under the other standard).

The boundary itself (exactly 24.0 months) is a documented edge case in the
golden test suite — CDC's own guidance is to switch at 24 months, not
"2 years" loosely interpreted, so age is compared in months, not rounded
years.

## 3. Length vs. stature

- **Recumbent length** (measured lying down) is used for `length_recumbent`,
  standard for ages 0 to < 24 months (or < 36 in some clinical settings for
  children who cannot yet stand reliably, but v1 follows the standard
  0-<24mo / 24mo+ split for consistency with the WHO/CDC handoff above).
- **Standing height** (`height_standing`) is used from 24 months onward.
- Weight-for-length uses the recumbent-length tables; weight-for-stature
  uses the standing-height tables. The engine picks the table based on
  which `metric` was supplied, not on age alone, so a caller who has a
  recumbent length for a 30-month-old (unusual but valid) gets the
  length-based table, not a silently wrong stature one.

## 4. Extended BMI-for-age

The ordinary LMS transform saturates at extreme obesity: because it maps
`X` through a power transform with `L < -1` at every age, very large BMI
values converge on nearly the same z-score (CDC's own worked example: BMI
33 -> z=1.97, but BMI 333 at the same sex/age -> z=3.1 -- a 300 kg/m2
difference collapses into a 1.1 SD difference). This understates severity
for children with the highest BMIs and makes the ordinary z-score useless
for catching gross data-entry errors.

CDC's 2022 extended BMI-for-age growth charts (`bmi-age-2022.csv`, see
`DATA_SOURCES.md`) replace the percentile above the 95th percentile with a
**half-normal distribution fit** using sex- and age-specific `sigma` and
`P95` parameters published alongside `L`, `M`, `S` in the same file, built
from NHANES data on children with obesity (not extrapolation). Below the
95th percentile, extended values are identical to ordinary CDC 2000
values by construction, so the transition is continuous.

**Formula (verified against the published data file — see below):**

For a BMI value `X`, sex, and age with parameters `L, M, S` (ordinary) and
`P95, sigma` (extended):

```
X < P95:  z = ((X/M)^L - 1) / (L*S)                       # ordinary LMS
X >= P95: p = 0.95 + 0.05 * erf((X - P95) / (sigma*sqrt(2)))
          z = Phi^-1(p)                                    # growth._norm_ppf (pure stdlib)
percentile = z-derived p * 100 in both branches
```

Verified: for CDC's own worked example row (male, 24mo, L=-2.01118107,
M=16.57502768, S=0.080592465, P95=19.338, sigma=1.3756), this formula
reproduces the file's own tabulated `Z2`/`Z2_5`/`Z3` BMI values (20.3657,
21.4529, 22.3802) to 4+ decimal places when evaluated in reverse (z ->
BMI). This cross-check is captured as a golden test vector.

The engine:
1. Computes the ordinary LMS z-score/percentile first.
2. If `X >= P95` for that sex/age (2-19 years only; extended parameters
   don't exist for WHO/under-24-months data), recomputes using the
   extended method above and tags the result with the `extended_bmi_used`
   flag.
3. Independently computes a **modified z-score** (see MZ below) purely as
   a plausibility check, regardless of which BMI method was used for the
   headline percentile.

## 4a. Modified z-scores (plausibility flag)

CDC's modified z-score exists specifically because the ordinary LMS
z-score is unsuitable for flagging data-entry errors (see extended-BMI
example above). It expresses a measurement relative to the median in
units of **half the LMS-predicted distance between z=0 and z=+/-2**:

```
BMI(z) = M * (1 + L*S*z)^(1/L)                 # Equation 2, same LMS family

if X > M:  SD_distance = 0.5 * (BMI(z=+2) - M)
if X < M:  SD_distance = 0.5 * (M - BMI(z=-2))
modified_z = (X - M) / SD_distance
```

Worked example from CDC's own documentation (200-month-old girl,
L=-2.18, M=20.76, S=0.148): BMI(z=+2) = 33.40, so
`SD_distance = (33.40-20.76)/2 = 6.32`. A BMI of 333 (a plausible
fat-fingered "33.3") gives `modified_z = (333-20.76)/6.32 = 49.2` -- caught
immediately, versus an ordinary LMS z of only 3.1. This same formula and
worked example is reproduced as a golden test vector.

The same construction (Equation 2 applied to that indicator's own L, M, S)
is used for weight-for-age and height/length-for-age, per CDC guidance
that "similar procedures were used to derive... modified z-scores for
weight and height."

**BIV (biologically implausible value) cutoffs**, per the CDC SAS growth
chart program:

| Indicator | Age range | Flag low | Flag high |
|---|---|---|---|
| Weight-for-age | 0 to <240mo | modified z < -5 | modified z > 8 |
| Height/length-for-age | 0 to <240mo | modified z < -5 | modified z > 4 |
| BMI-for-age | 24 to <240mo | modified z < -4 | modified z > 8 |
| Head circumference-for-age | any | modified z < -5 | modified z > 5 |

CDC does not publish an official BIV cutoff for head circumference; v1
uses a conservative +/-5 generic threshold and documents it as such rather
than implying it is an official CDC number. A value outside the relevant
range gets an `implausible_value` flag alongside its (still-reported)
percentile -- flagging never suppresses a result, per the plan's
"documented, not silently wrong" principle.

## 5. Age calculation and interpolation

- `age_months` is computed as the exact fractional number of months
  between `birth_date` and `observation_date` (day-resolution, not
  calendar-month counting), unless the caller supplies `age_months`
  directly.
- CDC's age-based tables (`references/data/cdc_*.csv`) are tabulated at
  half-month `Agemos` steps; its length/stature-based tables at half-cm
  steps. WHO's "expanded tables" (`references/data/who_*.csv`, converted
  from the official xlsx — see `DATA_SOURCES.md`) are tabulated daily
  (`age_days`, 0-1856) or at 0.1cm steps for weight-for-length, which is
  fine enough that most lookups land exactly on a row.
- In all cases the engine performs **linear interpolation of L, M, and S
  independently** between the two bracketing rows rather than snapping to
  the nearest one — this is standard practice (used by CDC's own SAS/R
  reference programs) and avoids small stairstep discontinuities at the
  CDC half-month/half-cm boundaries. For WHO's fine-grained tables this
  interpolation is nearly a no-op in practice but keeps the code path
  uniform across both standards.

## 6. Prematurity / gestational age (v1: flag-only)

v1 does **not** compute corrected age. If `gestational_age_weeks < 37` is
supplied and uncorrected `age_months < 24`, the engine still computes the
percentile against uncorrected chronological age (so a result is always
returned) but adds a `corrected_age_recommended` flag. Silently applying a
correction was rejected for v1: correction rules vary by clinical context
(cutoff at 24 months vs 36 months, whether to correct at all past a given
age) and getting it wrong is worse than clearly deferring to the caller.
See project plan §2/§10 for the decision record.

## 7. Deferred (not in v1)

- Condition-specific charts (Down syndrome, Turner syndrome, etc.)
- Growth velocity / trend analysis across multiple visits — v1 returns
  one `GrowthResult` per measurement, not a trajectory.

## Citations

- Cole TJ. "The LMS method for constructing normalized growth standards."
  *Eur J Clin Nutr.* 1990.
- CDC. "2000 CDC Growth Charts for the United States: Methods and
  Development." *Vital Health Stat 11(246).* 2002.
- Hales CM, Freedman DS, Akinbami L, Wei R, Ogden CL. "Evaluation of
  Alternative Body Mass Index (BMI) Metrics to Monitor Weight Status in
  Children and Adolescents With Extremely High BMI Using CDC BMI-for-age
  Growth Charts." *National Health Statistics Reports 2022;(197).*
  (https://www.cdc.gov/nchs/data/series/sr_02/sr02-197.pdf) — source of
  the extended-BMI half-normal method and its verified formula (§4).
- CDC. "Extended BMI-for-age growth charts" and data file with LMS/sigma
  parameters. 2022. (https://www.cdc.gov/growthcharts/extended-bmi.htm,
  https://www.cdc.gov/growthcharts/extended-bmi-data-files.htm)
- WHO. "WHO Child Growth Standards." 2006.
- CDC/AAP. Recommendation to use WHO growth standards for children
  0-<24 months and CDC growth charts for ages 2-19 years (2010 joint
  recommendation).
- CDC. "Modified z-scores in the CDC growth charts."
  (https://www.cdc.gov/growth-chart-training/media/pdfs/Modified-Z-scores-508.pdf)
  — source of the modified-z formula and BIV cutoffs (§4a), including the
  worked examples reproduced as golden test vectors.
- CDC. "SAS Program for CDC Growth Charts."
  (https://www.cdc.gov/growth-chart-training/hcp/computer-programs/sas.html)
  — source of the published BIV cutoff thresholds (§4a table).

Exact data file versions and URLs are tracked in `DATA_SOURCES.md`, not
here, so this document doesn't need updating every time a data file is
re-downloaded.
