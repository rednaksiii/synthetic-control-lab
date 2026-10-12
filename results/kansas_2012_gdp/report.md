# Kansas 2012 income tax cuts: real GDP per capita (secondary)

*Run 2026-10-12T10:30:38-04:00. Status: **CONFIRMATORY (matches locked spec)**.*

## Verdict (decision rule in the spec)

> NO DETECTABLE EFFECT: the estimated gap (-1.12) is not unusual relative to the placebo distribution (p = 0.967).

| check | value | threshold | passed |
|---|---|---|---|
| Pre-period fit (RMSPE) | 1.31 | <= 1.5 | yes |
| Effect size |mean post gap| | -1.12 | >= 2.0 in absolute value | no |
| Placebo-in-space p-value (post/pre RMSPE ratio) | 0.967 | <= 0.1 (minimum attainable 0.033) | no |
| Placebo in time (2006) |mean gap| | 6.82 | <= 1.0 | no |
| Leave-one-out: no sign flips | range -1.26 to 0.921 | same sign as main estimate | no |
| Synthetic DiD agrees in sign | -0.2 | same sign as main estimate | yes |

## Design

- Treated unit: **KS**, first treated period **2012**, window 1997-2016
- Outcome: Real GDP per capita, log points relative to the state's 1997-2011 mean (x100) (`bea_real_gdp_pc__log_demeaned`, transform `log_demeaned`)
- Donor pool: 29 units; 21 excluded
- Predictors: bea_real_gdp_pc__log_demeaned (1997-2001), bea_real_gdp_pc__log_demeaned (2002-2007), bea_real_gdp_pc__log_demeaned (2008-2011), ln_bea_real_gdp_pc (1997-2011), laus_unemployment_rate (1997-2011)
- V selection: `nested`

## Main estimate

- Pre-period RMSPE **1.31** (mean absolute error 32% of the treated level)
- Mean post-period gap **-1.12**; gap in final year 1.15
- Post/pre RMSPE ratio 1.28

Donor weights:

| donor | weight |
|---|---|
| WA | 0.518 |
| MT | 0.347 |
| SD | 0.0891 |
| UT | 0.0456 |

Predictor balance:

| predictor | treated | synthetic | donor_mean | v |
|---|---|---|---|---|
| bea_real_gdp_pc__log_demeaned (1997-2001) | -8.33 | -8.47 | -7.4 | 0.743 |
| bea_real_gdp_pc__log_demeaned (2002-2007) | 1.02 | 1.62 | 3.19 | 0.000835 |
| bea_real_gdp_pc__log_demeaned (2008-2011) | 8.88 | 8.16 | 4.46 | 0.204 |
| ln_bea_real_gdp_pc (1997-2011) | 10.8 | 10.8 | 10.8 | 0.0361 |
| laus_unemployment_rate (1997-2011) | 4.93 | 5.56 | 5.46 | 0.0159 |

## Placebo in space

The treated unit ranks **29 of 30** by post/pre RMSPE ratio: p = 0.967 (smallest attainable 0.0333). Using |mean post gap| instead: p = 0.9.

| filter | n_units | p_value_ratio | p_value_mean_gap |
|---|---|---|---|
| pre-MSPE <= 20.0x treated | 30 | 0.967 | 0.9 |
| pre-MSPE <= 5.0x treated | 28 | 0.964 | 0.893 |
| pre-MSPE <= 2.0x treated | 25 | 0.96 | 0.88 |

## Placebo in time

| fake_time | pre_rmspe | mean_placebo_gap | rmspe_ratio |
|---|---|---|---|
| 2.01e+03 | 0.375 | 6.82 | 19 |

- 2006: dropped predictors without data: bea_real_gdp_pc__log_demeaned (1997-2001)

## Leave-one-out

| dropped | dropped_weight | pre_rmspe | mean_post_gap |
|---|---|---|---|
| WA | 0.518 | 1.67 | 0.921 |
| MT | 0.347 | 1.37 | -0.444 |
| SD | 0.0891 | 1.31 | -0.857 |
| UT | 0.0456 | 1.31 | -1.26 |

## Robustness: synthetic difference-in-differences

Average post-period effect; placebo standard errors (each control as pseudo-treated once).

| method | estimate | se | ci_low | ci_high |
|---|---|---|---|---|
| sdid | -0.2 | 2.54 | -5.19 | 4.79 |
| sc | -0.457 | 3.66 | -7.63 | 6.72 |
| did | 5.26 | 6.13 | -6.76 | 17.3 |

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
