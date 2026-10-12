# Pre-registration

This file is the human-readable half of each study's pre-registration. The machine-readable half
is the spec in `specs/`. **The spec is binding**: `python -m synthpolicy lock <spec>` records its
SHA-256 hash and a timestamp in `<spec>.lock.json`, and every run reports whether the spec it used
still matches that lock. Results from an unlocked spec, or one edited after locking, are labelled
**EXPLORATORY** in the report and the dashboard.

Rules for every study:

1. Write the spec and this section **before** looking at any post-treatment outcome data for the
   treated unit, and lock it before the first `run`.
2. Any later change (outcome, window, donor pool, predictors, thresholds) is a *deviation*. It is
   made in a new spec with its own name, logged in that study's deviation table below, and its
   results are reported as exploratory next to, not instead of, the locked results.
3. Results are reported whatever they show, including "no detectable effect" and "inconclusive".

---

## Part A: Validation study. California Proposition 99 (replication)

**Spec:** `specs/prop99.toml` (status `replication`)

**Purpose.** Show that this code reproduces a published synthetic control analysis before using it
on a new question. Every design choice is taken from Abadie, Diamond & Hainmueller (2010), *JASA*
105(490), "Synthetic Control Methods for Comparative Case Studies". None was chosen by us.

| Item | Choice (from the paper) |
|---|---|
| Treated unit | California |
| Policy | Proposition 99: passed November 1988, raising the cigarette excise tax by 25¢ per pack from January 1989 and funding anti-smoking programmes |
| First treated year | 1989 |
| Window | 1970–2000 (19 pre-treatment years, 12 post-treatment years) |
| Outcome | Per-capita cigarette sales in packs (`cigsale`), untransformed |
| Donor pool | 38 states. The paper excludes states with large tobacco-control programmes or tax increases of 50¢ or more during 1989–2000 (AK, AZ, FL, HI, MA, MD, MI, NJ, NY, OR, WA) and DC |
| Predictors | ln GDP per capita, % aged 15–24, retail price (each averaged over 1980–88); beer consumption per capita (1984–88); cigarette sales in 1975, 1980 and 1988 |
| V selection | Nested optimisation: minimise the pre-period (1970–88) outcome MSPE |
| Inference | Placebo in space (all 38 donors), with pre-MSPE filters at 20×, 5× and 2× |

**Replication targets** (encoded in the spec and checked on every run):
the donor weights in ADH Table 2 (CO 0.164, CT 0.069, MT 0.199, NV 0.234, UT 0.334) to within
±0.02; the synthetic-California predictor means in ADH Table 1 to within 1%; a gap of about −26
packs by 2000; an average gap of almost −20 packs over 1989–2000; California ranking 1st of 39 on
the post/pre RMSPE ratio (p = 1/39 ≈ 0.026); and the Arkhangelsky et al. (2021, *AER* Table 1)
estimates SDID −15.6, SC −19.6 and DiD −27.3.

**Added by us** (not in the paper): a placebo-in-time test at 1980, leave-one-out refits, SDID as
a robustness comparison, and the decision rule below.

| Decision rule | Threshold |
|---|---|
| Pre-period fit | RMSPE ≤ 3 packs |
| Meaningful effect | \|mean 1989–2000 gap\| ≥ 10 packs |
| Significance | Unfiltered placebo-in-space p ≤ 0.10 |
| Placebo in time (1980) | \|mean 1980–88 placebo gap\| ≤ 5 packs |
| Leave-one-out / SDID | no sign change |

*Disclosure:* this decision rule was written after the main Prop 99 estimate had been computed
(that estimate is published anyway) but **before** the placebo-in-time, leave-one-out and SDID
checks were run.

### Outcome (12 October 2026)

All 21 replication targets are matched. Weights: Utah 0.335, Nevada 0.236, Montana 0.202,
Colorado 0.160, Connecticut 0.068. Gap in 2000 −25.7; mean gap −19.0; California ranks 1st of 39
(p = 0.026); SDID −15.60, SC −19.62, DiD −27.35.

Under the decision rule the result is **FRAGILE**: the 1980 placebo-in-time gap is −9.5 packs, which
exceeds the 5-pack threshold. An exploratory follow-up (not part of the locked rule) found that every
backdated placebo, at 1980, 1983 and 1985 and under each way of handling the predictors, shows
California 1.1–9.5 packs below its synthetic (median about 4) before Proposition 99 existed. So
California's consumption was already falling faster than its donors' in the 1980s. The headline
−19 pack effect is still several times larger, but part of it may continue that earlier trend. The threshold was **not** relaxed after
this was seen. The finding is reported as it stands: it is a known limitation of the original study,
not a code error. The code itself is validated by the 21 matched targets.

