"""Lock -> predict without test answers -> open answers and score.

This is software-interface separation on a previously explored historical dataset.
It is not a new blind study, a sandbox against a malicious analyst, or issue-time proof.
Only load model files created by this trusted project; joblib is not a safe interchange format.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,uuid
import numpy as np
import pandas as pd
import joblib
from common import write_json,sha256,load_config


def export_inputs(root,cfg,daily,X,specs,eligible):
    from model import calendar_cv,partition_rows
    folder=root/'data/processed/evaluation_inputs';folder.mkdir(exist_ok=True)
    indices=partition_rows(daily,eligible,cfg)
    folds,records=calendar_cv(daily,eligible,indices['train'],cfg)
    write_json(folder/'cv_indices.json',[{'train':a.tolist(),'validation':b.tolist()} for a,b in folds])
    pd.DataFrame(records).to_csv(root/'outputs/results/cv_calendar_audit.csv',index=False)
    chronology=[]
    for name,rows in indices.items():
        features=pd.concat([daily.iloc[rows][['date','target_date','forecast_origin_utc']].reset_index(drop=True),X.iloc[rows].reset_index(drop=True)],axis=1)
        features['B0_persistence']=daily.pm25_mean.iloc[rows].to_numpy()
        features['B1_provider_forecast']=daily.provider_forecast.iloc[rows].to_numpy()
        if name=='test':
            features.to_csv(folder/'test_features.csv',index=False)
            truth=daily.iloc[rows][['date','target_date','pm25_tomorrow']].rename(columns={'pm25_tomorrow':'y_true'})
            truth.to_csv(folder/'test_answers.csv',index=False)
        else:
            features['y_true']=daily.pm25_tomorrow.iloc[rows].to_numpy()
            features.to_csv(folder/(name+'.csv'),index=False)
        chronology.append({'partition':name,'n':len(rows),'first_target':str(daily.target_date.iloc[rows[0]]),
            'last_target':str(daily.target_date.iloc[rows[-1]]),'first_issue_utc':str(daily.forecast_origin_utc.iloc[rows[0]]),
            'last_label_complete_utc':str(daily.target_complete_utc.iloc[rows[-1]]),
            'positive_days':int(daily.pm25_tomorrow.iloc[rows].gt(cfg['warning_threshold']).sum())})
    pd.DataFrame(chronology).to_csv(root/'outputs/results/chronology.csv',index=False)
    record={'status':'EXPORTED_SEPARATE_FEATURES_AND_ANSWERS','test_rows':len(indices['test']),
        'prediction_inputs':'No y_true/pm25_tomorrow/exceed_tomorrow; B1 is a separately identified provider reference.',
        'answers':'Opened only after locked prediction commitment; SQL answer tables are not read by prediction.',
        'outer_label_purge_target_days':cfg['outer_label_purge_target_days'],
        'scope':'Retrospective benchmark after prior inspection; interface separation does not create an unseen prospective test.'}
    write_json(folder/'input_contract.json',record)
    return record


def _verify_lock(root,plan,include_answers=False):
    for name,digest in plan['locked_artifacts'].items():
        if sha256(root/name)!=digest:raise ValueError('Frozen artifact changed: '+name+'; relock and rerun predictions.')
    if include_answers:
        if sha256(root/plan['answer_file'])!=plan['answer_sha256']:raise ValueError('Test answers changed after experiment lock.')
        for name,digest in plan['provenance_artifacts'].items():
            if sha256(root/name)!=digest:raise ValueError('Upstream dataset changed after experiment lock: '+name)


def lock_experiment(root,cfg):
    from model import fit_training_and_validation
    from check_dataset import check_dataset,require_pass
    require_pass(check_dataset(root,cfg))
    from source_contract import materialize_source_contract
    materialize_source_contract(root,cfg)
    inputs=root/'data/processed/evaluation_inputs'
    features=pd.read_csv(inputs/'test_features.csv',float_precision='round_trip')
    if any(name in features for name in ['y_true','pm25_tomorrow','exceed_tomorrow']):raise ValueError('Answers leaked into test features.')
    models,majority,selection=fit_training_and_validation(root,cfg)
    paths=[root/'outputs/results/feature_availability.csv',root/'config.json',root/'analysis_plan.json',
        root/'configuration_dictionary.csv',root/'report/study_metadata/source_time_contract.json',
        root/'outputs/results/source_time_contract.json',*sorted((root/'src').glob('*.py')),
        inputs/'train.csv',inputs/'validation.csv',inputs/'test_features.csv',inputs/'cv_indices.json',inputs/'input_contract.json',
        root/'outputs/results/experiment_specs.json',root/'outputs/results/predictions_validation.csv',
        root/'outputs/results/validation_scores.csv',root/'outputs/results/tuning.json',root/'outputs/results/selection.json',
        *[root/item['path'] for item in models]]
    evidence_path=root/'data/processed/availability_evidence.csv'
    if evidence_path.is_file():
        paths.append(evidence_path)
        evidence=pd.read_csv(evidence_path)
        if 'evidence_file' in evidence:
            for name in evidence.evidence_file.dropna().unique():
                candidate=(root/str(name)).resolve()
                if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():raise ValueError('Invalid availability evidence path.')
                paths.append(candidate)
    plan={'run_id':uuid.uuid4().hex,'locked_at_utc':datetime.now(timezone.utc).isoformat(),
        'study_status':'EXPLORATORY_HISTORICAL_REPLAY_PREVIOUSLY_EXPLORED','models':models,'selection':selection,
        'warning_threshold':cfg['warning_threshold'],'majority_test_is_exceedance':majority,
        'feature_file':(inputs/'test_features.csv').relative_to(root).as_posix(),
        'answer_file':(inputs/'test_answers.csv').relative_to(root).as_posix(),
        'answer_sha256':sha256(inputs/'test_answers.csv'),
        'provenance_artifacts':{name:sha256(root/name) for name in ['data/processed/final_dataset_daily.csv','data/processed/all_seven_day_features.csv']},
        'locked_artifacts':{path.relative_to(root).as_posix():sha256(path) for path in paths}}
    # A new run invalidates old prediction/evaluation receipts; no old PASS is reused.
    for name in ['prediction_receipt.json','evaluation_receipt.json','seal_verification.json']:
        (root/'outputs/results'/name).unlink(missing_ok=True)
    write_json(root/'outputs/results/forecast_lock.json',plan)
    return plan


def predict_blind(root,require_operational=False):
    """Read frozen models and answer-free features only; never open test_answers.csv."""
    plan=json.loads((root/'outputs/results/forecast_lock.json').read_text())
    _verify_lock(root,plan)
    features=pd.read_csv(root/plan['feature_file'],float_precision='round_trip')
    if require_operational:
        from availability import validate_operational_inputs
        validate_operational_inputs(root,plan,features)
    wanted={'date','target_date','forecast_origin_utc','B0_persistence','B1_provider_forecast'}|{feature for model in plan['models'] for feature in model['features']}
    if set(features)!=wanted:raise ValueError('Unexpected prediction columns; refuse answers or undeclared predictors.')
    predictions=features[['date','target_date']].copy()
    predictions['B0_persistence']=features.B0_persistence
    predictions['B1_provider_forecast']=features.B1_provider_forecast
    predictions['C0_training_majority']=float(plan['warning_threshold']+1 if plan['majority_test_is_exceedance'] else 0)
    for item in plan['models']:
        fitted=joblib.load(root/item['path'])
        predictions[item['column']]=np.maximum(0,fitted.predict(features[item['features']]))
    if predictions.isna().any().any():raise ValueError('Missing predictions cannot be silently scored on different dates.')
    path=root/'outputs/results/predictions_test_blind.csv';predictions.to_csv(path,index=False)
    receipt={'run_id':plan['run_id'],'locked_plan_sha256':sha256(root/'outputs/results/forecast_lock.json'),
        'predicted_at_utc':datetime.now(timezone.utc).isoformat(),'prediction_sha256':sha256(path),
        'rows':len(predictions),'input_columns':features.columns.tolist(),
        'test_answers_opened_by_prediction_stage':False,'scope':'Interface isolation on previously explored historical data; not independent prospective validation.'}
    (root/'outputs/results/evaluation_receipt.json').unlink(missing_ok=True)
    write_json(root/'outputs/results/prediction_receipt.json',receipt)
    return receipt


def evaluate_predictions(root):
    """Open committed answers only after checking the prediction receipt and lock."""
    from model import metric_values,summarize_results
    plan=json.loads((root/'outputs/results/forecast_lock.json').read_text())
    receipt=json.loads((root/'outputs/results/prediction_receipt.json').read_text())
    _verify_lock(root,plan,include_answers=True)
    prediction_path=root/'outputs/results/predictions_test_blind.csv'
    if receipt['run_id']!=plan['run_id'] or receipt['locked_plan_sha256']!=sha256(root/'outputs/results/forecast_lock.json') or receipt['prediction_sha256']!=sha256(prediction_path):
        raise ValueError('Prediction receipt does not match current lock/predictions.')
    predictions=pd.read_csv(prediction_path,float_precision='round_trip')
    answers=pd.read_csv(root/plan['answer_file'],float_precision='round_trip')
    keys=['date','target_date']
    if predictions[keys].duplicated().any() or answers[keys].duplicated().any():raise ValueError('Duplicate evaluation dates.')
    table=answers.merge(predictions,on=keys,how='outer',validate='one_to_one',indicator=True)
    if not table['_merge'].eq('both').all():raise ValueError('Predictions and answers do not cover exactly the same dates.')
    table=table.drop(columns='_merge')
    if table.isna().any().any():raise ValueError('Evaluation contains missing answers or predictions.')
    rows=[]
    for item in [{'column':'B0_persistence','family':'baseline','experiment':'B0_persistence','hypothesis':'baseline','window':1},
        {'column':'B1_provider_forecast','family':'baseline','experiment':'B1_provider_forecast','hypothesis':'provider_reference','window':0},
        {'column':'C0_training_majority','family':'baseline','experiment':'C0_training_majority','hypothesis':'warning_only','window':0},*plan['models']]:
        values=metric_values(table.y_true,table[item['column']],plan['warning_threshold'])
        if item['hypothesis']=='warning_only':values={key:value for key,value in values.items() if key not in ['MAE','RMSE']}
        rows.append({'partition':'test',**{key:item[key] for key in ['family','experiment','hypothesis','window']},**values})
    validation_scores=pd.read_csv(root/'outputs/results/validation_scores.csv',float_precision='round_trip')
    scores=pd.concat([validation_scores,pd.DataFrame(rows)],ignore_index=True)
    scores.to_csv(root/'outputs/results/model_scores.csv',index=False)
    (root/'outputs/results/metrics.csv').write_bytes((root/'outputs/results/model_scores.csv').read_bytes())
    table.to_csv(root/'outputs/results/predictions_test.csv',index=False)
    cfg=json.loads((root/'config.json').read_text())
    pairs=summarize_results(root,cfg,scores,{'test':table})[1]
    bound=['predictions_test_blind.csv','predictions_test.csv','predictions_validation.csv','model_scores.csv','metrics.csv',
        'paired_comparisons.csv','twelve_answers.csv','window_selection_by_group.csv']
    write_json(root/'outputs/results/evaluation_receipt.json',{'run_id':plan['run_id'],
        'evaluated_at_utc':datetime.now(timezone.utc).isoformat(),'prediction_receipt_sha256':sha256(root/'outputs/results/prediction_receipt.json'),
        'answer_sha256':sha256(root/plan['answer_file']),'result_hashes':{name:sha256(root/'outputs/results'/name) for name in bound},
        'scope':'Previously explored historical replay; successful evaluation does not prove issue-time availability or warning deployment readiness.'})
    return scores,pairs


def verify_receipts(root):
    plan=json.loads((root/'outputs/results/forecast_lock.json').read_text())
    _verify_lock(root,plan,include_answers=True)
    prediction=json.loads((root/'outputs/results/prediction_receipt.json').read_text())
    evaluation=json.loads((root/'outputs/results/evaluation_receipt.json').read_text())
    if prediction['run_id']!=plan['run_id'] or evaluation['run_id']!=plan['run_id']:raise ValueError('Run identity changed.')
    if prediction['locked_plan_sha256']!=sha256(root/'outputs/results/forecast_lock.json'):raise ValueError('Lock changed after prediction.')
    if evaluation['prediction_receipt_sha256']!=sha256(root/'outputs/results/prediction_receipt.json'):raise ValueError('Prediction receipt changed after scoring.')
    if prediction['prediction_sha256']!=sha256(root/'outputs/results/predictions_test_blind.csv'):raise ValueError('Committed predictions changed.')
    for name,digest in evaluation['result_hashes'].items():
        if sha256(root/'outputs/results'/name)!=digest:raise ValueError('Evaluated output changed: '+name)
    times=[pd.Timestamp(plan['locked_at_utc']),pd.Timestamp(prediction['predicted_at_utc']),pd.Timestamp(evaluation['evaluated_at_utc'])]
    if times!=sorted(times):raise ValueError('Lock/predict/evaluate timestamps are out of order.')
    return {'status':'PASS','run_id':plan['run_id'],'ordered_stages':['lock','predict_without_answers','open_answers_and_score'],
        'scope':'Integrity and interface checks; not a claim that previously explored data became an unseen test.'}


def verify_saved_results(root,cfg):
    """Recalculate all 54 score rows and validate committed output identity before packaging."""
    receipt=verify_receipts(root)
    scores=pd.read_csv(root/'outputs/results/model_scores.csv',float_precision='round_trip')
    if sha256(root/'outputs/results/metrics.csv')!=sha256(root/'outputs/results/model_scores.csv'):raise ValueError('Canonical metrics file differs.')
    inputs=root/'data/processed/evaluation_inputs'
    train=pd.read_csv(inputs/'train.csv',float_precision='round_trip')
    validation=pd.read_csv(inputs/'validation.csv',float_precision='round_trip')
    checked=0
    for partition in ['validation','test']:
        table=pd.read_csv(root/f'outputs/results/predictions_{partition}.csv',float_precision='round_trip')
        answers=validation[['date','target_date','y_true']] if partition=='validation' else pd.read_csv(inputs/'test_answers.csv',float_precision='round_trip')
        if not table[['date','target_date']].equals(answers[['date','target_date']]):raise ValueError('Evaluation date identity changed.')
        np.testing.assert_array_equal(table.y_true,answers.y_true)
        fit_labels=train.y_true if partition=='validation' else pd.concat([train.y_true,validation.y_true])
        majority=float(cfg['warning_threshold']+1 if fit_labels.gt(cfg['warning_threshold']).mean()>.5 else 0)
        np.testing.assert_array_equal(table.C0_training_majority,np.repeat(majority,len(table)))
        for row in scores[scores.partition.eq(partition)].itertuples():
            column=row.experiment if row.family=='baseline' else row.family+'__'+row.experiment
            truth=table.y_true.to_numpy();prediction=table[column].to_numpy()
            if not np.isfinite(prediction).all() or not np.isfinite(truth).all():raise ValueError('Nonfinite prediction or label.')
            event=truth>cfg['warning_threshold'];warning=prediction>cfg['warning_threshold']
            tp=int((event&warning).sum());tn=int((~event&~warning).sum());fp=int((~event&warning).sum());fn=int((event&~warning).sum())
            independent={'n':len(truth),'TP':tp,'TN':tn,'FP':fp,'FN':fn,'positive_days':int(event.sum()),'threshold':cfg['warning_threshold'],
                'precision':tp/(tp+fp) if tp+fp else np.nan,'recall':tp/(tp+fn) if tp+fn else np.nan,
                'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else np.nan}
            if row.experiment!='C0_training_majority':
                independent.update(MAE=float(np.mean(np.abs(truth-prediction))),RMSE=float(np.sqrt(np.mean((truth-prediction)**2))))
            for key,value in independent.items():
                if not np.isclose(getattr(row,key),value,rtol=1e-10,atol=1e-10,equal_nan=True):raise ValueError(f'Stale or incorrect {partition}/{column}/{key}.')
            checked+=1
    selected=scores[scores.partition.eq('validation')&scores.family.eq(cfg['primary_family'])].sort_values(['MAE','window','experiment']).iloc[0]
    selection=json.loads((root/'outputs/results/selection.json').read_text())
    if selection['experiment']!=selected.experiment:raise ValueError('Primary choice does not match validation-only selection.')
    return {**receipt,'independently_recomputed_metric_rows':checked}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['export','lock','predict','score','verify'])
    parser.add_argument('--require-operational',action='store_true')
    args=parser.parse_args();root,cfg=load_config()
    if args.stage=='export':
        from workflow import load_prepared
        from prepare_data import build_experiments
        daily=load_prepared(root,cfg);X,specs,eligible=build_experiments(root,cfg,daily)
        result=export_inputs(root,cfg,daily,X,specs,eligible)
    elif args.stage=='lock':result=lock_experiment(root,cfg)
    elif args.stage=='predict':result=predict_blind(root,require_operational=args.require_operational)
    elif args.stage=='score':
        scores,pairs=evaluate_predictions(root);result={'scored_rows':len(scores),'paired_contrasts':len(pairs)}
    else:result=verify_receipts(root)
    print(json.dumps(result,indent=2))
