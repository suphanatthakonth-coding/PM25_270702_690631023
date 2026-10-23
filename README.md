# Chiang Mai PM2.5 Forecasting

Four-stage, nominal-source-clock-constrained **retrospective** benchmark. Issue D07:00 Thailand; predict the next local day P(D+1). CAMS modeled profiles are the outcome; a preserved contemporary station comparison is separate. Actual original historical public release/revision is not certified and operational prediction is blocked.

## Run the delivered project

Use Python 3.12 in a new environment. Install `requirements-lock.txt`, then run from the extracted project folder:

```text
python -m pip install -r requirements-lock.txt
python run_all.py --mode replay
```

This executes and saves the four actual notebooks in order, in separate fresh kernels; rebuilds the report after the final saved cells; checks metrics, locks, SQL values and report inputs; and seals a ZIP. Default mode uses the exact actual API responses captured by the student. It does not fabricate/relabel earlier execution counts. A CPU is sufficient.

For the script route, use a clean copy with empty generated outputs, preserving raw inputs/fonts/configuration:

```text
python src/fetch_data.py
python src/prepare_data.py
python src/analyse.py
python src/model.py
```

The scripts call the same shared orchestration as notebooks. Script execution alone does not create notebook execution counts. The final package separately includes authentic four-notebook execution evidence.

## New authenticated acquisition

The raw source acquisition logic is visible in `src/ads_bulk_acquisition.py`. To request the same full ADS period again without changing this frozen study, use:

```text
python src/fetch_data.py --acquire-new NEW_PERSISTENT_CAPTURE_FOLDER --max-new-jobs 50
```

The required fetch entry point delegates to the same real API acquisition logic in `tools/acquire_ads.py` and `src/ads_bulk_acquisition.py`; no rules are duplicated. Enter an ADS token only at the hidden prompt; personally accept provider terms when required. Keep the same capture folder for resume. It saves request IDs, blocks uncertain submission retries, verifies prior hashes and exports COMPLETE/PARTIAL evidence. No token is saved. A failed/uncertain job requires inspecting the existing ADS request, not deleting state or blindly resubmitting. The weather responses used by the delivered study are preserved separately with their original public API requests and hashes.

## Scientific design

- H1 PM; H2 PM+weather; H3 PM+fire; H4 all. Each uses 3/5/7-day histories, on one shared cohort.
- PM P(d): ADS run d-1 at 12 UTC, leads 5-28, exactly 24 instantaneous samples. Separate provider reference uses the earlier run and leads 29-52 for the target day.
- Weather: GFS previous_day1 forecast values, not ERA5 observations; local means and interval-correct rain totals. Derive hourly wind u/v before averaging.
- Fire: GFAS v1.2 UTC daily analysis. Latest nominal history day at D07Thai is D-2. Integrate W/m2 using cell areas to mean power MW; positive-analysis-area fraction is not hotspots/burnt area. offire is QC, may exceed 1, and is not clipped or predicted.
- Full study calendar 731 days; value-complete 704; conservative advisory dependencies 15 days; outer maturity purges 2 days; modeling cohort 687. Train 231, validation 91, full 2025 test 365. These rules were fixed before new scores.
- No target or predictor imputation. A long native zero-analysis stretch is not project-filled missing and does not prove absence of real fires.
- Primary Ridge and secondary HGB grids, fold-local scaling, fixed threshold 37.5, primary 14-day block intervals and validation-only selection are preserved. All 12 settings are reported. Test is previously explored historical data, not a newly blind/prospective validation.

## Structure

```text
01_fetch_data.ipynb        actual captured-response and native GRIB validation
02_prepare_data.ipynb      calendar, features, source clocks, missing/quality and label maturity
03_analyse.ipynb           severity, seasonality, source quality and spatial scope
04_model.ipynb             lock -> answer-free prediction -> score -> report/evidence
src/                      shared logic and four required script entry points
tools/                    acquisition/sealing helpers
data/raw/                 exact returned payloads and original receipts
data/interim/             native exports and area-derived GFAS summaries
data/processed/            daily/features, separate answers and SQLite audit store
outputs/figures/           separate PNG/PDF figures and captions
outputs/results/           metrics, twelve answers, chronology, provenance and checks
report/                   report.pdf, one-page proposal.pdf, grey code listing, metadata/fonts
reference/                initial notebook inventory and benchmark comparison results
tests/                    targeted regressions
```

## Interpretation and submission

The report retains the established fonts, margins, page structure, English explanation and grey code cells with Thai comments. Structural changes are distinguished from accuracy outcomes. Raw MAE across different study designs cannot isolate algorithm improvement when target vintage, horizon, period and cohort change.

Temporal-cutoff, label-maturity and fold-local preprocessing checks address Section 6.2 under the declared retrospective design. They do not certify exact historical public release/revision, deployment, student understanding or external submission. See `SUBMISSION_STATUS.json` and `SUBMISSION_GUIDE.md`; never mark these personal tasks completed automatically.

## Public weather acquisition

For real public weather acquisition, from the project folder run:

```text
python src/fetch_data.py --acquire-weather data/raw/weather_new_capture
```

The exact two original annual requests are used. Raw response bytes, timestamps, HTTP status, hashes and schema/calendar checks are saved; verified successes resume without new requests. Source nulls stay null. A separate actual successful capture is included under data/raw/weather_verified_new_capture. Fresh API files can differ in metadata or revised values: they are never substituted into the frozen study silently. The optional FETCH_NEW_WEATHER notebook flag calls the same function. ADS acquisition still needs your own hidden token.

C6 is a real one-time station/Open-Meteo comparison, satisfying that comparison task for the captured product; it does not validate the separate ADS target historically. Actual historical public availability and operational station-forecast skill remain unverified. Do not change test selection or replace old receipts after modifying src.

## Independent checks

After preparation or a completed replay:

```text
python src/check_dataset.py data/processed/final_dataset_daily.csv --target pm25_tomorrow --time date --fetch-script src/fetch_data.py
python -m unittest discover -s tests -v
```

The project-owned checker reports FEASIBLE WITH ISSUES for this qualified retrospective scope. Technical PASS is distinct from historical source-publication verification. See VERIFICATION.md and the evidence files under outputs/results.

## Start here before submission

- `RUBRIC_EVIDENCE.md`: required sections, C1-C6 and supporting files.
- `ORAL_DEMO_GUIDE.md`: ten-minute outline and real acquisition demonstration.
- `SUBMISSION_GUIDE.md`: personal review, repository access/clone and video/link steps.
- `VERIFICATION.md`: technical checks and the scope of the evidence.

Clean Windows environment, from this extracted project folder:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe run_all.py --mode replay
```

Keep `.venv`, credentials and local caches out of the repository. Archived study replay needs no ADS token. New ADS acquisition needs the user's own accepted terms and hidden token. Reviewer marks are not scientific results; no grade is included or guaranteed. Current technical evidence is under outputs/results. The initial benchmark under reference supports the model-development discussion; it is not a current execution receipt.