---

## Part B: Kansas 2012 income tax cuts (locked 12 October 2026)

**Specs:** `specs/kansas_2012.toml` (primary), `specs/kansas_2012_gdp.toml` and
`specs/kansas_2012_estabs.toml` (secondary).

> **Status: LOCKED** on 12 October 2026, before any Kansas outcome results were computed. Claude
> drafted the plan and verified its facts (sources below); the analyst chose to accept the remaining
> draft choices (outcomes, window, thresholds, `tie_break`) and lock. The lock files
> `specs/kansas_2012*.lock.json` hold each spec's SHA-256.

### Question

Did the 2012 Kansas income tax cuts change private-sector employment in Kansas during 2012–2016,
compared with what a synthetic Kansas built from comparable states would have experienced?

This is treated as a question about method and evidence, not a test of a political position. "The
evidence is weaker than either side claims" is an acceptable and publishable answer.

### Policy and timing

- **January 2012:** the governor proposes the plan in his State of the State address.
  **22 May 2012:** Senate Substitute for H.B. 2117 is signed. **Tax year 2013:** it takes effect. The top personal rate falls from 6.45% to 4.9%, and
  pass-through business income (LLCs, S corporations, sole proprietors) is exempted.
- **First treated year: 2012.** The plan was public from January and law from May 2012, so firms
  could react during 2012 (anticipation). The 2013 effective date is a robustness alternative.
- **6 June 2017:** the legislature overrides the veto of S.B. 30, which ends the pass-through
  exemption and raises rates retroactively to 1 January 2017.
  **The post-period therefore ends in 2016**, and 2017 onward is never analysed.
- **Pre-period:** 1990–2011 (22 years) for QCEW outcomes; 1997–2011 (15 years) for BEA GDP.

### Outcomes

