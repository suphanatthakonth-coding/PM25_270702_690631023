
## Chiang Mai PM2.5: prediction, evidence and decisions

SUPHANATTHAKON THOBSRI | Student ID: 690631023

270702 Data Science Programming | 24 October 2026 | Four notebooks, twelve settings


## 1 Problem background

- Fine particulate pollution is associated with respiratory and cardiovascular disease; children are a particularly affected group [1]. A school needs lead time to review outdoor activities and communicate with families. A useful forecast requires timely inputs as well as accuracy.

- Chiang Mai source-apportionment research identifies biomass burning as important during haze periods [2]. This motivates a regional fire predictor, but does not guarantee incremental forecast skill.

- This lab examines severity, timing, tomorrow prediction and an actionable recommendation for one Chiang Mai receptor. Modeled CAMS values are distinguished from measured station exposure throughout.


## Study contract

| Item | Definition |

| Location | 18.7883 N, 98.9853 E; one receptor |

| Study targets | 2024-01-01 to 2025-12-31; earlier source days are buffers |

| Issue / target | D 07:00 Thailand -> modeled daily profile P(D+1), local 00:00-24:00 |

| Fixed threshold | 37.5 ug/m3; modeled exceedance, not an official measured violation |

| Scope | Nominal-source-clock-constrained retrospective benchmark; actual original publication/revision not certified |


## Key findings: baseline first

- The common modeling cohort has 687 of 731 target dates. Test covers all 365 days of calendar 2025.

- Persistence test MAE is 6.282; direct CAMS reference MAE is 3.739. Validation selects H1_3d, whose test MAE is 6.137.

- Selected-model missed exceedances: 23/30; false alerts: 8. Accuracy and operational readiness are separate conclusions.

Evidence: model_scores.csv; selection.json; coverage_summary.json; source_time_contract.json.


## 2 Approach | questions and expected contributions

Question: what do weather and regional fire histories add beyond PM history, and does a 3-, 5- or 7-day history help? All settings use the same dates and fixed target definition.

| Group | Inputs | Paired question at each k | Features: 3 / 5 / 7 |

| H1 | PM | H1 - persistence | 9 / 15 / 21 |

| H2 | PM + weather | H2 - H1 | 30 / 50 / 70 |

| H3 | PM + fire | H3 - H1 | 15 / 25 / 35 |

| H4 | PM + weather + fire | H4 - H2; H4 - H3 | 36 / 60 / 84 |

- Subquestions a/b/c mean k=3/5/7. PM persistence motivates H1; meteorological transport/removal motivates H2; biomass-burning activity motivates H3. H4 tests each addition conditionally. Expectations are working hypotheses, not required positive findings.

- A short window may follow recent conditions; a longer one may capture persistence but adds correlated inputs. Validation selects windows, while all three test results remain visible.


## Development from the original model

| Initial approach | Current approach |

| Baselines and temporal evaluation already existed | Baselines are retained; source clocks and label maturity are explicit. |

| Original code used several lags and rolling windows | Compare exactly 3/5/7 days within each of four source groups. |

| Covered-day zeros and unknown fire days were distinguished | Native GFAS values are distinguished from missing data, with separate QC. |

| Metrics and configurations were exported | Receipts link sources, data and models; prediction and SQL checks are reproducible. |

- Structural progress is clearer timing, provenance and matched comparisons. Better accuracy must be demonstrated separately. The original H1-H4 had different fire-specific meanings; the labels have different meanings in the initial and current experiments.

Evidence: reference/model_development_trace.csv; original_notebook_inventory.json; Appendix F.


## 3 Method | workflow and information separation

Figure 1. Shared notebook/script workflow. The availability branch keeps operational prediction blocked; technical checks are not original-release evidence.

Figure: outputs/figures/08_workflow.png

- Freeze -> commit predictions without test answers -> open answers and score. The SQL store preserves real records and receipts; it is not an independent ground-truth dataset.

- This historical dataset was previously inspected. Interface isolation does not turn it into an untouched or prospective trial.


## 3 Method | sources, target and time availability

| Source / role | Native product and clock | At issue D 07:00 Thailand |

| PM history / target | ADS CAMS mc/fc/0001; run d-1 at 12 UTC; leads 5-28 form P(d) | History P(D-1)..P(D-k). Target P(D+1) is later verification output. |

| Weather history | Open-Meteo gfs_global previous_day1 forecast values; local daily summaries | Days D-1..D-k. Fixed forecast offset is not an observed public-release timestamp. |

| Fire history | GFAS v1.2 daily UTC means; FRP density and observation-opportunity QC | UTC days D-2..D-(k+1), reflecting the documented next-day 07 UTC schedule. |

| Provider reference | CAMS run D-1 at 12 UTC, leads 29-52 | Target D+1, nominally released 2h before issue; never a learned feature. |

| API / dataset | Request identity |

| ADS /api | https://ads.atmosphere.copernicus.eu/api; datasets: cams-global-atmospheric-composition-forecasts and cams-global-fire-emissions-gfas. |

| Public weather /v1/forecast | https://previous-runs-api.open-meteo.com/v1/forecast; models=gfs_global, six *_previous_day1 fields, timezone=UTC, wind_speed_unit=ms. |

| Request periods | PM runs: 2023-12-23..2025-12-30; GFAS UTC days: 2023-12-23..2025-12-31; weather UTC hours: 2024-01-01..2025-12-31. Exact bounds/areas are preserved in raw plans and manifests. |


## Explicit clock example

- For issue 1 January 2025 at 07:00 Thailand (=00 UTC), predict 2 January local 00:00-24:00. Target starts 17h and ends 41h after issue. The PM/weather 7-day history is 25-31 December; GFAS UTC history is 24-30 December.

- CAMS 12 UTC is scheduled by 22 UTC; GFAS daily analysis by 07 UTC. Latest PM history has 26h nominal margin, fire 17h, and provider reference 2h. ADS delivery exceptions remain possible [3,4].

- Section 6.2: source-day and target offsets are checked; labels must mature before evaluation and transforms fit within training folds. Documented source clocks inform the offsets. Exact historical public-release/revision was not audited, so operational replay is not certified.

Evidence: source_time_contract.json; raw transfer_receipt.json; timezone_examples.csv; study_contract.json.


## 3 Method | preparation and row reconciliation C1-C3


## C1-C2: preserve calendars, units and one-to-one joins

| Step | Rows / decision |

| Study target calendar | 731 days across full 2024-2025 |

| Value-complete PM/fire/weather 7-day histories | 704; first usable target 28 January 2024 |

| Declared source-advisory dependency quarantine | 15 targets: 9-23 August 2024; conservative, not confirmed local contamination |

| Outer label-maturity purges | 30 September and 31 December 2024: 2 days |

| Common modeling cohort | 687 days shared by all 12 settings |

- The table keeps history buffers before the study and unavailable targets after it. PM/weather join on local dates; GFAS on its explicit earlier UTC mean day. Calendar lags precede exclusions, so missing dates cannot become adjacent observations.

| Source before join | Alignment / retained calendar |

| 739 complete PM profiles | One local profile per date; 739 history-anchor calendar rows. |

| 17544 weather UTC hours | Convert to Thai time; require 24 valid hours per daily field; missing values remain missing. |

| 740 GFAS UTC days (two fields/day) | Latest source day D-2; reindex to the 739-row history calendar. |

| Calendar before / after join | 739 / 739; one-to-one keys, no row multiplication. Buffers and out-of-study targets stay in the ledger. |


## C3: fill/drop decisions and native zeros

- No target or predictor interpolation, forward fill, median replacement or blanket zero filling. Daily PM/weather need 24 valid hours. Missing or invalid input makes its complete-history row ineligible; raw records remain preserved.

- GFAS native regional FRP is all zero on 323 of 740 captured UTC days; the longest run is 59 days, 11 June-8 August 2025. These are source-analysis values, not project-imputed missing. They do not prove absence of real fires; assimilation and observation opportunity remain source limitations.

- GFAS density (W/m2) is integrated with spherical cell area: mean power MW = sum(density*area)/1e6. Positive-analysis area fraction is an extent index, not hotspots or burnt area. offire may exceed 1 and is not clipped or modeled [4].

Evidence: join_audit.json; row_inclusion.csv; missing_decisions.csv; gfas_daily_derived.csv; fire_area_aggregation.json.


## 3 Method | variables, models and evaluation

| Input group | Base variables and units |

| PM:3 | Mean / minimum / maximum of the same 24-hour profile (ug/m3) |

| Weather:7 | Temperature(degC), humidity(%), pressure(hPa), wind speed/u/v(m/s), precipitation total(mm/day) |

| Fire:2 | log1p(area-integrated mean FRP in MW); positive-analysis area fraction |

| Excluded | Target, dates, quality/availability flags, offire and provider reference are not learned predictors |

- Hourly wind components u=-s*sin(theta), v=-s*cos(theta) are averaged after conversion. Rain intervals use their start day. A k-day setting has only its source groups and lags 0..k-1; its actual source days follow the source-clock contract.

- Primary Ridge: squared error plus alpha*sum(beta squared), alpha in {0.1,1,10,100,1000}; StandardScaler fits only within training folds. HGB is secondary: 200 iterations, learning rate 0.05,minimum leaf 20; leaf nodes 7/15 and L2=0/10. Both clip predictions at 0 consistently in CV and scoring.

| Partition | Dates | N |

| train | 2024-01-28 to 2024-09-29 | 231 |

| validation | 2024-10-01 to 2024-12-30 | 91 |

| test | 2025-01-01 to 2025-12-31 | 365 |

- Three training-only expanding calendar folds use gap 1 plus explicit label-completion checks. Two outer boundaries are purged before selection/refit, because next-phase first issue precedes completion of those target days.

- Validation MAE selects the primary source/window and within-group preferred windows. Every fixed setting is reported on test; no test winner is promoted. Moving-block 95% intervals: 14 days, 1000 repeats, seed 42; 7/28-day blocks are secondary sensitivity.

Evidence: feature_manifest.csv; cv_calendar_audit.csv; chronology.csv; forecast_lock.json; tuning.json.


## 4 Results | severity, seasonality and fire quality

| Year | Valid days | Mean PM | Maximum | Modeled exceedance days |

| 2024 | 366 | 19.55 | 44.62 | 10 |

| 2025 | 365 | 23.77 | 91.88 | 30 |

Figure 2. Full-year modeled counts with actual denominators;2024 includes leap day. Pooled monthly means describe two archived model years, not a long-term measured trend.

Figure: outputs/figures/02_exceedances_seasonality.png

Figure 3. GFAS mean FRP power and observation-opportunity area are different quantities. Native zero-analysis stretches are retained; no detection/observation completeness claim follows.

Figure: outputs/figures/03_fire_quality.png

- Severity uses the full modeled calendar; predictive scores below use the common cohort and declared partitions. These populations are not interchangeable.

Evidence: annual_summary.csv; monthly_summary.csv; coverage_by_month.csv; gfas_daily_derived.csv.


## 4 Results | baseline first, then all twelve settings C5

| Test reference | MAE | RMSE | Recall | FP / FN |

| B0_persistence | 6.282 | 8.766 | 0.367 | 19 / 19 |

