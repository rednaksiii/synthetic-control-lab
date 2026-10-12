# California Proposition 99 (1988 tobacco tax): replication of Abadie, Diamond & Hainmueller (2010)

*Run 2026-10-12T08:43:38-04:00. Status: **REPLICATION (published specification)**.*

## Verdict (decision rule in the spec)

> FRAGILE: a meaningful reduction (-19) that fails robustness check(s): Placebo in time (1980) |mean gap|.

| check | value | threshold | passed |
|---|---|---|---|
| Pre-period fit (RMSPE) | 1.75 | <= 3.0 | yes |
| Effect size |mean post gap| | -19 | >= 10.0 in absolute value | yes |
| Placebo-in-space p-value (post/pre RMSPE ratio) | 0.0256 | <= 0.1 (minimum attainable 0.026) | yes |
| Placebo in time (1980) |mean gap| | -9.52 | <= 5.0 | no |
| Leave-one-out: no sign flips | range -20.7 to -17.5 | same sign as main estimate | yes |
| Synthetic DiD agrees in sign | -15.6 | same sign as main estimate | yes |

## Design

- Treated unit: **California**, first treated period **1989**, window 1970-2000
- Outcome: Per-capita cigarette sales (packs) (`cigsale`, transform `none`)
- Donor pool: 38 units; 0 excluded
- Predictors: lnincome (1980-1988), age15to24 (1980-1988), retprice (1980-1988), beer (1984-1988), cigsale (1988), cigsale (1980), cigsale (1975)
- V selection: `nested`

## Main estimate

- Pre-period RMSPE **1.75** (mean absolute error 1.04% of the treated level)
- Mean post-period gap **-19**; gap in final year -25.7
- Post/pre RMSPE ratio 11.4

Donor weights:

| donor | weight |
|---|---|
| Utah | 0.335 |
| Nevada | 0.236 |
| Montana | 0.202 |
| Colorado | 0.16 |
| Connecticut | 0.0679 |

Predictor balance:

| predictor | treated | synthetic | donor_mean | v |
|---|---|---|---|---|
| lnincome (1980-1988) | 10.1 | 9.86 | 9.83 | 7.57e-10 |
| age15to24 (1980-1988) | 17.4 | 17.4 | 17.3 | 0.135 |
| retprice (1980-1988) | 89.4 | 89.4 | 87.3 | 0.0483 |
| beer (1984-1988) | 24.3 | 24.2 | 23.7 | 5.63e-08 |
| cigsale (1988) | 90.1 | 91.7 | 114 | 8.52e-08 |
| cigsale (1980) | 120 | 120 | 138 | 5.74e-12 |
| cigsale (1975) | 127 | 127 | 137 | 0.817 |

## Placebo in space

The treated unit ranks **1 of 39** by post/pre RMSPE ratio: p = 0.0256 (smallest attainable 0.0256). Using |mean post gap| instead: p = 0.103.

| filter | n_units | p_value_ratio | p_value_mean_gap |
|---|---|---|---|
| pre-MSPE <= 20.0x treated | 33 | 0.0303 | 0.0606 |
| pre-MSPE <= 5.0x treated | 27 | 0.037 | 0.0741 |
| pre-MSPE <= 2.0x treated | 17 | 0.0588 | 0.0588 |

## Placebo in time

| fake_time | pre_rmspe | mean_placebo_gap | rmspe_ratio |
|---|---|---|---|
| 1.98e+03 | 2.09 | -9.52 | 4.62 |

- 1980: dropped predictors without data: beer (1984-1988), cigsale (1975)

## Leave-one-out

| dropped | dropped_weight | pre_rmspe | mean_post_gap |
|---|---|---|---|
| Utah | 0.335 | 2.58 | -17.5 |
| Nevada | 0.236 | 2.43 | -20.7 |
| Montana | 0.202 | 1.92 | -17.6 |
| Colorado | 0.16 | 1.78 | -19.3 |
| Connecticut | 0.0679 | 1.94 | -18.9 |

## Robustness: synthetic difference-in-differences

Average post-period effect; placebo standard errors (each control as pseudo-treated once).

| method | estimate | se | ci_low | ci_high |
|---|---|---|---|---|
| sdid | -15.6 | 9.37 | -34 | 2.76 |
| sc | -19.6 | 10.6 | -40.4 | 1.19 |
| did | -27.3 | 17.3 | -61.2 | 6.53 |

## Comparison with published results

21 of 21 items within tolerance. Source: ADH (2010) Tables 1-2 and text; Arkhangelsky, Athey, Hirshberg, Imbens & Wager (2021), AER 111(12), Table 1

| item | published | ours | tolerance | match |
|---|---|---|---|---|
| weight: Colorado | 0.164 | 0.16 | 0.02 | yes |
| weight: Connecticut | 0.069 | 0.0679 | 0.02 | yes |
| weight: Montana | 0.199 | 0.202 | 0.02 | yes |
| weight: Nevada | 0.234 | 0.236 | 0.02 | yes |
| weight: Utah | 0.334 | 0.335 | 0.02 | yes |
| synthetic lnincome (1980-1988) | 9.86 | 9.86 | 1.0% | yes |
| synthetic age15to24 (1980-1988) | 17.4 | 17.4 | 1.0% | yes |
| synthetic retprice (1980-1988) | 89.4 | 89.4 | 1.0% | yes |
| synthetic beer (1984-1988) | 24.2 | 24.2 | 1.0% | yes |
| synthetic cigsale (1988) | 91.6 | 91.7 | 1.0% | yes |
| synthetic cigsale (1980) | 120 | 120 | 1.0% | yes |
| synthetic cigsale (1975) | 127 | 127 | 1.0% | yes |
| Gap in 2000 (packs) | -26 | -25.7 | 2 | yes |
| Mean gap 1989-2000 (packs) | -20 | -19 | 1.5 | yes |
| Rank of California's post/pre RMSPE ratio among 39 states | 1 | 1 | 0 | yes |
| Synthetic DiD estimate | -15.6 | -15.6 | 0.1 | yes |
| SC estimate (synthdid definition) | -19.6 | -19.6 | 0.1 | yes |
| DiD estimate | -27.3 | -27.3 | 0.1 | yes |
| SDID placebo SE | 8.4 | 9.37 | 1.5 | yes |
| SC placebo SE | 9.9 | 10.6 | 1.5 | yes |
| DiD placebo SE | 17.7 | 17.3 | 1.5 | yes |

## Excluded donors

None.

## Caveats to address in the write-up

- **Anticipation**: could agents have reacted before the first treated period?
- **Spillovers**: could the policy have affected donor units (commuting, relocation, cross-border shopping)?
- **Concurrent shocks**: did anything else hit the treated unit (or key donors) around the same time?
- **Interpolation bias**: are the weighted donors similar to the treated unit, not just matched on average?
- **Specification search**: every deviation from the locked spec must be reported as exploratory.