| Role | Outcome | Source | Transform |
|---|---|---|---|
| **Primary** | Private-sector employment, all industries, annual average | BLS QCEW (`qcew_private_10_emp`) | 100 × (ln y − the state's 1990–2011 mean of ln y) |
| Secondary | Real GDP per capita | BEA SAGDP1 / SAINC1 (`bea_real_gdp_pc`) | as above, with a 1997–2011 base |
| Secondary | Private-sector establishments (UI-covered employers) | BLS QCEW (`qcew_private_10_estabs`) | as above |

The transform removes each state's level, so the synthetic unit is matched on *growth paths*, not
size. Gaps are in log points, roughly percent. Conclusions rest on the primary outcome. The
secondary outcomes are descriptive, and with three outcomes at least one "significant" result at
α = 0.10 has a substantial chance of arising by luck.

### Donor pool rules

From the 50 states and DC, minus Kansas:

1. **Bordering states** (MO, NE, OK, CO): excluded for spillover risk. The Kansas City metro
   straddles the KS–MO line, and the exemption gave firms a reason to relocate across it.
2. **Energy-dependent states**: excluded if mining, quarrying and oil-and-gas extraction exceeded 8%
   of 2011 GDP (BEA SAGDP2). Today that removes AK, LA, ND, NM, TX, WV and WY. The 2014–16 oil
   price collapse would otherwise contaminate the counterfactual. (Kansas: 1.6%.)
3. **Structural:** DC (a city) and HI (a non-contiguous island economy).
4. **Concurrent tax changes:** a state is excluded if the top marginal rate on wage and business
   income faced by a high earner (including temporary surcharges and optional flat-tax
   alternatives) varied by at least 0.5 percentage points across tax years 2010–2016, or if it
   enacted a pass-through business income exemption or deduction effective 2011–2016.
   Verified 12 October 2026 (see "Sources" below):

   | State | Change | Excluded |
   |---|---|---|
   | CA | Proposition 30: top rate 10.3% → 13.3% from 2012 | yes |
   | HI | temporary 11% top rate expired: 8.25% from 2016 | yes (also rule 3) |
   | IL | flat rate 3% → 5% (2011) → 3.75% (2015) | yes |
   | MD | 6.25% millionaire bracket expired after 2010 (5.5% in 2011) | yes |
   | ME | 8.5% → 7.95% (2013) → 7.15% (2016) | yes |
   | MN | new 9.85% top bracket from 2013 (was 7.85%) | yes |
   | NC | top 7.75% → flat 5.8% (2014) → 5.75% (2015) | yes |
   | ND | repeated cuts, 2011–2015 | yes (also rule 2) |
   | OH | 5.925% → 4.997% (2013–2016) plus small-business income deduction from 2013 | yes |
   | OR | Measure 66's temporary 11% top rate (2009–2011) replaced by 9.9% from 2012 | yes |
   | CT | 6.5% → 6.7% (2011) → 6.99% (2015): 0.49 points in total | no (below 0.5) |
   | NY | 8.97% (2009–2011) → 8.82% from 2012 | no (0.15) |
   | RI | 2011 reform cut the regular top rate 9.9% → 5.99%, but high earners could already elect the 6% alternative flat tax, so their rate barely changed | no |
   | VT, NE | statutory top rates unchanged (8.95%, 6.84%) | no (NE excluded by rule 1) |
   | TN, NH | tax only interest and dividends, not wages or business income | no |

   The draft list (NC, OH, CA, MN, IL, ME) was confirmed; **MD and OR were added**. NBER TAXSIM's
   effective state rates for a $1.5M earner were used as a cross-check to catch changes, but not as
   the test itself: they move with federal law (for example the 2013 federal changes) even where a
   state's own rates did not.
5. States missing the outcome in any year of the window.

Resulting pool (29): AL AR AZ CT DE FL GA IA ID IN KY MA MI MS MT NH NJ NV NY PA RI SC SD TN UT VA
VT WA WI. The smallest attainable placebo p-value is 1/30 ≈ 0.033.

**Sources.** Kansas: Kansas Department of Revenue notices
([12-05](https://ksrevenue.gov/taxnotices/notice12-05.pdf)); Tax Foundation on the
[January 2012 proposal](https://taxfoundation.org/kansas-governor-proposes-significant-income-tax-reform-reducing-rate-645-49)
and the [pass-through exemption](https://taxfoundation.org/not-kansas-anymore-income-taxes-pass-through-businesses-eliminated);
EY on the [2017 repeal](https://taxnews.ey.com/news/2017-0927-over-governors-veto-new-kansas-law-repeals-the-personal-income-tax-exemption-for-pass-through-entity-income-modifies-other-provisions)
and the [Kansas Legislature vote record](https://kslegislature.gov/li_2018/b2017_18/measures/vote_view/je_20170606201241_068283).
Other states: [NBER TAXSIM top state rates, 1977–2024](https://taxsim.nber.org/state-rates/maxrate.html);
Tax Foundation, [State Individual Income Tax Rates and Brackets 2016](https://taxfoundation.org/data/all/state/state-individual-income-tax-rates-and-brackets-2016/);
Maryland DLS [fiscal note HB 1070 (2011)](https://mgaleg.maryland.gov/2011rs/fnotes/bil_0000/hb1070.pdf);
Oregon LRO [Measures 66–67 report](https://www.oregonlegislature.gov/lro/Documents/11-19-09%20RR%206-09%20Measures%2066-67.pdf);
Minnesota Revenue [HF 677 (2013) summary](https://www.revenue.state.mn.us/sites/default/files/2013-05/hf0677%28sf0552%29_3.pdf);
Tax Foundation on the [Rhode Island 2010 reform](https://taxfoundation.org/blog/rhode-island-approves-tax-reform-package/).

### Method

- **Predictors:** the transformed outcome averaged over 1990–95, 1996–2001, 2002–07 and 2008–11;
  ln real GDP per capita (1997–2011); unemployment rate (1990–2011). Using sub-period averages
  instead of every lag keeps the covariates from being ignored.
- **V selection:** nested (ADH): minimise pre-period outcome MSPE. W ≥ 0 and Σ W = 1.
- **Tie-break (`tie_break = 1e-4`):** Kansas is a middle-of-the-distribution state, so it probably
  lies inside the donors' convex hull on these predictors. Classic ADH weights are then not unique
  and depend on the solver. The draft breaks ties by pre-period outcome fit. This is a slightly
  different estimator from pure ADH (on Prop 99 it moves the mean gap from −19.0 to −19.4 and
  reshuffles the weights), so it has to be decided before running. Set it to 0 for pure ADH, in
  which case the run will warn if the weights are not identified.
- **Inference:** placebo in space over all 29 donors, using the unfiltered post/pre RMSPE ratio
  (primary) and 20×/5×/2× pre-MSPE filters (reported). Placebo in time at 2005, fitted on
  1990–2004 only. Leave-one-out over every donor with weight above 0.001.
- **Robustness:** synthetic DiD, plus synthdid-style SC and DiD, with placebo standard errors.

### Decision rule: what counts as a meaningful effect (primary outcome)

| Check | Threshold |
|---|---|
| Pre-period fit | RMSPE ≤ 1.0 log point; otherwise **INCONCLUSIVE** and no effect is claimed |
| Meaningful size | \|mean 2012–2016 gap\| ≥ 2.0 log points (≈ 2% of private employment, ≈ 21,000 jobs) |
| Significance | placebo p ≤ 0.10 |
| Placebo in time | \|mean 2005–2011 placebo gap\| ≤ 1.0 log point |
| Leave-one-out | no sign change in the mean gap |
| SDID | same sign as the SC estimate |

The verdict is computed mechanically from these checks: **MEANINGFUL EFFECT** if all pass;
**FRAGILE** if size and significance pass but a robustness check fails; **UNUSUAL BUT SMALL** if
significant but below 2.0; **NO DETECTABLE EFFECT** if p > 0.10; **INCONCLUSIVE** if the fit
fails. Both signs count: a 2% employment *loss* is as meaningful as a 2% gain.

### Known threats (to be discussed in the write-up whatever the result)

- **Anticipation:** the announcement in January 2012 is handled by treating 2012 as exposed.
- **Spillovers:** relocation into Kansas from Missouri would inflate the effect; the bordering
  states are excluded, but spillovers can reach further.
- **Concurrent shocks:** the 2014–16 farm-income decline (Kansas is agriculture-heavy, as are
  donors like IA and SD) and aerospace employment in Wichita.
- **Fiscal response:** the cuts came with spending cuts (schools, highways) that are part of the
  treatment. The estimate is of the whole package.
- **Measurement:** QCEW counts UI-covered employers. Tax-motivated reclassification of employees as
  pass-through owners would *reduce* measured employment without any real change.
- **Short post-period:** 5 years, so long-run effects cannot be measured.

### Checklist before locking (analyst)

- [x] Verify the policy dates and rates above against primary sources.
- [x] Verify or replace the concurrent-tax-change exclusion list (rule 4), citing a source.
- [x] Confirm the primary outcome, the 2012 first treated year, and the 2016 end of the window.
- [x] Confirm the decision thresholds (2.0 / 1.0 / 0.10 / 1.0).
- [x] Decide on `tie_break` (kept at 1e-4).
- [x] Lock each spec.

### Outcome (12 October 2026; all three runs CONFIRMATORY, matching the locked specs)

**Primary: private-sector employment. Verdict: NO DETECTABLE EFFECT.**
Synthetic Kansas is WA 0.31, MS 0.31, NH 0.15, PA 0.10, MA 0.07, UT 0.06 and MI 0.01, with a
pre-period fit of 0.88 log points (passes ≤ 1.0). After 2012 Kansas grew a little more slowly than its
twin: −1.7 log points on average over 2012–2016, widening to −3.8 by 2016. That is below the 2.0
threshold for a meaningful effect. It is also ordinary: Kansas ranks 17th of 30 among the placebos
(p = 0.57). The 2005 placebo in time shows a −3.4 gap before any policy existed, so a shortfall of
this size happens for Kansas even without a tax change. The estimate is stable when donors are
dropped (−2.1 to −1.5), and the other estimators agree in sign but are not distinguishable from zero:
SDID −1.2 (SE 1.9), SC −3.1 (2.8), DiD −2.0 (7.3). So there is no evidence of the promised job boost,
and the hint of slower growth is too small and too common among placebos to call an effect.

**Secondary: real GDP per capita. Verdict: NO DETECTABLE EFFECT.** The mean gap is −1.1 and Kansas
ranks 29th of 30 (p = 0.97). The 2006 placebo in time gap is large (+6.8), and dropping Washington
flips the sign, so this outcome is too noisy to say anything either way.

**Secondary: private establishments. Verdict: INCONCLUSIVE** (pre-period fit 1.13 > 1.0). Kansas's
establishment count falls 4.2 log points against its twin in a single year, 2012, then converges back
by 2016. A one-year step like that looks more like an administrative or reporting change in the QCEW
establishment counts than a policy response. It is worth checking with BLS before anyone interprets it.

### Deviation log

| Date | Spec | Change | Reason |
|---|---|---|---|
| 2026-10-12 (before locking) | all three Kansas specs | rule 4 list verified; MD and OR added; bill name corrected to "Senate Substitute for H.B. 2117" | fact check before lock, no results seen |