| B1_provider_forecast | 3.739 | 5.195 | 0.667 | 25 / 10 |

| C0_training_majority | - | - | 0.000 | 0 / 30 |

| Primary Ridge setting | MAE | RMSE | Recall | FP / FN |

| H1_3d | 6.137 | 8.512 | 0.233 | 8 / 23 |

| H1_5d | 6.236 | 8.619 | 0.200 | 11 / 24 |

| H1_7d | 6.585 | 8.983 | 0.267 | 13 / 22 |

| H2_3d | 5.701 | 8.112 | 0.200 | 4 / 24 |

| H2_5d | 5.705 | 8.010 | 0.200 | 3 / 24 |

| H2_7d | 5.792 | 8.252 | 0.133 | 3 / 26 |

| H3_3d | 6.105 | 8.391 | 0.400 | 11 / 18 |

| H3_5d | 5.796 | 7.929 | 0.300 | 11 / 21 |

| H3_7d | 6.284 | 8.550 | 0.467 | 15 / 16 |

| H4_3d | 5.741 | 8.023 | 0.233 | 5 / 23 |

| H4_5d | 5.754 | 7.950 | 0.233 | 6 / 23 |

| H4_7d | 5.755 | 8.171 | 0.133 | 3 / 26 |

- Validation selected H1_3d; its test MAE is 6.137. Relative to persistence this is 2.3% lower. Relative to the provider forecast it is 64.1% higher.

- All rows use identical 365 test dates. C0 is warning-only; its numeric encoding is not assigned a regression score. A good persistence comparison alone does not show benefit over the earlier CAMS forecast.

Evidence: model_scores.csv; predictions_test.csv; selection.json; metrics.csv. Secondary HGB results appear in Appendix C.


## 4 Results | incremental inputs and uncertainty

Figure 4. All 12 primary settings on matched dates. Color/rank does not change the validation-selected candidate.

Figure: outputs/figures/04_twelve_settings.png

| k | Increment | MAE difference | Pointwise 95% block interval |

| 3 | H1-B0 | -0.145 | [-0.528, +0.238] |

| 3 | H2-H1 | -0.435 | [-0.761, -0.159] |

| 3 | H3-H1 | -0.031 | [-0.252, +0.155] |

| 3 | H4-H2 | +0.040 | [-0.070, +0.148] |

| 3 | H4-H3 | -0.364 | [-0.817, +0.068] |

| 5 | H1-B0 | -0.046 | [-0.430, +0.357] |

| 5 | H2-H1 | -0.531 | [-0.913, -0.214] |

| 5 | H3-H1 | -0.440 | [-0.693, -0.236] |

| 5 | H4-H2 | +0.049 | [-0.078, +0.172] |

| 5 | H4-H3 | -0.042 | [-0.376, +0.264] |

| 7 | H1-B0 | +0.303 | [-0.189, +0.896] |

| 7 | H2-H1 | -0.794 | [-1.614, -0.127] |

| 7 | H3-H1 | -0.301 | [-0.583, -0.056] |

| 7 | H4-H2 | -0.036 | [-0.116, +0.022] |

| 7 | H4-H3 | -0.528 | [-1.401, +0.236] |

- Negative differences favor the added group. Intervals spanning 0 are inconclusive; intervals entirely above 0 favor the reference. H4 needs both conditional comparisons to distinguish weather from fire contributions.

- Across 7/14/28-day block sensitivity, 1 of 15 primary contrast classifications change. These are exploratory pointwise intervals, not multiplicity-adjusted confirmations; uncertainty is not hidden when a working expectation fails.

Evidence: paired_comparisons.csv; twelve_answers.csv; bootstrap_sensitivity.csv; window_selection_by_group.csv.


## 4 Results | warning errors and station reference C4-C6

Figure 5. Fixed 37.5 threshold on the same modeled test outcomes; lower MAE does not guarantee fewer missed exceedances.

Figure: outputs/figures/05_warning_errors.png

- Selected model: recall 0.233, precision 0.467, FP 8, FN 23. Persistence: FP 19, FN 19. Provider reference: FP 25, FN 10.


## C4: one primary receptor, explicit source grids

- The requested Chiang Mai receptor maps to ADS 18.8N, 98.8E on 0.4-degree output. Weather has its own source grid; the regional fire box is not another PM location. No second independent study site is invented.


## C6: preserved contemporary measured reference

| Station | Reporting local time | Air4Thai 24h | CAMS 24 samples | Signed difference |

| 36t | 2026-10-16T21:00:00 | 13.30 | 12.97 | -0.33 |

| 35t | 2026-10-16T21:00:00 | 16.40 | 12.97 | -3.43 |

- This 16 October 2026 station/Open-Meteo snapshot is outside the 2024-2025 study and uses a separate product/grid. Air4Thai rolling 24h concentration is compared with 24 modeled hourly samples at nominally matched location/time; one-hour boundary sensitivity is retained. It does not validate the historical ADS target [6].

- Subject to station QA, the ground monitor is the local empirical reference; CAMS is a coarse-grid model product. Differences may reflect grid and averaging-window mismatch; this point check does not validate historical ADS targets or station-level warning skill.

Evidence: station_crosscheck.csv/json; spatial_resolution_audit.json; warning_day_details.csv; missed_day_details.csv.


## 5 Conclusion | supported actions and limitations

The direct answer is conditional on the modeled target and retained dates: validation chose H1_3d. Its MAE is 6.137, persistence 6.282, provider reference 3.739. Warning misses are 23 vs 19 and 10, respectively. Source additions and window answers are reported separately, not reduced to one winner.

Incremental answers (pointwise intervals): H1 beats persistence with an interval below 0 at k=none. Weather beyond PM is supported at k=3/5/7; fire beyond PM at k=5/7. Fire conditional on weather: k=none; weather conditional on fire: k=none. These are exploratory associations, not causal or familywise-confirmed effects.


## What improved structurally, and what the numbers establish

- The original already had baselines, temporal evaluation and multiple lags. The current design improves the inspectable contract: fixed archived vintages, actual 07:00 next-day horizon, source-specific offsets, cell-area-correct fire variables, label-maturity purges and current-run provenance.

- Predictive improvement is assessed against contemporaneous baselines on matched dates. Old/new MAE also changes with product, horizon, period and cohort; it cannot isolate algorithm improvement. Appendix F preserves both results and explains this comparison limit.

- Training/validation contain 7/3 modeled exceedances, versus 30 in test. The validation-selected candidate is not the lowest-test-MAE setting; this shift and the short validation season limit generalization. These counts explain uncertainty, not a reason to retune the inspected test.


## Who should do what, and when

| Owner / timing | Proposed action and check |

| Principal / before outdoor activities | Review current official local air-quality information under existing school policy; log source/time and the decision. Recheck when conditions change. Do not treat this prototype as an automatic warning. |

| Analytics team / each 07:00 trial issue | Shadow trial only: retain source values/versions, acquisition times, issued prediction and missing-input status; do not backfill a missed issue. Score later against a separately defined local measured target. |

| School + analytics / before trial and review | Agree FN/FP costs, minimum acceptable recall, review schedule and stop conditions before seeing new outcomes. Compare persistence and direct-provider forecasts; a failed source gate means no automatic release. |

- These are proposed procedures, not evidence that a school adopted them. For the current modeled test, cost=FP+r*FN gives selected-minus-persistence = -11+4r; selected is worse for r>2.75. The cost ratio is illustrative, not a measured stakeholder value. False reassurance and unnecessary disruption require explicit review.


## Limits that remain open

- Temporal cutoff and label-maturity checks address Section 6.2 under this retrospective design. Separate limits remain: exact historical public release/revision, one coarse-grid receptor, GFAS/CAMS source dependence, two-year/model-cycle variability and exploratory multiple comparisons.

Evidence: availability_gate.json; source_time_contract.json; model_development_comparison.csv; reference_store.json. Student review/signature and actual repository/video submission remain external tasks.


## Appendix A | every-column missingness and decisions

Denominators include all 739 daily history-anchor rows, with explicit buffers and out-of-study targets. Raw native source missingness and derived-calendar missingness are different quantities.

| Column | Missing N | Total N | Missing % |

| date | 0 | 739 | 0.000 |

| pm25_mean | 0 | 739 | 0.000 |

| pm25_min | 0 | 739 | 0.000 |

| pm25_max | 0 | 739 | 0.000 |

| pm25_valid_hours | 0 | 739 | 0.000 |

| temperature_mean | 27 | 739 | 3.654 |

| humidity_mean | 27 | 739 | 3.654 |

| pressure_mean | 27 | 739 | 3.654 |

| wind_speed_ms | 27 | 739 | 3.654 |

| wind_u_ms | 27 | 739 | 3.654 |

| wind_v_ms | 27 | 739 | 3.654 |

| precipitation_sum | 27 | 739 | 3.654 |

| rain_valid_hours | 8 | 739 | 1.083 |

| weather_min_valid_hours | 8 | 739 | 1.083 |

| fire_power_mw | 0 | 739 | 0.000 |

| log_fire_power_mw | 0 | 739 | 0.000 |

| fire_positive_area_fraction | 0 | 739 | 0.000 |

| fire_observation_area_fraction | 0 | 739 | 0.000 |

| fire_opportunity_weighted_mean | 0 | 739 | 0.000 |

| fire_zero_grid_cells | 0 | 739 | 0.000 |

| fire_missing_grid_cells | 0 | 739 | 0.000 |

| fire_project_fill_applied | 0 | 739 | 0.000 |

| fire_source_day_utc | 0 | 739 | 0.000 |

| target_date | 0 | 739 | 0.000 |

| issue_date | 0 | 739 | 0.000 |

| forecast_origin_utc | 0 | 739 | 0.000 |

| target_complete_utc | 0 | 739 | 0.000 |

| pm25_tomorrow | 2 | 739 | 0.271 |

| exceed_tomorrow | 2 | 739 | 0.271 |

| provider_forecast | 1 | 739 | 0.135 |

| source_advisory_dependency | 0 | 739 | 0.000 |

| in_study_target_calendar | 0 | 739 | 0.000 |

| outer_label_purge | 0 | 739 | 0.000 |

| Column | Action / reason |

| date | Retain audit identity/QC; exclude it from learned features. History anchor D-1; calendar join key, not a predictor. |

| pm25_mean | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| pm25_min | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| pm25_max | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| pm25_valid_hours | Retain audit identity/QC; exclude it from learned features. Number of valid PM samples; 24 required. |

| temperature_mean | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| humidity_mean | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| pressure_mean | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| wind_speed_ms | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| wind_u_ms | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| wind_v_ms | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| precipitation_sum | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| rain_valid_hours | Retain audit identity/QC; exclude it from learned features. Valid precipitation intervals in the local day; 24 required. |

| weather_min_valid_hours | Retain audit identity/QC; exclude it from learned features. Minimum valid count across hourly weather fields. |

| fire_power_mw | Retain audit identity/QC; exclude it from learned features. Area-integrated daily mean FRP power before log1p; not energy or emissions. |

| log_fire_power_mw | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| fire_positive_area_fraction | No imputation; preserve missing and require complete calendar windows. Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled. |

