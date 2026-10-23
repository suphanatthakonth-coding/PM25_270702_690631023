# Ten-minute presentation and code-explanation guide

Preparation material for SUPHANATTHAKON THOBSRI, 690631023, 270702 Data Science Programming. The student should rewrite this outline in their own words and demonstrate understanding; this file does not certify a presentation or video.

| Time | Explain or show | Evidence to open |
|---|---|---|
| 0:00-1:00 | One Chiang Mai receptor, modeled PM outcome, decision-maker and three lab questions. Distinguish modeled exposure from measured ground truth | Report p1 and severity figure |
| 1:00-2:00 | Issue today D07 Thai; predict the whole next local day. Explain row anchor D-1, target anchor+2 and source offsets | Report pp3-4; source_time_contract.json |
| 2:00-3:15 | Show real fetch code and run a separate small public capture; explain exact raw bytes, requests/hashes and why study replay is frozen | src/fetch_data.py; src/weather_acquisition.py; acquisition command below |
| 3:15-4:30 | Explain calendar-first join, every-column missingness, no imputation, source zeros and exclusions. A zero is not automatically a missing value | Report p5; join_audit.json; missing_decisions.csv; row_inclusion.csv |
| 4:30-5:30 | Explain H1-H4 x3/5/7, Ridge regularisation, fold-local scaling and temporal CV. Show train/validation/test and label maturity | 02_prepare_data.ipynb; 04_model.ipynb; cv_calendar_audit.csv |
| 5:30-7:00 | Baselines first, same test dates, validation-only selected H1_3d. Explain answer-free prediction versus previously inspected historical test | 04_model.ipynb; selection.json; model_scores.csv |
| 7:00-8:00 | MAE versus warning recall; selected misses23/30, persistence19/30, provider10/30. Weather/fire comparisons are exploratory, not causal | Report pp8-10; paired_comparisons.csv |
| 8:00-9:15 | Named audience, timing and stop conditions. Explain FP+r*FN and why the selected model is worse than persistence when r>2.75 | Report p11; decision_cost_scenarios.csv |
| 9:15-10:00 | Actual-publication limitation, source dependence, C6 scope, reproducibility evidence and AI disclosure | Final report page; SUBMISSION_STATUS.json; archive validation |

## Real acquisition demonstration

From the extracted project folder, with the environment installed:

```text
python src/fetch_data.py --acquire-weather data/raw/video_weather_capture
```

This runs the same real public downloader for the two original annual weather requests (17,544 hourly rows), writes exact response bytes and separate transfer/schema receipts, and never overwrites the frozen scientific snapshot. Start a fresh capture folder for a new demonstration: rerunning an already verified capture correctly resumes without another HTTP request. Network/provider latency may exceed the clip; it is acceptable to start before recording and explain the real log and request, without presenting a replay or resume as a new transfer.

The full study acquisition is `python src/fetch_data.py --acquire-new NEW_PERSISTENT_CAPTURE_FOLDER --max-new-jobs 50`; it needs a personal ADS token at a hidden prompt and may take much longer. No key should appear in the recording or submitted files. The required lab fetch entry point delegates to the shared acquisition modules.

## Questions to practise

1. Why is target shifted by minus two rows? Row date is D-1, issue D07, target D+1: target date is anchor+2, not an accidental two-day-ahead issue.
2. Why not fill missing PM/weather/fire with zero? It would invent physical values and training histories. Eligibility requires complete calendar windows; raw missingness and reasons remain visible.
3. Why keep a long GFAS zero stretch? The decoded source field actually contains zeros; these are neither project imputation nor evidence that all real fires were absent. Explain source coverage and observation-opportunity limitations.
4. Why are all settings on the same dates? Otherwise apparent improvement could come from a different seasonal/quality subset. Do not drop hard-to-predict test days separately for each setting.
5. Why leave a gap before validation? A next-day daily label is not complete at the next early forecast issue. Show the maturity inequality in cv_calendar_audit.csv.
6. Why use StandardScaler inside the pipeline? Fold means/scales must be fitted only on the training fold; Ridge penalisation depends on feature scale. HGB has its own declared grid.
7. Why not switch to H2_3d after seeing its better test score? Selection used validation; reselecting on test would exploit already inspected answers.
8. Did the model improve? Structure/provenance improved. Selected point MAE is lower than persistence, the paired interval spans zero, warning misses are worse, and the provider forecast is substantially better. Old/new datasets have different targets/periods and cannot isolate an algorithm gain.
9. Does no test answer in predict prove a blind test? No. It verifies the software interface; the historical dataset was previously inspected and remains retrospective.
10. Does a timestamp or hash prove past public availability? No. Current receipts establish current transfer; nominal model clocks and hashes establish different claims. Original release/revision remains unverified and the operational gate stays blocked.
11. Why only one city? The lab requires two sources or endpoints, not two cities. A regional fire box supplies a predictor; it is not another independent PM site.
12. Is CAMS versus Air4Thai a ground-truth accuracy study? The preserved contemporary point comparison meets that comparison task for its captured product; it cannot validate all historical ADS outcomes or resolve grid/window/measurement differences.
13. Is lower MAE sufficient for school warnings? No. Explain threshold recall, FN harm, FP disruption, agreed costs and why this prototype should not automatically issue warnings.

## Functions worth being able to explain

Trace the notebook calls into src/prepare_data.py (prepare_daily, build_experiments), src/model.py (partition_rows and training/CV), src/evaluate_forecast.py (lock_experiment and receipts), src/stages.py (commit_predictions, score_and_diagnose), src/reference_store.py (SQL checks), and src/availability.py (operational rejection). Use the actual source when practising rather than memorising a function's name.
