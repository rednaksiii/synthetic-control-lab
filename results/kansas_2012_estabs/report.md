# Kansas 2012 income tax cuts: private-sector establishments (secondary)

*Run 2026-10-12T10:31:29-04:00. Status: **CONFIRMATORY (matches locked spec)**.*

## Verdict (decision rule in the spec)

> INCONCLUSIVE: the pre-period fit fails the decision-rule threshold, so the synthetic unit is not a credible counterfactual.

| check | value | threshold | passed |
|---|---|---|---|
| Pre-period fit (RMSPE) | 1.13 | <= 1.0 | no |
| Effect size |mean post gap| | -3.36 | >= 2.0 in absolute value | yes |
| Placebo-in-space p-value (post/pre RMSPE ratio) | 0.333 | <= 0.1 (minimum attainable 0.033) | no |
| Placebo in time (2005) |mean gap| | 0.359 | <= 1.0 | yes |
| Leave-one-out: no sign flips | range -4.22 to -2.68 | same sign as main estimate | yes |
| Synthetic DiD agrees in sign | -4.1 | same sign as main estimate | yes |

## Design

- Treated unit: **KS**, first treated period **2012**, window 1990-2016
- Outcome: Private-sector establishments (UI-covered employers), log points relative to the state's 1990-2011 mean (x100) (`qcew_private_10_estabs__log_demeaned`, transform `log_demeaned`)
- Donor pool: 29 units; 21 excluded
- Predictors: qcew_private_10_estabs__log_demeaned (1990-1995), qcew_private_10_estabs__log_demeaned (1996-2001), qcew_private_10_estabs__log_demeaned (2002-2007), qcew_private_10_estabs__log_demeaned (2008-2011), ln_bea_real_gdp_pc (1997-2011), laus_unemployment_rate (1990-2011)
- V selection: `nested`

## Main estimate

- Pre-period RMSPE **1.13** (mean absolute error 43.1% of the treated level)
- Mean post-period gap **-3.36**; gap in final year -0.727
- Post/pre RMSPE ratio 3.22

Donor weights:

| donor | weight |
|---|---|
| CT | 0.256 |
| IN | 0.235 |
| SD | 0.214 |
| IA | 0.175 |
| NY | 0.0572 |
| AR | 0.0506 |
| WA | 0.0126 |

Predictor balance:

| predictor | treated | synthetic | donor_mean | v |
|---|---|---|---|---|
| qcew_private_10_estabs__log_demeaned (1990-1995) | -8.44 | -8.44 | -17 | 0.699 |
| qcew_private_10_estabs__log_demeaned (1996-2001) | -0.331 | -0.44 | -1.32 | 3.67e-06 |
| qcew_private_10_estabs__log_demeaned (2002-2007) | 3.25 | 3.77 | 9.31 | 1.07e-13 |
| qcew_private_10_estabs__log_demeaned (2008-2011) | 8.28 | 7.65 | 13.5 | 1.77e-06 |
| ln_bea_real_gdp_pc (1997-2011) | 10.8 | 10.9 | 10.8 | 5.54e-12 |
| laus_unemployment_rate (1990-2011) | 4.8 | 4.8 | 5.56 | 0.301 |

## Placebo in space

The treated unit ranks **10 of 30** by post/pre RMSPE ratio: p = 0.333 (smallest attainable 0.0333). Using |mean post gap| instead: p = 0.467.

| filter | n_units | p_value_ratio | p_value_mean_gap |
|---|---|---|---|
| pre-MSPE <= 20.0x treated | 29 | 0.345 | 0.448 |
| pre-MSPE <= 5.0x treated | 25 | 0.4 | 0.4 |
| pre-MSPE <= 2.0x treated | 17 | 0.471 | 0.353 |

## Placebo in time

| fake_time | pre_rmspe | mean_placebo_gap | rmspe_ratio |
|---|---|---|---|
| 2e+03 | 1.09 | 0.359 | 1.4 |

- 2005: dropped predictors without data: qcew_private_10_estabs__log_demeaned (1990-1995)

## Leave-one-out

| dropped | dropped_weight | pre_rmspe | mean_post_gap |
|---|---|---|---|
| CT | 0.256 | 1.21 | -4.22 |
| IN | 0.235 | 1.17 | -3.85 |
| SD | 0.214 | 1.16 | -3.43 |
| IA | 0.175 | 1.16 | -2.68 |
| NY | 0.0572 | 1.12 | -3.38 |
| AR | 0.0506 | 1.18 | -3.68 |
| WA | 0.0126 | 1.13 | -3.48 |

## Robustness: synthetic difference-in-differences

Average post-period effect; placebo standard errors (each control as pseudo-treated once).

| method | estimate | se | ci_low | ci_high |
|---|---|---|---|---|
| sdid | -4.1 | 3.16 | -10.3 | 2.09 |
| sc | -3.34 | 4.02 | -11.2 | 4.54 |
| did | -9.29 | 9.41 | -27.7 | 9.15 |

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