| fire_observation_area_fraction | Retain audit identity/QC; exclude it from learned features. Area fraction with native offire > 0; observation-opportunity QC, not burnt area. |

| fire_opportunity_weighted_mean | Retain audit identity/QC; exclude it from learned features. Area-weighted native offire QC; values above 1 are retained. |

| fire_zero_grid_cells | Retain audit identity/QC; exclude it from learned features. Number of cells with zero native FRP analysis. |

| fire_missing_grid_cells | Retain audit identity/QC; exclude it from learned features. Number of missing native fire cells; missing fields are rejected. |

| fire_project_fill_applied | Retain audit identity/QC; exclude it from learned features. Whether the project filled fire values; false in this study. |

| fire_source_day_utc | Retain audit identity/QC; exclude it from learned features. Start date of the GFAS UTC daily averaging interval. |

| target_date | Retain audit identity/QC; exclude it from learned features. Forecast verification day D+1; not a predictor. |

| issue_date | Retain audit identity/QC; exclude it from learned features. Issue day D; issue time is 07:00 Thailand. |

| forecast_origin_utc | Retain audit identity/QC; exclude it from learned features. Timezone-aware forecast issue instant. |

| target_complete_utc | Retain audit identity/QC; exclude it from learned features. End of the target local day; used to check label maturity. |

| pm25_tomorrow | No target fill; require the exact next-day-after-issue profile. Unknown outcomes cannot become safe labels. |

| exceed_tomorrow | No target fill; require the exact next-day-after-issue profile. Unknown outcomes cannot become safe labels. |

| provider_forecast | Retain baseline; no imputation; require a present reference on common dates. Compare every baseline and setting on identical dates; never use B1 as a learned feature. |

| source_advisory_dependency | Retain audit identity/QC; exclude it from learned features. Target or history intersects the prespecified advisory dependency mask. |

| in_study_target_calendar | Retain audit identity/QC; exclude it from learned features. Target date falls within the declared study period. |

| outer_label_purge | Retain audit identity/QC; exclude it from learned features. Boundary target excluded because its label is not mature at the next phase. |


## Appendix A | daily variables, units and retain/drop rationale

| Column | Unit | Purpose | Input? |

| date | local date | History anchor D-1; calendar join key, not a predictor. | False |

| pm25_mean | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. | True |

| pm25_min | ug/m3 | Minimum of the same admitted daily forecast profile. | True |

| pm25_max | ug/m3 | Maximum of the same admitted daily forecast profile. | True |

| pm25_valid_hours | hourly values (count) | Number of valid PM samples; 24 required. | False |

| temperature_mean | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. | True |

| humidity_mean | % | Mean 2 m relative humidity; association rather than causal evidence. | True |

| pressure_mean | hPa | Mean forecast surface pressure. | True |

| wind_speed_ms | m/s | Arithmetic mean hourly 10 m wind speed. | True |

| wind_u_ms | m/s | Mean eastward component derived before aggregation. | True |

| wind_v_ms | m/s | Mean northward component derived before aggregation. | True |

| precipitation_sum | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. | True |

| rain_valid_hours | hourly values (count) | Valid precipitation intervals in the local day; 24 required. | False |

| weather_min_valid_hours | hourly values (count) | Minimum valid count across hourly weather fields. | False |

| fire_power_mw | MW | Area-integrated daily mean FRP power before log1p; not energy or emissions. | False |

| log_fire_power_mw | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. | True |

| fire_positive_area_fraction | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. | True |

| fire_observation_area_fraction | dimensionless fraction | Area fraction with native offire > 0; observation-opportunity QC, not burnt area. | False |

| fire_opportunity_weighted_mean | dimensionless index | Area-weighted native offire QC; values above 1 are retained. | False |

| fire_zero_grid_cells | grid cells (count) | Number of cells with zero native FRP analysis. | False |

| fire_missing_grid_cells | grid cells (count) | Number of missing native fire cells; missing fields are rejected. | False |

| fire_project_fill_applied | boolean | Whether the project filled fire values; false in this study. | False |

| fire_source_day_utc | UTC date | Start date of the GFAS UTC daily averaging interval. | False |

| target_date | local date | Forecast verification day D+1; not a predictor. | False |

| issue_date | local date | Issue day D; issue time is 07:00 Thailand. | False |

| forecast_origin_utc | UTC timestamp | Timezone-aware forecast issue instant. | False |

| target_complete_utc | UTC timestamp | End of the target local day; used to check label maturity. | False |

| pm25_tomorrow | ug/m3 | Target P(D+1); history anchor+2; never a feature. | False |

| exceed_tomorrow | binary 0/1 | Derived target: PM > 37.5; unknown PM retains a missing label. | False |

| provider_forecast | ug/m3 | Direct CAMS baseline B1 for the target day; never a learned feature. | False |

| source_advisory_dependency | boolean | Target or history intersects the prespecified advisory dependency mask. | False |

| in_study_target_calendar | boolean | Target date falls within the declared study period. | False |

| outer_label_purge | boolean | Boundary target excluded because its label is not mature at the next phase. | False |


## Appendix B | every derived predictor

Exactly 84 maximum-window predictors. PM/weather lagj uses local day D-1-j; fire uses UTC day D-2-j. Original public release remains unverified; nominal rules are explicit.

| Feature | Group | Lag | Unit | Purpose |

| pm25_mean_lag0 | PM | 0 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag1 | PM | 1 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag2 | PM | 2 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag3 | PM | 3 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag4 | PM | 4 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag5 | PM | 5 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_mean_lag6 | PM | 6 | ug/m3 | Fixed-vintage mean of 24 instantaneous CAMS hourly values. |

| pm25_min_lag0 | PM | 0 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag1 | PM | 1 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag2 | PM | 2 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag3 | PM | 3 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag4 | PM | 4 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag5 | PM | 5 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_min_lag6 | PM | 6 | ug/m3 | Minimum of the same admitted daily forecast profile. |

| pm25_max_lag0 | PM | 0 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag1 | PM | 1 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag2 | PM | 2 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag3 | PM | 3 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag4 | PM | 4 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag5 | PM | 5 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| pm25_max_lag6 | PM | 6 | ug/m3 | Maximum of the same admitted daily forecast profile. |

| temperature_mean_lag0 | weather | 0 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag1 | weather | 1 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag2 | weather | 2 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag3 | weather | 3 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag4 | weather | 4 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag5 | weather | 5 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| temperature_mean_lag6 | weather | 6 | deg C | Mean 2 m temperature from GFS previous_day1 forecast history. |

| humidity_mean_lag0 | weather | 0 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag1 | weather | 1 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag2 | weather | 2 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag3 | weather | 3 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag4 | weather | 4 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag5 | weather | 5 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| humidity_mean_lag6 | weather | 6 | % | Mean 2 m relative humidity; association rather than causal evidence. |

| pressure_mean_lag0 | weather | 0 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag1 | weather | 1 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag2 | weather | 2 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag3 | weather | 3 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag4 | weather | 4 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag5 | weather | 5 | hPa | Mean forecast surface pressure. |

| pressure_mean_lag6 | weather | 6 | hPa | Mean forecast surface pressure. |

| wind_speed_ms_lag0 | weather | 0 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag1 | weather | 1 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag2 | weather | 2 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag3 | weather | 3 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag4 | weather | 4 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag5 | weather | 5 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_speed_ms_lag6 | weather | 6 | m/s | Arithmetic mean hourly 10 m wind speed. |

| wind_u_ms_lag0 | weather | 0 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag1 | weather | 1 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag2 | weather | 2 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag3 | weather | 3 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag4 | weather | 4 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag5 | weather | 5 | m/s | Mean eastward component derived before aggregation. |

| wind_u_ms_lag6 | weather | 6 | m/s | Mean eastward component derived before aggregation. |

| wind_v_ms_lag0 | weather | 0 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag1 | weather | 1 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag2 | weather | 2 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag3 | weather | 3 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag4 | weather | 4 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag5 | weather | 5 | m/s | Mean northward component derived before aggregation. |

| wind_v_ms_lag6 | weather | 6 | m/s | Mean northward component derived before aggregation. |

| precipitation_sum_lag0 | weather | 0 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag1 | weather | 1 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag2 | weather | 2 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag3 | weather | 3 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag4 | weather | 4 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag5 | weather | 5 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| precipitation_sum_lag6 | weather | 6 | mm/day | Sum of preceding-hour intervals assigned to interval-start local day. |

| log_fire_power_mw_lag0 | fire | 0 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag1 | fire | 1 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag2 | fire | 2 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag3 | fire | 3 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag4 | fire | 4 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag5 | fire | 5 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| log_fire_power_mw_lag6 | fire | 6 | log1p(MW-valued index) | Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions. |

| fire_positive_area_fraction_lag0 | fire | 0 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag1 | fire | 1 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag2 | fire | 2 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag3 | fire | 3 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag4 | fire | 4 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag5 | fire | 5 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |

| fire_positive_area_fraction_lag6 | fire | 6 | fraction of bounding-box grid area | Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area. |


## Appendix C | complete experiment answers and robustness

| Learner / setting | MAE | Recall | FP/FN | Answer |

| ridge / H1_3d | 6.137 | 0.233 | 8/23 | H1-B0: no clear MAE difference; interval spans zero; delta=-0.1453, 95% CI [-0.5277, 0.2377] |

| ridge / H1_5d | 6.236 | 0.200 | 11/24 | H1-B0: no clear MAE difference; interval spans zero; delta=-0.0463, 95% CI [-0.4300, 0.3573] |

| ridge / H1_7d | 6.585 | 0.267 | 13/22 | H1-B0: no clear MAE difference; interval spans zero; delta=0.3034, 95% CI [-0.1887, 0.8963] |

| ridge / H2_3d | 5.701 | 0.200 | 4/24 | H2-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.4352, 95% CI [-0.7614, -0.1585] |

| ridge / H2_5d | 5.705 | 0.200 | 3/24 | H2-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.5306, 95% CI [-0.9130, -0.2141] |

| ridge / H2_7d | 5.792 | 0.133 | 3/26 | H2-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.7937, 95% CI [-1.6135, -0.1274] |

| ridge / H3_3d | 6.105 | 0.400 | 11/18 | H3-H1: no clear MAE difference; interval spans zero; delta=-0.0313, 95% CI [-0.2523, 0.1553] |

| ridge / H3_5d | 5.796 | 0.300 | 11/21 | H3-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.4399, 95% CI [-0.6930, -0.2359] |

| ridge / H3_7d | 6.284 | 0.467 | 15/16 | H3-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.3015, 95% CI [-0.5828, -0.0562] |

| ridge / H4_3d | 5.741 | 0.233 | 5/23 | H4-H2: no clear MAE difference; interval spans zero; delta=0.0397, 95% CI [-0.0697, 0.1480] | H4-H3: no clear MAE difference; interval spans zero; delta=-0.3642, 95% CI [-0.8167, 0.0681] |

