# Lab requirements and evidence map

This is an index to existing evidence, not a replacement for the required report and not the instructor's marking decision. Paths below are relative to this project. Main report page references refer to its physical pages, except the final-page disclosure.

| Rubric item | What the package demonstrates | Where to inspect | Remaining qualification |
|---|---|---|---|
| Acquisition/reproducibility (15) | Preserved real API bytes; request identities, dates, hashes, units and schema; script and notebook entry points | README.md; src/fetch_data.py; src/ads_bulk_acquisition.py; src/weather_acquisition.py; data/raw; outputs/results/raw_checks.json; weather_raw_audit.json | New ADS acquisition needs the student's account/terms; publication access and a clone of the actual GitHub repository are separate personal steps |
| Data quality (15) | Calendar-first alignment, no predictor/target imputation, native zero distinction, explicit exclusions and source grids | Report pp4-5, appendix A; outputs/results/join_audit.json; missingness.csv; missing_decisions.csv; row_inclusion.csv; station_coordinate_grid_audit.json | Model-source completeness does not imply measurement completeness or original public availability |
| Visualisation/interpretation (15) | Separate labelled figures, severity/seasonality, source quality, model comparisons and warning failures | Report pp1,3,6-10; outputs/figures; outputs/results/annual_summary.csv; monthly_summary.csv | One receptor and two study years do not establish provincial exposure or a long-term trend |
| Machine-learning method (20) | Fixed forecast target; later test; maturity purges; temporal CV; fold-local scaling; baselines; validation selection; answer-free prediction and metrics | Report pp2,4-5,7-10; outputs/results/cv_calendar_audit.csv; experiment_specs.json; tuning.json; selection.json; forecast_lock.json; prediction_receipt.json; evaluation_receipt.json | Source/target offsets, label maturity and fold-local transforms address temporal knowability. Exact historical release/revision is a separate unverified operational audit |
| Recommendation (20) | Named principal/analytics audience, timing, proposed actions, stopping gate and FP/FN cost sensitivity | Report p11; outputs/results/decision_cost_scenarios.csv; missed_day_details.csv | Proposed workflow and illustrative costs are not adopted school policy or validated utility |
| Report (10) | English fixed five-section format; 12 main pages excluding appendices; traceable figures/tables; final-page AI disclosure | report/report.pdf; report/report_provenance.json; configuration_dictionary.csv; outputs/results/data_dictionary.csv | Student must verify disclosure and explain the work |
| Oral defence (5) | Preparation outline and runnable acquisition/replay examples provided | ORAL_DEMO_GUIDE.md; README.md | Unassessed until the student presents and explains it |

## Required checkpoint answers

| Checkpoint | Answer and evidence | Scope |
|---|---|---|
| C1 time | Report pp4-5; timezone_examples.csv, rain_interval_audit.csv, source_time_contract.json, raw native time/lead exports | Thai local PM/weather days and UTC GFAS days are explicitly different; interval-start precipitation alignment is checked |
| C2 join | Report p5; join_audit.json; row_inclusion.csv | 739 PM profiles, 17,544 native weather hours and 740 UTC GFAS days; 739 calendar rows before/after alignment. 731 study targets ->704 complete ->689 advisory-safe ->687 maturity-safe |
| C3 missing | Report p5 and appendix A; missingness.csv, missing_decisions.csv, raw_checks.json | Every daily column has a denominator; no target/predictor fill. Native all-zero GFAS runs are retained analysis values, not proof of no fires |
| C4 places | Report p10; spatial_resolution_audit.json, station_coordinate_grid_audit.json | One primary PM receptor, explicitly different source grids. A fire bounding box is not a second city; no independent spatial comparison is invented |
| C5 baseline | Report pp7-11; model_scores.csv, validation_scores.csv, paired_comparisons.csv, selection.json | Same 365 test dates; validation-selected candidate retained despite another setting's lower test MAE; disagreement across periods is explained |
| C6 ground truth | Report p10; station_crosscheck.csv/json, preserved raw station/Open-Meteo responses | Real 16 October 2026 point comparison for that captured modeled product, with station-QA reference priority and grid/window limitations. It is not direct historical ADS target validation |

## Three problem questions and twelve experimental settings

- Severity, where and when: one requested Chiang Mai receptor; modeled daily/annual/monthly evidence, not measured provincial exposure.
- Useful tomorrow warning: D07 Thai issue, target D+1; primary Ridge and secondary HGB compare H1 PM, H2 PM+weather, H3 PM+fire, H4 all at 3/5/7 days on identical dates. No automatic-warning recommendation is supported by the selected model's failures.
- Who should act, and when: report p11 supplies a proposed principal/analytics decision procedure, missing-input stop gate and false-negative/false-positive consequences.

There are twelve feature/window settings per learner. H4 supplies two conditional source comparisons; therefore the paired-comparison count is not twelve. All intervals are exploratory pointwise intervals, not causal or multiplicity-adjusted confirmations.

## Evidence integrity

Current source-bound acceptance, regression and independent script-route checks are under outputs/results. The sibling PM25_270702_690631023_Archive_Verification.json binds actual fresh replay to the final delivered ZIP SHA256. The initial benchmark under reference is retained only for the scientific development comparison. No old receipt is represented as a new execution, and no reviewer grade is included in the submission.
