# Submission checklist

## Files to retain in the GitHub repository

Keep the four root notebooks, required `src/fetch_data.py`, `prepare_data.py`, `analyse.py`, `model.py` and their shared modules, both requirements files, configuration/plan/dictionaries, exact `data/raw`, generated `data/interim` and `data/processed`, separate `outputs/figures` and `outputs/results`, and the complete `report` folder. Keep proposal.pdf and feasibility_report.txt. The full folder structure is documented in README.md. Do not upload the enclosing ZIP into the repository as a substitute for these files.

## Required personal steps, in order

1. Read report/report.pdf, particularly the target, missing-data decisions, baseline comparison and limits. Read the actual shared functions called by the notebooks. Practise with ORAL_DEMO_GUIDE.md.
2. Review the final-page AI disclosure against the assistance actually used. Complete any required signature/date personally. No signature or claim of understanding is supplied automatically. If changing the PDF after sealing, retain the final edited version and identify it as a student-edited report; its old PDF hash will no longer apply. A PDF modification does not justify changing data, model selection or results.
3. Create/update the actual GitHub repository and confirm that the instructor can access it. Keep secrets and local environments out. Raw scientific payloads, provenance, code, separate figures/results and the report must remain accessible.
4. Clone that published repository into a fresh folder, create a new Python 3.12 environment, install requirements-lock.txt and run `python run_all.py --mode replay`. Save the actual log. A local ZIP replay is useful technical evidence but does not certify access or cloning from that published repository.
5. Record a 10-minute video explaining the report, code and fetch process. Show a real separate public weather request or your hidden authenticated ADS acquisition process. Explain archived replay versus new acquisition. Do not expose a token or claim that a full multi-year ADS download finishes during the clip.
6. Publish the clip as unlisted, verify that its actual URL opens with the intended access, and submit the actual GitHub and video links through the course channel. Verify instructor repository access before submitting.

## Interpretation to preserve

The package is a reproducible retrospective benchmark of modeled daily PM, with operational availability blocked. It contains a real contemporary station comparison, not year-long measured validation. The selected model has lower point MAE than persistence but misses more modeled exceedances and loses to the direct-provider reference. These are findings to explain, not results to hide.

Do not mark the unchecked personal items in the final report or SUBMISSION_STATUS.json completed unless you actually performed them. No numeric grade is guaranteed.