| ridge / H4_5d | 5.754 | 0.233 | 6/23 | H4-H2: no clear MAE difference; interval spans zero; delta=0.0492, 95% CI [-0.0783, 0.1720] | H4-H3: no clear MAE difference; interval spans zero; delta=-0.0415, 95% CI [-0.3760, 0.2640] |

| ridge / H4_7d | 5.755 | 0.133 | 3/26 | H4-H2: no clear MAE difference; interval spans zero; delta=-0.0362, 95% CI [-0.1160, 0.0216] | H4-H3: no clear MAE difference; interval spans zero; delta=-0.5283, 95% CI [-1.4015, 0.2363] |

| hgb / H1_3d | 6.497 | 0.000 | 0/30 | H1-B0: no clear MAE difference; interval spans zero; delta=0.2147, 95% CI [-0.5475, 1.0225] |

| hgb / H1_5d | 6.704 | 0.000 | 0/30 | H1-B0: no clear MAE difference; interval spans zero; delta=0.4225, 95% CI [-0.4097, 1.3354] |

| hgb / H1_7d | 6.799 | 0.000 | 0/30 | H1-B0: no clear MAE difference; interval spans zero; delta=0.5172, 95% CI [-0.3352, 1.4699] |

| hgb / H2_3d | 6.344 | 0.000 | 0/30 | H2-H1: no clear MAE difference; interval spans zero; delta=-0.1525, 95% CI [-0.5475, 0.1729] |

| hgb / H2_5d | 6.713 | 0.000 | 0/30 | H2-H1: no clear MAE difference; interval spans zero; delta=0.0087, 95% CI [-0.4434, 0.5223] |

| hgb / H2_7d | 6.644 | 0.000 | 0/30 | H2-H1: no clear MAE difference; interval spans zero; delta=-0.1550, 95% CI [-0.6263, 0.3900] |

| hgb / H3_3d | 6.360 | 0.033 | 1/29 | H3-H1: no clear MAE difference; interval spans zero; delta=-0.1363, 95% CI [-0.4679, 0.1417] |

| hgb / H3_5d | 6.362 | 0.000 | 1/30 | H3-H1: lower MAE with pointwise exploratory interval below zero; delta=-0.3420, 95% CI [-0.7188, -0.0234] |

| hgb / H3_7d | 6.653 | 0.000 | 0/30 | H3-H1: no clear MAE difference; interval spans zero; delta=-0.1456, 95% CI [-0.5027, 0.1539] |

| hgb / H4_3d | 6.221 | 0.000 | 0/30 | H4-H2: no clear MAE difference; interval spans zero; delta=-0.1231, 95% CI [-0.3520, 0.0842] | H4-H3: no clear MAE difference; interval spans zero; delta=-0.1393, 95% CI [-0.5364, 0.2086] |

| hgb / H4_5d | 6.458 | 0.000 | 0/30 | H4-H2: no clear MAE difference; interval spans zero; delta=-0.2549, 95% CI [-0.5141, 0.0116] | H4-H3: no clear MAE difference; interval spans zero; delta=0.0958, 95% CI [-0.2375, 0.5129] |

| hgb / H4_7d | 6.387 | 0.000 | 0/30 | H4-H2: lower MAE with pointwise exploratory interval below zero; delta=-0.2573, 95% CI [-0.4109, -0.1016] | H4-H3: no clear MAE difference; interval spans zero; delta=-0.2667, 95% CI [-0.6972, 0.2289] |


## Appendix C | quality-policy and uncertainty sensitivity


## fire_policy_sensitivity.csv

| policy | common_history_rows | used_for_primary_model |

| value_complete_before_advisory_and_outer_purges | 704 | False |

| after_conservative_advisory_before_outer_purges | 689 | False |

| primary_with_advisory_and_label_maturity_purges | 687 | True |


## learner_robustness.csv

| experiment | MAE_ridge | MAE_hgb | delta_hgb_minus_ridge |

| H1_3d | 6.1366 | 6.4965 | 0.36 |

| H1_5d | 6.2356 | 6.7043 | 0.4687 |

| H1_7d | 6.5853 | 6.7991 | 0.2138 |

| H2_3d | 5.7014 | 6.344 | 0.6426 |

| H2_5d | 5.7051 | 6.7131 | 1.008 |

| H2_7d | 5.7916 | 6.6441 | 0.8525 |

| H3_3d | 6.1053 | 6.3603 | 0.255 |

| H3_5d | 5.7958 | 6.3624 | 0.5666 |

| H3_7d | 6.2838 | 6.6535 | 0.3697 |

| H4_3d | 5.7411 | 6.2209 | 0.4798 |

| H4_5d | 5.7542 | 6.4581 | 0.7039 |

| H4_7d | 5.7555 | 6.3868 | 0.6313 |

The advisory policy and 14-day interval stay primary. Policy alternatives count coverage only; HGB and 7/28-day intervals do not trigger reselection. All complete interval tables remain in the CSV outputs.


## Appendix C | additional figures and interpretation

Figure A1. Full-calendar fixed-vintage CAMS profiles; modeled output at one point, not measured provincial exposure.

Figure: outputs/figures/01_daily_pm25.png

Figure A2. Source-history availability, conservative advisory policy and maturity purges change cohort coverage.

Figure: outputs/figures/06_matched_period_coverage.png

Figure A3. Selected-model forecasts, targets and missed modeled exceedances on retained test dates.

Figure: outputs/figures/07_warning_days.png


## Appendix D | complete executed notebook code cells

English explanations describe each cell. Grey blocks reproduce every code cell with Thai inline comments. Display wrapping is not a source edit. Execution counts reflect the saved notebooks at generation time. The runner rebuilds this PDF after saving all four complete notebooks; final execution evidence is authoritative.


## 01_fetch_data.ipynb


### 01_fetch_data.ipynb cell 3
from pathlib import Path  # กำหนดตำแหน่งโครงการให้ใช้ได้ในเครื่องและ Colab
import sys  # ใช้โมดูลของโครงการกับ Python ที่กำลังรัน
import os  # อ่านกุญแจจากสภาพแวดล้อมโดยไม่บันทึกค่า
import json  # อ่านค่ากำหนดและข้อมูลอธิบายที่สร้างจริง
import zipfile  # ตรวจและแตกแพ็กเกจโครงการเมื่อจำเป็น
PROJECT_NAME = 'PM25_270702_690631023_Submission'  # ระบุชื่อโครงการฝุ่นและลำดับงานสี่ขั้น
BASE = Path.cwd().resolve()  # ใช้โฟลเดอร์ที่ notebook กำลังรัน
ROOT = BASE if (BASE / 'config.json').is_file() and (BASE / 'src' / 'workflow.py').is_file() else BASE / PROJECT_NAME  # เลือกโครงการที่แตกไฟล์ไว้ก่อน
if not (ROOT / 'src' / 'workflow.py').is_file():  # ค้นหาแพ็กเกจเมื่อเปิด notebook เดี่ยวใน Colab
    if not Path('/content').is_dir():  # การรันในเครื่องต้องมีโครงการที่แตก ZIP อยู่ข้าง notebook
        raise FileNotFoundError('Extract the supplied project ZIP and open its notebook first.')  # หยุดแทนการนำเข้าโค้ดคนละโครงการ
    from google.colab import files  # ขอแพ็กเกจโค้ดและข้อมูลที่มาพร้อม notebook
    uploaded = files.upload()  # อัปโหลด ZIP โครงการที่มีข้อมูลและโค้ดครบ
    archives = [name for name in uploaded if name.lower().endswith('.zip')]  # รับเฉพาะแพ็กเกจ ZIP
    assert len(archives) == 1, 'Upload exactly one project ZIP.'  # หยุดเมื่อเลือกแพ็กเกจได้ไม่แน่นอน
    with zipfile.ZipFile(BASE / archives[0]) as archive:  # เปิด ZIP ที่เลือกเพื่อตรวจความสมบูรณ์
        assert archive.testzip() is None, 'Project ZIP is damaged.'  # ตรวจความสมบูรณ์ ZIP ก่อนแตกไฟล์
        for member in archive.infolist():  # ตรวจปลายทางทุกไฟล์แทนการเชื่อชื่อใน ZIP
            destination = (BASE / member.filename).resolve()  # หาตำแหน่งปลายทางแบบสมบูรณ์ของทุกไฟล์
            assert destination.is_relative_to(BASE), 'Unsafe archive member.'  # ปฏิเสธตำแหน่งไฟล์ที่ออกนอกโฟลเดอร์ทำงาน
        archive.extractall(BASE)  # แตกไฟล์โครงการหลังตรวจความปลอดภัย
assert (ROOT / 'src' / 'workflow.py').is_file(), 'Expected PM2.5 project not found.'  # ตรวจว่ามีโมดูลของโครงการนี้จริง
sys.path.insert(0, str(ROOT / 'src'))  # ใช้โมดูลต้นฉบับที่แนบมากับโครงการ
print('PROJECT:', ROOT)  # แสดงโครงการที่จะรัน


### 01_fetch_data.ipynb cell 5
import importlib.util  # ตรวจไลบรารีที่ขาดก่อนนำเข้าโมดูลวิเคราะห์
import subprocess  # ติดตั้งแพ็กเกจด้วย Python ของ notebook เมื่อจำเป็น
REQUIRED_IMPORTS = ['numpy', 'pandas', 'requests', 'matplotlib', 'scipy', 'sklearn', 'nbformat', 'nbclient', 'reportlab', 'pypdf', 'PIL', 'eccodes']  # ระบุไลบรารีที่ต้องใช้
missing_imports = [name for name in REQUIRED_IMPORTS if importlib.util.find_spec(name) is None]  # ตรวจไลบรารีโดยไม่เปลี่ยนแพ็กเกจที่ติดตั้งเงียบ ๆ
if missing_imports:  # ติดตั้งตามรายการรุ่นเมื่อขาดไลบรารีที่จำเป็น
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')])  # ใช้รุ่นแพ็กเกจที่กำหนดเพื่อให้ทำซ้ำได้
FETCH_NEW_WEATHER = False  # เปิดเฉพาะเมื่อต้องการเก็บคำตอบ API ชุดใหม่แยกจากชุดทดลองเดิม
MODE = 'replay'  # ตรวจและใช้ไฟล์ API จริงที่เก็บไว้ตามแผนที่ล็อก
os.environ['MPLBACKEND'] = 'Agg'  # บันทึกกราฟโดยไม่ต้องใช้หน้าต่างแสดงภาพ
for thread_variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:  # จำกัดเธรดเพื่อให้โมเดลขนาดเล็กทำซ้ำได้
    os.environ.setdefault(thread_variable, '1')  # เคารพค่าที่ผู้ใช้ตั้งและให้ค่าเริ่มต้นที่ย้ายเครื่องได้
