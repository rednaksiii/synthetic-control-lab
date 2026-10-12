# Kansas 2012 income tax cuts: private-sector employment

*Run 2026-10-12T10:30:13-04:00. Status: **CONFIRMATORY (matches locked spec)**.*

## Verdict (decision rule in the spec)

> NO DETECTABLE EFFECT: the estimated gap (-1.73) is not unusual relative to the placebo distribution (p = 0.567).

| check | value | threshold | passed |
|---|---|---|---|
| Pre-period fit (RMSPE) | 0.877 | <= 1.0 | yes |
| Effect size |mean post gap| | -1.73 | >= 2.0 in absolute value | no |
| Placebo-in-space p-value (post/pre RMSPE ratio) | 0.567 | <= 0.1 (minimum attainable 0.033) | no |
| Placebo in time (2005) |mean gap| | -3.36 | <= 1.0 | no |
| Leave-one-out: no sign flips | range -2.12 to -1.46 | same sign as main estimate | yes |
| Synthetic DiD agrees in sign | -1.16 | same sign as main estimate | yes |

## Design

- Treated unit: **KS**, first treated period **2012**, window 1990-2016
- Outcome: Private-sector employment, log points relative to the state's 1990-2011 mean (x100) (`qcew_private_10_emp__log_demeaned`, transform `log_demeaned`)
- Donor pool: 29 units; 21 excluded
- Predictors: qcew_private_10_emp__log_demeaned (1990-1995), qcew_private_10_emp__log_demeaned (1996-2001), qcew_private_10_emp__log_demeaned (2002-2007), qcew_private_10_emp__log_demeaned (2008-2011), ln_bea_real_gdp_pc (1997-2011), laus_unemployment_rate (1990-2011)
- V selection: `nested`

## Main estimate

- Pre-period RMSPE **0.877** (mean absolute error 14.9% of the treated level)
- Mean post-period gap **-1.73**; gap in final year -3.81
- Post/pre RMSPE ratio 2.37

Donor weights:

| donor | weight |
|---|---|
| WA | 0.314 |
| MS | 0.308 |
| NH | 0.146 |
| PA | 0.0987 |
| MA | 0.065 |
| UT | 0.0567 |
| MI | 0.0115 |

Predictor balance:

| predictor | treated | synthetic | donor_mean | v |
|---|---|---|---|---|
| qcew_private_10_emp__log_demeaned (1990-1995) | -12.7 | -12.2 | -13.3 | 8.18e-12 |
| qcew_private_10_emp__log_demeaned (1996-2001) | 3.35 | 2.87 | 2.25 | 1.28e-09 |
| qcew_private_10_emp__log_demeaned (2002-2007) | 5.63 | 5.63 | 7.22 | 0.0794 |
| qcew_private_10_emp__log_demeaned (2008-2011) | 5.59 | 5.59 | 5.77 | 0.629 |
| ln_bea_real_gdp_pc (1997-2011) | 10.8 | 10.8 | 10.8 | 0.292 |
| laus_unemployment_rate (1990-2011) | 4.8 | 6.02 | 5.56 | 1.09e-10 |

## Placebo in space

The treated unit ranks **17 of 30** by post/pre RMSPE ratio: p = 0.567 (smallest attainable 0.0333). Using |mean post gap| instead: p = 0.4.

| filter | n_units | p_value_ratio | p_value_mean_gap |
|---|---|---|---|
| pre-MSPE <= 20.0x treated | 28 | 0.607 | 0.357 |
| pre-MSPE <= 5.0x treated | 27 | 0.593 | 0.333 |
| pre-MSPE <= 2.0x treated | 25 | 0.6 | 0.28 |

## Placebo in time

| fake_time | pre_rmspe | mean_placebo_gap | rmspe_ratio |
|---|---|---|---|
| 2e+03 | 0.505 | -3.36 | 6.77 |

- 2005: dropped predictors without data: qcew_private_10_emp__log_demeaned (1990-1995)

## Leave-one-out

| dropped | dropped_weight | pre_rmspe | mean_post_gap |
|---|---|---|---|
| WA | 0.314 | 0.918 | -1.46 |
| MS | 0.308 | 0.924 | -1.72 |
| NH | 0.146 | 0.885 | -2.12 |
| PA | 0.0987 | 0.88 | -1.66 |
| MA | 0.065 | 0.882 | -1.56 |
| UT | 0.0567 | 0.837 | -2.12 |
| MI | 0.0115 | 0.878 | -1.61 |

## Robustness: synthetic difference-in-differences

Average post-period effect; placebo standard errors (each control as pseudo-treated once).

| method | estimate | se | ci_low | ci_high |
|---|---|---|---|---|
| sdid | -1.16 | 1.94 | -4.96 | 2.65 |
| sc | -3.09 | 2.77 | -8.52 | 2.34 |
| did | -1.99 | 7.28 | -16.3 | 12.3 |

## Excluded donors

| unit | reason |
|---|---|
| AK | rule: bea_mining_share = 0.3217 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| CA | excluded: concurrent tax change: Proposition 30 raised the top rate 10.3% -> 13.3% from 2012 |
| CO | borders KS (spillover risk) |
| DC | excluded: city, not comparable to a state economy |
| HI | excluded: non-contiguous island economy (tourism, military); also top rate 11% -> 8.25% in 2016 |
| IL | excluded: concurrent tax change: flat rate 3% -> 5% in 2011, cut to 3.75% in 2015 |
| LA | rule: bea_mining_share = 0.08733 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| MD | excluded: concurrent tax change: 6.25% millionaire bracket expired after 2010 (5.5% in 2011, 5.75% from 2012) |
| ME | excluded: concurrent tax change: top rate 8.5% -> 7.95% (2013) -> 7.15% (2016) |
| MN | excluded: concurrent tax change: new 9.85% top bracket from 2013 (was 7.85%) |
| MO | borders KS (spillover risk) |
| NC | excluded: concurrent tax change: graduated tax (top 7.75%) replaced by flat 5.8% in 2014, 5.75% in 2015 |
| ND | rule: bea_mining_share = 0.1218 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| NE | borders KS (spillover risk) |
| NM | rule: bea_mining_share = 0.1091 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| OH | excluded: concurrent tax change: top rate 5.925% -> 4.997% (2013-2016) and small-business income deduction from 2013 |
| OK | borders KS (spillover risk) |
| OR | excluded: concurrent tax change: temporary 11% top rate (2009-2011) replaced by 9.9% from 2012 |
| TX | rule: bea_mining_share = 0.1084 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| WV | rule: bea_mining_share = 0.1341 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |
| WY | rule: bea_mining_share = 0.3281 in 2011 (> 0.08) - energy-dependent economy; the 2014-16 oil price collapse would contaminate the counterfactual |

## Caveats to address in the write-up

- **Anticipation**: could agents have reacted before the first treated period?
- **Spillovers**: could the policy have affected donor units (commuting, relocation, cross-border shopping)?
- **Concurrent shocks**: did anything else hit the treated unit (or key donors) around the same time?
- **Interpolation bias**: are the weighted donors similar to the treated unit, not just matched on average?
- **Specification search**: every deviation from the locked spec must be reported as exploratory.
