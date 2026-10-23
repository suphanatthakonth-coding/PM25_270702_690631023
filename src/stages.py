"""Shared stage orchestration for notebooks and the four required script entry points.

Notebook cells retain visible explanations and stage boundaries. These functions own
the same side effects in both routes, preventing dependence on old generated files.
"""


def prepare_handoff(root,cfg,daily,X,specs,eligible):
    from check_dataset import check_dataset,require_pass
    from evaluate_forecast import export_inputs
    from diagnostics import preparation_diagnostics
    from reference_store import build_reference_store
    checks=require_pass(check_dataset(root,cfg,daily,X,specs,eligible))
    inputs=export_inputs(root,cfg,daily,X,specs,eligible)
    coverage=preparation_diagnostics(root,cfg,daily,X,eligible)
    reference=build_reference_store(root)
    return {'checks':checks,'inputs':inputs,'coverage':coverage,'reference':reference}


def commit_predictions(root):
    """Prediction and SQL commitment use no test answers; scoring is separate."""
    from evaluate_forecast import predict_blind
    from reference_store import store_committed_predictions
    receipt=predict_blind(root)
    stored=store_committed_predictions(root)
    return receipt,stored


def score_and_diagnose(root,cfg):
    from evaluate_forecast import evaluate_predictions
    from diagnostics import model_diagnostics
    scores,comparisons=evaluate_predictions(root)
    diagnostic=model_diagnostics(root,cfg)
    return scores,comparisons,diagnostic


def report_ready_artifacts(root,cfg,daily,X,specs,eligible):
    from report_assets import make_workflow,decision_evidence
    from reference_store import verify_reference_store
    from workflow import verify_science
    make_workflow(root,cfg)
    scenarios=decision_evidence(root,cfg)
    reference=verify_reference_store(root)
    science=verify_science(root,cfg,daily,X,specs,eligible)
    return {'science':science,'reference':reference,'decision_scenarios':scenarios}


def run_model_stage(root,cfg):
    """Complete script stage04, after the same prepare/describe handoffs as notebooks."""
    from workflow import load_prepared
    from prepare_data import build_experiments
    from check_dataset import check_dataset,require_pass
    from evaluate_forecast import lock_experiment
    from analyse import model_figures
    from report import build_report
    daily=load_prepared(root,cfg);X,specs,eligible=build_experiments(root,cfg,daily)
    require_pass(check_dataset(root,cfg,daily,X,specs,eligible))
    lock_experiment(root,cfg)
    commit_predictions(root)
    scores,comparisons,diagnostic=score_and_diagnose(root,cfg)
    model_figures(root,cfg,scores)
    report_ready_artifacts(root,cfg,daily,X,specs,eligible)
    return build_report(root,cfg)