from common import load_config  # อ่านตำแหน่งโครงการและค่าการศึกษาที่กำหนด
os.chdir(ROOT)  # ให้ notebook และสคริปต์อ้างอิงโฟลเดอร์โครงการเดียวกัน
ROOT, CONFIG = load_config()  # สร้างโฟลเดอร์ผลลัพธ์และอ่านค่ากำหนดการศึกษา
assert CONFIG['study_contract'] == 'next_day_0700_thai', 'Wrong forecast contract.'  # ตรวจว่ากำลังใช้ข้อกำหนดเวลาทำนายที่กำหนด
from IPython.display import display, Image, HTML  # แสดงตารางหลักฐานและภาพผลการวิเคราะห์
import pandas as pd  # อ่านข้อมูลรายวันและตารางผลลัพธ์
import numpy as np  # ใช้ตรวจตัวเลขแบบทำซ้ำได้
import workflow as lab  # ใช้ฟังก์ชันควบคุม ตรวจ และจัดแพ็กเกจของโครงการ
run_state = lab.begin_run(ROOT, CONFIG, MODE)  # บันทึก hash โค้ดปัจจุบันก่อนเริ่มวิเคราะห์
display(pd.read_csv(ROOT / 'configuration_dictionary.csv'))  # อธิบายค่ากำหนดทุกตัวและเหตุผลที่ใช้
from environment_check import check_environment  # ตรวจรุ่นที่ติดตั้งกับรายการที่แนบ
dependency_evidence = check_environment(ROOT, strict=True)  # หยุดเมื่อรุ่นแพ็กเกจไม่ตรงแทนการอ้างว่าทำซ้ำได้
print('DEPENDENCIES:', dependency_evidence['status'])  # แสดงผลตรวจสภาพแวดล้อมจริง
display(HTML("<style>.jp-CodeCell .jp-InputArea-editor,.input_area{background:#f2f2f2!important;border:1px solid #ccc}</style>"))  # แสดงพื้นเซลล์โค้ดสีเทาในหน้าที่รองรับ CSS


### 01_fetch_data.ipynb cell 7
analysis_plan = json.loads((ROOT / 'analysis_plan.json').read_text(encoding='utf-8'))  # อ่านแผนที่ล็อกก่อนมีคะแนนรอบใหม่
display(pd.DataFrame(analysis_plan['hypotheses'].items(), columns=['Group', 'Question']))  # แสดงคำถามทั้งสี่กลุ่ม
display(pd.DataFrame(json.loads((ROOT / 'report/study_metadata/study_contract.json').read_text(encoding='utf-8')).items(), columns=['Contract item', 'Meaning']))  # แยกขอบเขตย้อนหลังจากการรับรองพร้อมใช้จริง



### 01_fetch_data.ipynb cell 9
from weather_acquisition import acquire_weather  # ใช้ตัวดึงอากาศจริงชุดเดียวกับสคริปต์
if FETCH_NEW_WEATHER:  # เปิดเฉพาะเมื่อต้องการเก็บข้อมูลใหม่แยกจากชุดทดลองเดิม
    display(acquire_weather(ROOT, ROOT / 'data/raw/weather_new_capture'))  # เก็บคำตอบ API และหลักฐานจริงไว้แยกชุด
raw_folder, raw_manifest, station_reference = lab.acquire_all(ROOT, CONFIG, mode=MODE)  # ตรวจ raw จริงและสร้าง native exports ใหม่จากข้อมูลดิบ
print('RAW RUN:', raw_manifest['run_id'], '| Preserved files:', len(raw_manifest['files']))  # แสดงรอบข้อมูลโดยไม่เปิดเผย credentials
display(pd.DataFrame(json.loads((ROOT / 'outputs/results/raw_decode_audit.json').read_text(encoding='utf-8'))['records']))  # ตรวจจำนวน field และ missing ของคำขอทั้ง 50



### 01_fetch_data.ipynb cell 11
source_inventory = pd.DataFrame(raw_manifest['files'])  # อ่านรายการไฟล์จริงและ hash ใน snapshot
display(source_inventory[['file', 'bytes', 'status']].head(12))  # ตัวอย่างรายการ โดยไฟล์ครบอยู่ใน manifest
display(pd.read_csv(ROOT / 'outputs/results/station_crosscheck.csv'))  # แสดงการเทียบสถานีที่เก็บไว้ตามเวลาและหน่วยจริง



### 01_fetch_data.ipynb cell 13
from check_dataset import check_raw, require_pass  # ใช้ checker ชุดเดียวกับสคริปต์
raw_validation = require_pass(check_raw(ROOT, CONFIG))  # หยุดเมื่อหลักฐาน raw หรือ native exports เปลี่ยน
display(pd.DataFrame(raw_validation['checks']))  # แสดงทั้งข้อที่ผ่านและข้อที่ยังไม่รับรอง
display(pd.DataFrame(json.loads((ROOT / 'outputs/results/source_time_contract.json').read_text(encoding='utf-8'))['sources']))  # แสดงนาฬิกาของแต่ละแหล่งอย่างชัดเจน



## 02_prepare_data.ipynb


### 02_prepare_data.ipynb cell 3
from pathlib import Path  # กำหนดตำแหน่งโครงการให้ใช้ได้ในเครื่องและ Colab
import sys  # ใช้โมดูลของโครงการกับ Python ที่กำลังรัน
import os  # อ่านกุญแจจากสภาพแวดล้อมโดยไม่บันทึกค่า
import json  # อ่านค่ากำหนดและข้อมูลอธิบายที่สร้างจริง
import zipfile  # ตรวจและแตกแพ็กเกจโครงการเมื่อจำเป็น
PROJECT_NAME = 'PM25_270702_690631023_Submission'  # ระบุชื่อโครงการฝุ่นและลำดับงานสี่ขั้น
BASE = Path.cwd().resolve()  # ใช้โฟลเดอร์ที่ notebook กำลังรัน
ROOT = BASE if (BASE / 'config.json').is_file() and (BASE / 'src' / 'workflow.py').is_file() else BASE / PROJECT_NAME  # เลือกโครงการที่แตกไฟล์ไว้ก่อน
if not (ROOT / 'src' / 'workflow.py').is_file():  # ค้นหาแพ็กเกจเมื่อเปิด notebook เดี่ยวใน Colab
    if not Path('/content').is_dir():  # การรันในเครื่องต้องมีโครงการที่แตก ZIP อยู่ข้าง notebook
        raise FileNotFoundError('Extract the supplied project ZIP and open its notebook first.')  # หยุดแทนการนำเข้าโค้ดคนละโครงการ
    from google.colab import files  # ขอแพ็กเกจโค้ดและข้อมูลที่มาพร้อม notebook
    uploaded = files.upload()  # อัปโหลด ZIP โครงการที่มีข้อมูลและโค้ดครบ
    archives = [name for name in uploaded if name.lower().endswith('.zip')]  # รับเฉพาะแพ็กเกจ ZIP
    assert len(archives) == 1, 'Upload exactly one project ZIP.'  # หยุดเมื่อเลือกแพ็กเกจได้ไม่แน่นอน
    with zipfile.ZipFile(BASE / archives[0]) as archive:  # เปิด ZIP ที่เลือกเพื่อตรวจความสมบูรณ์
        assert archive.testzip() is None, 'Project ZIP is damaged.'  # ตรวจความสมบูรณ์ ZIP ก่อนแตกไฟล์
        for member in archive.infolist():  # ตรวจปลายทางทุกไฟล์แทนการเชื่อชื่อใน ZIP
            destination = (BASE / member.filename).resolve()  # หาตำแหน่งปลายทางแบบสมบูรณ์ของทุกไฟล์
            assert destination.is_relative_to(BASE), 'Unsafe archive member.'  # ปฏิเสธตำแหน่งไฟล์ที่ออกนอกโฟลเดอร์ทำงาน
        archive.extractall(BASE)  # แตกไฟล์โครงการหลังตรวจความปลอดภัย
assert (ROOT / 'src' / 'workflow.py').is_file(), 'Expected PM2.5 project not found.'  # ตรวจว่ามีโมดูลของโครงการนี้จริง
sys.path.insert(0, str(ROOT / 'src'))  # ใช้โมดูลต้นฉบับที่แนบมากับโครงการ
print('PROJECT:', ROOT)  # แสดงโครงการที่จะรันos.environ['MPLBACKEND'] = 'Agg'  # สร้างไฟล์กราฟโดยไม่เปิดหน้าต่าง
for thread_variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:  # จำกัดเธรดก่อนนำเข้าไลบรารีคำนวณ
    os.environ.setdefault(thread_variable, '1')  # ใช้ค่าเริ่มต้นที่ทำซ้ำได้
os.chdir(ROOT)  # ให้ทุกพาธอ้างโครงการเดียวกัน
from common import load_config  # อ่าน contract รุ่นนี้
ROOT, CONFIG = load_config()  # ตรวจเวลาออกคำทำนายและรุ่นโครงการ
from IPython.display import display, Image, HTML  # แสดงหลักฐานและรูปภาพที่สร้างจริง
import pandas as pd  # อ่านตารางโดยรักษาบทบาทของข้อมูล
import numpy as np  # ตรวจค่าตัวเลขและลำดับเวลา
import workflow as lab  # ใช้ orchestration เดียวกับสคริปต์
from environment_check import check_environment  # ตรวจ dependency ที่ล็อกรุ่น
dependency_evidence = check_environment(ROOT, strict=True)  # ไม่เปลี่ยนรุ่นเงียบ ๆ
display(HTML("<style>.jp-CodeCell .jp-InputArea-editor,.input_area{background:#f2f2f2!important;border:1px solid #ccc}</style>"))  # รักษาพื้นเซลล์โค้ดสีเทา



### 02_prepare_data.ipynb cell 5
from prepare_data import prepare_daily, build_experiments  # ใช้การเตรียมข้อมูลเดียวกับสคริปต์
daily, join_audit = prepare_daily(ROOT, CONFIG)  # เก็บทุกวัน รวม buffer และ missing เดิม
display(daily[['date', 'issue_date', 'forecast_origin_utc', 'fire_source_day_utc', 'target_date', 'pm25_tomorrow']].head(10))  # ตรวจ offset ก่อนสร้าง lag
print(json.dumps(join_audit, indent=2))  # แสดงจำนวนแถวก่อนและหลัง join



### 02_prepare_data.ipynb cell 7
X, specifications, eligible = build_experiments(ROOT, CONFIG, daily)  # สร้าง 4 กลุ่ม x 3 หน้าต่างบนวันเดียวกัน
display(pd.DataFrame([{k: v for k, v in item.items() if k != 'features'} for item in specifications]))  # แสดง input groups และจำนวนตัวแปร
display(pd.read_csv(ROOT / 'outputs/results/feature_manifest.csv'))  # นิยามตัวแปร หน่วย เหตุผล และ source day ทุกตัว
print('COMMON ELIGIBLE DAYS:', int(eligible.sum()))  # ไม่นับกริดหรือ setting ซ้ำเป็นจำนวนวัน



### 02_prepare_data.ipynb cell 9
from check_dataset import check_dataset, require_pass  # ตรวจความถูกต้องก่อนส่งเข้าโมเดล
dataset_validation = require_pass(check_dataset(ROOT, CONFIG, daily, X, specifications, eligible))  # ตรวจ shift2, source offset, lags และขอบ label
display(pd.DataFrame(dataset_validation['checks']))  # แสดงข้อจำกัด publication แยกจาก technical PASS
display(pd.read_csv(ROOT / 'outputs/results/missing_decisions.csv'))  # อธิบายทุกคอลัมน์ว่าทำไมไม่ fill และกรณีใดไม่เข้าโมเดล
display(pd.read_csv(ROOT / 'outputs/results/cohort_ledger.csv'))  # บัญชีเหตุผลแบบไม่ซ้ำนับแถว



### 02_prepare_data.ipynb cell 11
from stages import prepare_handoff  # ใช้ shared orchestration เพื่อไม่ให้ notebook และ script ต่างกัน
handoff = prepare_handoff(ROOT, CONFIG, daily, X, specifications, eligible)  # ตรวจข้อมูล ส่งออก answers แยก และสร้าง SQL store
display(pd.read_csv(ROOT / 'outputs/results/chronology.csv'))  # แสดงวันและจำนวนแต่ละ partition
display(pd.read_csv(ROOT / 'outputs/results/cv_calendar_audit.csv'))  # ตรวจ label maturity ภายในแต่ละ fold
print('SQL STORE:', handoff['reference']['status'])  # ฐานข้อมูลใช้ตรวจหลักฐานจริง ไม่ใช่สร้าง target ใหม่



### 02_prepare_data.ipynb cell 13
display(pd.read_csv(ROOT / 'outputs/results/row_inclusion.csv').tail(12))  # คงแถวที่ไม่ใช้ให้ตรวจเหตุผลได้
display(pd.read_csv(ROOT / 'outputs/results/feature_availability.csv'))  # แสดงสถานะ UNVERIFIED ของ original release ตามจริง
display(Image(filename=str(ROOT / 'outputs/figures/06_matched_period_coverage.png'), width=900))  # แสดงผลการคัดวันร่วมและความเป็นตัวแทน



## 03_analyse.ipynb


### 03_analyse.ipynb cell 3
from pathlib import Path  # กำหนดตำแหน่งโครงการให้ใช้ได้ในเครื่องและ Colab
import sys  # ใช้โมดูลของโครงการกับ Python ที่กำลังรัน
import os  # อ่านกุญแจจากสภาพแวดล้อมโดยไม่บันทึกค่า
import json  # อ่านค่ากำหนดและข้อมูลอธิบายที่สร้างจริง
import zipfile  # ตรวจและแตกแพ็กเกจโครงการเมื่อจำเป็น
PROJECT_NAME = 'PM25_270702_690631023_Submission'  # ระบุชื่อโครงการฝุ่นและลำดับงานสี่ขั้น
BASE = Path.cwd().resolve()  # ใช้โฟลเดอร์ที่ notebook กำลังรัน
ROOT = BASE if (BASE / 'config.json').is_file() and (BASE / 'src' / 'workflow.py').is_file() else BASE / PROJECT_NAME  # เลือกโครงการที่แตกไฟล์ไว้ก่อน
if not (ROOT / 'src' / 'workflow.py').is_file():  # ค้นหาแพ็กเกจเมื่อเปิด notebook เดี่ยวใน Colab
    if not Path('/content').is_dir():  # การรันในเครื่องต้องมีโครงการที่แตก ZIP อยู่ข้าง notebook
        raise FileNotFoundError('Extract the supplied project ZIP and open its notebook first.')  # หยุดแทนการนำเข้าโค้ดคนละโครงการ
    from google.colab import files  # ขอแพ็กเกจโค้ดและข้อมูลที่มาพร้อม notebook
    uploaded = files.upload()  # อัปโหลด ZIP โครงการที่มีข้อมูลและโค้ดครบ
    archives = [name for name in uploaded if name.lower().endswith('.zip')]  # รับเฉพาะแพ็กเกจ ZIP
    assert len(archives) == 1, 'Upload exactly one project ZIP.'  # หยุดเมื่อเลือกแพ็กเกจได้ไม่แน่นอน
    with zipfile.ZipFile(BASE / archives[0]) as archive:  # เปิด ZIP ที่เลือกเพื่อตรวจความสมบูรณ์
        assert archive.testzip() is None, 'Project ZIP is damaged.'  # ตรวจความสมบูรณ์ ZIP ก่อนแตกไฟล์
        for member in archive.infolist():  # ตรวจปลายทางทุกไฟล์แทนการเชื่อชื่อใน ZIP
            destination = (BASE / member.filename).resolve()  # หาตำแหน่งปลายทางแบบสมบูรณ์ของทุกไฟล์
            assert destination.is_relative_to(BASE), 'Unsafe archive member.'  # ปฏิเสธตำแหน่งไฟล์ที่ออกนอกโฟลเดอร์ทำงาน
        archive.extractall(BASE)  # แตกไฟล์โครงการหลังตรวจความปลอดภัย
assert (ROOT / 'src' / 'workflow.py').is_file(), 'Expected PM2.5 project not found.'  # ตรวจว่ามีโมดูลของโครงการนี้จริง
sys.path.insert(0, str(ROOT / 'src'))  # ใช้โมดูลต้นฉบับที่แนบมากับโครงการ
print('PROJECT:', ROOT)  # แสดงโครงการที่จะรันos.environ['MPLBACKEND'] = 'Agg'  # สร้างไฟล์กราฟโดยไม่เปิดหน้าต่าง
for thread_variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:  # จำกัดเธรดก่อนนำเข้าไลบรารีคำนวณ
    os.environ.setdefault(thread_variable, '1')  # ใช้ค่าเริ่มต้นที่ทำซ้ำได้
os.chdir(ROOT)  # ให้ทุกพาธอ้างโครงการเดียวกัน
from common import load_config  # อ่าน contract รุ่นนี้
ROOT, CONFIG = load_config()  # ตรวจเวลาออกคำทำนายและรุ่นโครงการ
from IPython.display import display, Image, HTML  # แสดงหลักฐานและรูปภาพที่สร้างจริง
import pandas as pd  # อ่านตารางโดยรักษาบทบาทของข้อมูล
import numpy as np  # ตรวจค่าตัวเลขและลำดับเวลา
import workflow as lab  # ใช้ orchestration เดียวกับสคริปต์
from environment_check import check_environment  # ตรวจ dependency ที่ล็อกรุ่น
dependency_evidence = check_environment(ROOT, strict=True)  # ไม่เปลี่ยนรุ่นเงียบ ๆ
display(HTML("<style>.jp-CodeCell .jp-InputArea-editor,.input_area{background:#f2f2f2!important;border:1px solid #ccc}</style>"))  # รักษาพื้นเซลล์โค้ดสีเทา



### 03_analyse.ipynb cell 5
daily = lab.load_prepared(ROOT, CONFIG)  # ปฏิเสธตารางที่เปลี่ยนหลังเตรียมข้อมูล
from prepare_data import build_experiments  # อ่านชุดทดลองตาม contract เดิม
X, specifications, eligible = build_experiments(ROOT, CONFIG, daily)  # ไม่เลือกตัวแปรใหม่จากความสัมพันธ์ใน test
import analyse as analysis  # ใช้กราฟร่วมกับสคริปต์
annual, monthly = analysis.describe(ROOT, CONFIG, daily)  # สรุปความรุนแรงและฤดูกาลในข้อมูลจำลอง



### 03_analyse.ipynb cell 7
display(annual)  # รายงานจำนวนวันจริงและสัดส่วน ไม่เปรียบเทียบจำนวนโดยลืม denominator
display(monthly)  # ค่าเฉลี่ยรายเดือนจากสองปี ไม่ใช่การพิสูจน์เหตุและผล
display(Image(filename=str(ROOT / 'outputs/figures/01_daily_pm25.png'), width=900))  # แสดงโปรไฟล์และวันที่ต้องระวัง
display(Image(filename=str(ROOT / 'outputs/figures/02_exceedances_seasonality.png'), width=900))  # แสดงจำนวนเกินเกณฑ์และฤดูกาล



### 03_analyse.ipynb cell 9
display(Image(filename=str(ROOT / 'outputs/figures/03_fire_quality.png'), width=900))  # ตรวจค่าศูนย์ไฟกับการสังเกตแยกกัน
display(pd.DataFrame(json.loads((ROOT / 'outputs/results/spatial_resolution_audit.json').read_text(encoding='utf-8')).items(), columns=['Spatial item', 'Evidence']))  # แสดงขอบเขตหนึ่งจุดและกริดต้นทาง
display(pd.read_csv(ROOT / 'outputs/results/exceedance_episodes.csv').head(12))  # ตัวอย่างเหตุการณ์จำลองต่อเนื่องโดยไม่เปลี่ยนการคัดวัน



## 04_model.ipynb


### 04_model.ipynb cell 3
from pathlib import Path  # กำหนดตำแหน่งโครงการให้ใช้ได้ในเครื่องและ Colab
import sys  # ใช้โมดูลของโครงการกับ Python ที่กำลังรัน
import os  # อ่านกุญแจจากสภาพแวดล้อมโดยไม่บันทึกค่า
import json  # อ่านค่ากำหนดและข้อมูลอธิบายที่สร้างจริง
import zipfile  # ตรวจและแตกแพ็กเกจโครงการเมื่อจำเป็น
PROJECT_NAME = 'PM25_270702_690631023_Submission'  # ระบุชื่อโครงการฝุ่นและลำดับงานสี่ขั้น
BASE = Path.cwd().resolve()  # ใช้โฟลเดอร์ที่ notebook กำลังรัน
ROOT = BASE if (BASE / 'config.json').is_file() and (BASE / 'src' / 'workflow.py').is_file() else BASE / PROJECT_NAME  # เลือกโครงการที่แตกไฟล์ไว้ก่อน
if not (ROOT / 'src' / 'workflow.py').is_file():  # ค้นหาแพ็กเกจเมื่อเปิด notebook เดี่ยวใน Colab
    if not Path('/content').is_dir():  # การรันในเครื่องต้องมีโครงการที่แตก ZIP อยู่ข้าง notebook
        raise FileNotFoundError('Extract the supplied project ZIP and open its notebook first.')  # หยุดแทนการนำเข้าโค้ดคนละโครงการ
    from google.colab import files  # ขอแพ็กเกจโค้ดและข้อมูลที่มาพร้อม notebook
    uploaded = files.upload()  # อัปโหลด ZIP โครงการที่มีข้อมูลและโค้ดครบ
    archives = [name for name in uploaded if name.lower().endswith('.zip')]  # รับเฉพาะแพ็กเกจ ZIP
    assert len(archives) == 1, 'Upload exactly one project ZIP.'  # หยุดเมื่อเลือกแพ็กเกจได้ไม่แน่นอน
    with zipfile.ZipFile(BASE / archives[0]) as archive:  # เปิด ZIP ที่เลือกเพื่อตรวจความสมบูรณ์
        assert archive.testzip() is None, 'Project ZIP is damaged.'  # ตรวจความสมบูรณ์ ZIP ก่อนแตกไฟล์
        for member in archive.infolist():  # ตรวจปลายทางทุกไฟล์แทนการเชื่อชื่อใน ZIP
            destination = (BASE / member.filename).resolve()  # หาตำแหน่งปลายทางแบบสมบูรณ์ของทุกไฟล์
            assert destination.is_relative_to(BASE), 'Unsafe archive member.'  # ปฏิเสธตำแหน่งไฟล์ที่ออกนอกโฟลเดอร์ทำงาน
        archive.extractall(BASE)  # แตกไฟล์โครงการหลังตรวจความปลอดภัย
assert (ROOT / 'src' / 'workflow.py').is_file(), 'Expected PM2.5 project not found.'  # ตรวจว่ามีโมดูลของโครงการนี้จริง
sys.path.insert(0, str(ROOT / 'src'))  # ใช้โมดูลต้นฉบับที่แนบมากับโครงการ
print('PROJECT:', ROOT)  # แสดงโครงการที่จะรันos.environ['MPLBACKEND'] = 'Agg'  # สร้างไฟล์กราฟโดยไม่เปิดหน้าต่าง
for thread_variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:  # จำกัดเธรดก่อนนำเข้าไลบรารีคำนวณ
    os.environ.setdefault(thread_variable, '1')  # ใช้ค่าเริ่มต้นที่ทำซ้ำได้
os.chdir(ROOT)  # ให้ทุกพาธอ้างโครงการเดียวกัน
from common import load_config  # อ่าน contract รุ่นนี้
ROOT, CONFIG = load_config()  # ตรวจเวลาออกคำทำนายและรุ่นโครงการ
from IPython.display import display, Image, HTML  # แสดงหลักฐานและรูปภาพที่สร้างจริง
import pandas as pd  # อ่านตารางโดยรักษาบทบาทของข้อมูล
import numpy as np  # ตรวจค่าตัวเลขและลำดับเวลา
import workflow as lab  # ใช้ orchestration เดียวกับสคริปต์
from environment_check import check_environment  # ตรวจ dependency ที่ล็อกรุ่น
dependency_evidence = check_environment(ROOT, strict=True)  # ไม่เปลี่ยนรุ่นเงียบ ๆ
display(HTML("<style>.jp-CodeCell .jp-InputArea-editor,.input_area{background:#f2f2f2!important;border:1px solid #ccc}</style>"))  # รักษาพื้นเซลล์โค้ดสีเทา



### 04_model.ipynb cell 5
daily = lab.load_prepared(ROOT, CONFIG)  # อ่านตารางที่ตรวจ hash แล้ว
from prepare_data import build_experiments  # รักษาคำถาม 12 แบบเดิม
X, specifications, eligible = build_experiments(ROOT, CONFIG, daily)  # ใช้ full-calendar lags และ common cohort
from check_dataset import check_dataset, require_pass  # ใช้ checker ชุดเดียวกับ CLI
require_pass(check_dataset(ROOT, CONFIG, daily, X, specifications, eligible))  # ไม่ฝึกต่อหาก target หรือ offset ผิด



### 04_model.ipynb cell 7
from evaluate_forecast import lock_experiment, verify_receipts  # จัดการการล็อกและ receipt ของรอบจริง
display(pd.read_csv(ROOT / 'outputs/results/chronology.csv'))  # แสดงรอยต่อที่ผ่าน label maturity
test_feature_columns = pd.read_csv(ROOT / 'data/processed/evaluation_inputs/test_features.csv', nrows=0).columns.tolist()  # อ่านเฉพาะหัวคอลัมน์ input ของ test
assert not {'y_true', 'pm25_tomorrow', 'exceed_tomorrow'} & set(test_feature_columns)  # ไม่ให้คำตอบเป็นคอลัมน์ทำนาย
print('Answer-free test columns:', len(test_feature_columns))  # นับ input โดยไม่เปิดคำตอบ



### 04_model.ipynb cell 9
forecast_plan = lock_experiment(ROOT, CONFIG)  # ฝึกจาก train/CV เลือกจาก validation และล็อก source ปัจจุบัน
display(pd.DataFrame(json.loads((ROOT / 'outputs/results/tuning.json').read_text(encoding='utf-8'))))  # รายงานพารามิเตอร์ทุกแบบ
print('VALIDATION-SELECTED:', forecast_plan['selection'])  # ไม่เลือกผู้ชนะใหม่จาก test



### 04_model.ipynb cell 11
from stages import commit_predictions  # ใช้ขั้นทำนายและ SQL commitment ร่วมกับสคริปต์
prediction_receipt, sql_commitment = commit_predictions(ROOT)  # ไม่ส่ง target ของช่วง test เข้า predict
print(json.dumps(prediction_receipt, indent=2))  # เก็บรหัสรอบ เวลา และ hash ของคำทำนาย
print('SQL COMMITMENT:', sql_commitment)  # ตรวจว่าบันทึกคำทำนายก่อนเปิดคำตอบ



### 04_model.ipynb cell 13
committed = pd.read_csv(ROOT / 'outputs/results/predictions_test_blind.csv')  # อ่านคำทำนายที่ commit แล้วเท่านั้น
assert 'y_true' not in committed and not committed.isna().any().any()  # ตรวจว่าไม่มีคำตอบหรือคำทำนายขาด
display(committed.head())  # ตัวอย่างผลที่ยังไม่รวมคำตอบ
print('Committed test dates:', len(committed))  # ทุกแบบต้องมีจำนวนวันเท่ากัน



### 04_model.ipynb cell 15
from stages import score_and_diagnose  # ใช้ขั้นประเมินแยกจากขั้น predict
scores, comparisons, diagnostic_evidence = score_and_diagnose(ROOT, CONFIG)  # เปิดคำตอบหลังตรวจ receipt และคำนวณทุกแบบ
display(scores.query('partition == "test" and family == "baseline"'))  # รายงาน baseline ก่อนโมเดล
print('RECEIPTS:', verify_receipts(ROOT)['status'])  # ยืนยันลำดับ lock -> predict -> score ของรอบปัจจุบัน



### 04_model.ipynb cell 17
import analyse as analysis  # ใช้กราฟจาก metrics ที่บันทึกจริง
mae_matrix = analysis.model_figures(ROOT, CONFIG, scores)  # สร้าง heatmap และกราฟ FP/FN
display(mae_matrix)  # เทียบทุกกลุ่มและหน้าต่าง
display(scores.query('partition == "test" and family == "ridge"'))  # ไม่ซ่อนแบบที่ทำนายแย่กว่า baseline
display(Image(filename=str(ROOT / 'outputs/figures/04_twelve_settings.png'), width=850))  # ดูผลเปรียบเทียบครบ 12 แบบ



### 04_model.ipynb cell 19
display(comparisons.query('family == "ridge"')[['window', 'comparison', 'estimate', 'ci_low', 'ci_high', 'interpretation']])  # แสดงทั้งทิศทางและความไม่แน่นอน
display(pd.read_csv(ROOT / 'outputs/results/twelve_answers.csv').query('family == "ridge"'))  # ตอบครบ 12 คำถามย่อยตามหลักฐาน
display(pd.read_csv(ROOT / 'outputs/results/window_selection_by_group.csv').query('family == "ridge"'))  # หน้าต่างที่เลือกจาก validation ไม่ใช่ test



### 04_model.ipynb cell 21
display(pd.read_csv(ROOT / 'outputs/results/missed_day_details.csv'))  # แสดงทุกวันที่โมเดลพลาดเกินเกณฑ์
display(pd.read_csv(ROOT / 'outputs/results/learner_robustness.csv'))  # เปรียบเทียบ learner รองโดยไม่เลือกใหม่
display(pd.read_csv(ROOT / 'outputs/results/bootstrap_sensitivity.csv').query('family == "ridge"'))  # ตรวจความไวต่อความยาว block ที่กำหนดไว้
display(Image(filename=str(ROOT / 'outputs/figures/07_warning_days.png'), width=900))  # แสดงคำตอบและความผิดพลาดตามวันจริง



### 04_model.ipynb cell 23
display(pd.read_csv(ROOT / 'outputs/results/station_crosscheck.csv'))  # รายงาน measured reference แยกจาก target ของโมเดล
print(json.dumps(json.loads((ROOT / 'outputs/results/spatial_resolution_audit.json').read_text(encoding='utf-8')), indent=2))  # ไม่สร้างจุดศึกษาที่สองจากกริดเดียวกัน
print(json.dumps(json.loads((ROOT / 'outputs/results/availability_gate.json').read_text(encoding='utf-8')), indent=2))  # คงข้อจำกัด original release และ operational gate ตามจริง



### 04_model.ipynb cell 25
from stages import report_ready_artifacts  # ใช้รายงานและการตรวจร่วมกับสคริปต์
report_evidence = report_ready_artifacts(ROOT, CONFIG, daily, X, specifications, eligible)  # ตรวจ science, SQL และสร้าง workflow
from report import build_report  # สร้างรายงานจากผลรอบเดียวกัน
documents = build_report(ROOT, CONFIG)  # คงรูปแบบเดิมและเปลี่ยนเฉพาะเนื้อหาที่หลักฐานใหม่เกี่ยวข้อง
print('TECHNICAL VERIFICATION:', report_evidence['science']['status'])  # ไม่แปลง technical PASS เป็นการรับรอง publication
print('DOCUMENTS:', documents)  # ตรวจจำนวนหน้าและตำแหน่งจริง



### 04_model.ipynb cell 27
candidate_zip, execution_evidence = lab.make_submission(ROOT)  # ตรวจไฟล์และสร้าง candidate จากสิ่งที่บันทึกจริง
print('CANDIDATE ZIP:', candidate_zip)  # ตัวรันจะ seal ใหม่หลังบันทึกครบทุกเซลล์
print('SAVED EXECUTION EVIDENCE:', execution_evidence)  # ไม่ประดิษฐ์ execution_count ให้เซลล์ที่ยังไม่บันทึก



### 04_model.ipynb cell 29
SEAL_COLAB_EXPORTS = False  # เปิดใช้หลังรันครบและส่งออก notebook จริงทั้งสี่ไฟล์
if SEAL_COLAB_EXPORTS:  # ไม่ให้การรันปกติหยุดรอการโต้ตอบ
    import nbformat  # ตรวจต้นฉบับ จำนวนรัน และ error ของ notebook จริง
    import re  # ยอมให้เปลี่ยนเฉพาะโหมดดึงข้อมูลและค่าจัดแพ็กเกจที่กำหนด
    import tempfile  # แยกไฟล์อัปโหลดจากต้นฉบับจนกว่าจะตรวจผ่าน
    from google.colab import files  # อัปโหลด notebook ที่ส่งออกจากการรันจริงทั้งสี่ไฟล์
    expected_books = {name: nbformat.read(ROOT / name, as_version=4) for name in lab.NOTEBOOKS}  # เก็บต้นฉบับที่คาดหวังก่อนอัปโหลดไฟล์
    previous_directory = Path.cwd()  # กลับเข้าโฟลเดอร์โครงการหลังอัปโหลด
    with tempfile.TemporaryDirectory() as upload_folder:  # แยกไฟล์อัปโหลดจากพื้นที่ตรวจต้นฉบับ
        try:  # คืนโฟลเดอร์ทำงานแม้การอัปโหลดผิดพลาด
            os.chdir(upload_folder)  # ป้องกันไฟล์อัปโหลดเขียนทับต้นฉบับก่อนตรวจ
            uploaded_exports = files.upload()  # เลือกไฟล์ส่งออกสี่ notebook ตามชื่อเดิม
        finally:  # คืนตำแหน่งทำงานก่อนตรวจหรือจัดแพ็กเกจ
            os.chdir(previous_directory)  # กลับเข้าโครงการเดิมที่เซลล์ก่อนหน้าใช้
    assert set(uploaded_exports) == set(lab.NOTEBOOKS), 'Upload exactly the four original notebook filenames.'  # ปฏิเสธหลักฐานการรันที่ขาดหรือเกิน
    verified_books = {}  # ยังไม่เขียนทับโครงการจนกว่าจะตรวจต้นฉบับและผลครบ
    for name in lab.NOTEBOOKS:  # ตรวจทุกขั้นแทนการเชื่อ notebook หลักเพียงไฟล์เดียว
        incoming = nbformat.reads(uploaded_exports[name].decode('utf-8'), as_version=4)  # อ่านเนื้อหา notebook ที่ส่งออกจริง
        expected = expected_books[name]  # ใช้อ้างอิงต้นฉบับที่ป้องกันไว้ก่อนอัปโหลด
        assert len(incoming.cells) == len(expected.cells), 'Notebook structure changed.'  # ตรวจให้คำอธิบายและเซลล์วิเคราะห์ตรงต้นฉบับ
        for actual, original in zip(incoming.cells, expected.cells):  # เทียบโค้ดและ Markdown ทุกเซลล์
            actual_source = re.sub(r"MODE = '(?:live|replay)'", "MODE = '<selected>'", actual.source)  # ปรับเฉพาะค่าควบคุมโหมดดึงข้อมูลที่อนุญาต
            original_source = re.sub(r"MODE = '(?:live|replay)'", "MODE = '<selected>'", original.source)  # ปรับข้อความควบคุมของต้นฉบับด้วยกฎเดียวกัน
            actual_source = re.sub(r'SEAL_COLAB_EXPORTS = (?:True|False)', 'SEAL_COLAB_EXPORTS = <selected>', actual_source)  # อนุญาตให้เปิดค่าควบคุมการจัดแพ็กเกจ
            original_source = re.sub(r'SEAL_COLAB_EXPORTS = (?:True|False)', 'SEAL_COLAB_EXPORTS = <selected>', original_source)  # คงการตรวจอักขระส่วนอื่นของต้นฉบับทั้งหมด
            assert actual.cell_type == original.cell_type and actual_source == original_source, 'Export source differs from this package.'  # ปฏิเสธโค้ดวิเคราะห์ที่ไม่ตรงรุ่น
            if actual.cell_type == 'code':  # ตรวจผล Run all จริงรวมเซลล์จัดแพ็กเกจที่ข้ามตามค่าปกติ
                assert actual.execution_count is not None and all(o.output_type != 'error' for o in actual.outputs), 'Export is incomplete or has errors.'  # ไม่สร้างหลักฐานว่าเซลล์รันผ่านขึ้นมาเอง
        verified_books[name] = incoming  # เก็บ notebook ที่ตรวจแล้วในหน่วยความจำ
    for name, incoming in verified_books.items():  # บันทึกผลรันจริงทั้งชุดหลังตรวจครบ
        nbformat.write(incoming, ROOT / name)  # บันทึกต้นฉบับ จำนวนรัน และผลตามไฟล์ที่ส่งออกจริง
    sealed_zip, sealed_evidence = lab.make_submission(ROOT, require_executed=True)  # จัดแพ็กเกจฉบับสมบูรณ์เมื่อทุก notebook บันทึกผลรันแล้ว
    print('SEALED ZIP:', sealed_zip, '| EVIDENCE:', sealed_evidence)  # แสดงหลักฐานรันครบทั้งสี่ไฟล์
    files.download(str(sealed_zip))  # ดาวน์โหลดแพ็กเกจโครงการที่ผ่านการตรวจ
else:  # ตัวรันในเครื่องจะจัดแพ็กเกจหลังบันทึกทุกขั้น
    print('Optional Colab export sealing skipped; local run_all.py saves and seals automatically.')  # อธิบายพฤติกรรมเมื่อใช้ค่าควบคุมเริ่มต้น


## Appendix E | requirements and source references

| Requirement | Where | Evidence / status |

| C1 local/UTC days | Main p4-5 | timezone_examples.csv; rain_interval_audit.csv; source_time_contract.json |

| C2 joins / row counts | Main p5 | join_audit.json; row_inclusion.csv; cohort_ledger.csv |

| C3 missing / zero / drop | Main p5; Appendix A | missing_decisions.csv; gfas_daily_derived.csv; no target fill |

| C4 spatial scope | Main p10 | One receptor retained; source grids/region explicit |

| C5 baseline / CV / test | Main p6; p8-9 | Persistence+provider reference; maturity-purged CV; all 12 settings |

| C6 measured reference | Main p10 | Preserved separate contemporary Air4Thai/Open-Meteo point check |

| Section 6.2 knowability | Main p4; p6; p11 | Checked source/target offsets, mature labels and fold-local transforms; separate original-release audit not certified |

| Feasibility checker | Stages01/02 | Project-owned check_dataset.py; no additional instructor script |

| Reproducibility | README; four notebooks | Exact raw payloads, source/data locks, SQL parity and authentic saved cells |

| Personal submission | Final page | Student review/signature, actual repository access and 10-minute unlisted video remain external |

[1] WHO. Ambient (outdoor) air pollution (2024). https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health . Health context only.

[2] Chansuebsri et al. (2024). Chemical composition and origins of PM2.5 in Chiang Mai (Thailand) by integrated source apportionment and potential source areas. Atmospheric Environment 327,120517. https://doi.org/10.1016/j.atmosenv.2024.120517 . Motivation, not forecast-skill evidence.

[3] ECMWF. CAMS Global atmospheric composition forecast data documentation. https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation . Native forecast identity, units and nominal release schedule; ADS delay caveat.

[4] ECMWF. GFAS v1.2 data documentation. https://confluence.ecmwf.int/spaces/CKB/pages/88247734/CAMS+global+biomass+burning+emissions+based+on+fire+radiative+power+GFAS+v1.2+data+documentation . UTC means, density, assimilation and offire interpretation.

[5] Open-Meteo. Previous Runs API. https://open-meteo.com/en/docs/previous-runs-api . Forecast values at fixed offsets; not station observations or a per-origin public-release ledger.

[6] PCD/EPO8. Air4Thai PM2.5 rolling-period explanation. https://epo08.pcd.go.th/th/news/detail/180206 . Separate raw station snapshot and boundary sensitivity are preserved.

[7] ECMWF. GFAS/CAMS contamination advisory9-14 August 2024 and corrected GFAS notice. https://forum.ecmwf.int/t/issue-with-gfas-and-cams-global-forecast-outputs-due-to-contaminated-observations/3995 . Conservative date dependencies do not prove local contamination.

[8] scikit-learn. Cross-validation and common pitfalls. https://scikit-learn.org/stable/modules/cross_validation.html ; https://scikit-learn.org/stable/common_pitfalls.html . Fold-local transforms and temporal evaluation.

[9] DS-270702 HW4 PM2.5 lab sheet. Required structure/checkpoints and assessment criteria. Example PDFs inform formatting only.

Scientific counts and metrics come from the delivered raw/processed/result files. Documentation supports nominal contracts; no historical public-release timestamp is invented.


## Appendix F | development from the original model

The original notebooks, initial benchmark and current study address related but different questions. The comparison retains the initial results and identifies changes in the evaluation conditions.

| Topic | Verified original / retained strength | Development in this study |

| Original strengths | Temporal evaluation and baseline comparisons were already implemented. | Temporal evaluation and baselines are retained, with fold-local tuning and validation-only selection. |

| Hypothesis meaning | Original H1-H4 concern upwind-fire gains, total-fire gains, interactions and upwind versus total; original ladder includes PM-only/no-fire references. | H1-H4 now represent four source groups; initial fire-specific hypotheses remain distinct. |

| History length | The supplied model uses fire lags1-7, PM lag subsets and mixed rolling windows including3/7/14/30 days; it is not a single isolated five-day experiment. | Consecutive 3/5/7-day histories are compared within every source group. |

| Missing data | Covered-day fire zeros and uncovered-day missing already existed; model pipelines can median-impute remaining predictors. Median imputation is not intrinsically invalid. | A common complete-history cohort supports paired comparisons; no targets or predictors are imputed. |

| Prediction clock | Valid-date lags alone do not establish source publication at a specified clock time. | The issue is fixed at 07:00 Thai and the target is the following local day. Source offsets follow the declared nominal clocks. |

| Reproducibility | The original workflow saved metrics, predictions and configurations. | Current source/data/model receipts separate prediction from scoring and verify SQL/CSV/report consistency. |

| Predictive outcome | Initial results use different feature groups and evaluation conditions; raw MAE cannot isolate an algorithm gain. | Each selected model is compared with its own matched persistence baseline; horizon, sources and cohort changes are explained. |


## Historical numerical comparison: interpretation first

| Stage | N | Selected | Model MAE | Own B0 MAE | Skill vs own B0 |

| Initial benchmark | 102 | H3_5d | 5.720 | 6.552 | +12.7% |

| Current study | 365 | H1_3d | 6.137 | 6.282 | +2.3% |

- The initial benchmark tested a quality-screened 2026 subset; the current study tests full 2025 with a 17h lead to the next local day, explicit archived-vintage targets and different weather/fire products. Raw MAE and event frequency therefore change with evaluation conditions.

- The comparison establishes skill for each model against its own matched persistence reference. It does not identify why every numeric difference occurred or isolate a causal improvement from the algorithm. A controlled accuracy comparison across study designs would require matching target, dates and information sets.

- Structural gains are directly checked: source identities/offsets, forecast-vintage separation, area/unit calculations, mature training labels and consistent notebook/script/SQL/report evidence. Original public release and independent station forecasting remain unresolved.

Evidence: model_development_comparison.csv; reference/initial_benchmark; original_notebook_inventory.json; study_contract.json.


## AI disclosure and submission checklist

Final physical page; twelfth main-report page when appendices are excluded. Student review/signature are not supplied by automation.

| Where used | Assistance requested | Changes / rejected claims |

| Data/code | Source-clock design, acquisition/QC and all 12 comparisons. | Preserved real raw payloads; rejected target fill, false-zero conversion and invented publication timestamps. |

| Analysis | Temporal split, source/window effects and verification. | Retained baselines, validation-only selection and negative/inconclusive results; distinguished modeled targets from measured reference. |

| Report | English sections, figures, development trace and Thai line comments. | Kept original report style; separated structural progress from predictive outcomes. Student must review and explain submitted work. |

[ ] Repository is public or the instructor has access

[x] README explains execution order and dependencies

[x] Raw files are exact captured API responses with hashes

[x] Four notebooks and required scripts are included

[x] Figures and metrics are separate artifacts

[x] Five report sections and all C1-C6 answers are present

[x] Persistence and provider reference are reported alongside the models

[x] Recommendation names a decision-maker and limits

[x] AI disclosure table is supplied for student review

[ ] I personally cloned the published repository and reran it

[ ] I can explain every line and have verified the final disclosure

[ ] The required 10-minute unlisted video and links are submitted

Local technical replay evidence is distinct from a student-verified published-repository clone. The required video demonstrates the report, code and fetch process. Technical PASS does not certify original historical publication, deployment readiness or student understanding.

Student signature: __________________________   Date: __________________
