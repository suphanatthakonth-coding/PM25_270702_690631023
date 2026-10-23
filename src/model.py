"""Twelve prespecified source/window settings; selection is chronological and training-only."""
import json
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit,GridSearchCV
from common import load_config,write_json,paired_block_ci,sha256
import joblib
from prepare_data import build_experiments


def metric_values(y,prediction,threshold=37.5):
    y=np.asarray(y,dtype=float);prediction=np.asarray(prediction,dtype=float)
    truth=y>threshold;warning=prediction>threshold
    tp=int((truth&warning).sum());tn=int((~truth&~warning).sum())
    fp=int((~truth&warning).sum());fn=int((truth&~warning).sum())
    return {'n':len(y),'MAE':float(np.abs(y-prediction).mean()),'RMSE':float(np.sqrt(np.mean((y-prediction)**2))),
        'TP':tp,'TN':tn,'FP':fp,'FN':fn,'positive_days':int(truth.sum()),'threshold':threshold,
        'precision':tp/(tp+fp) if tp+fp else np.nan,'recall':tp/(tp+fn) if tp+fn else np.nan,
        'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else np.nan}


def calendar_cv(daily,eligible,train_rows,cfg):
    calendar_rows=np.flatnonzero(daily.target_date.between(pd.Timestamp(cfg['start_date']),pd.Timestamp(cfg['train_target_end'])).to_numpy())
    positions=pd.Series(np.arange(len(train_rows)),index=train_rows)
    splits=[];records=[]
    for number,(tr,va) in enumerate(TimeSeriesSplit(n_splits=cfg['inner_splits'],gap=cfg['cv_gap_calendar_days']).split(calendar_rows),1):
        a,b=calendar_rows[tr],calendar_rows[va]
        a=a[eligible.iloc[a].to_numpy()];b=b[eligible.iloc[b].to_numpy()]
        if min(len(a),len(b))<30:raise ValueError('Too few complete rows in a chronological CV fold.')
        origin=pd.Timestamp(daily.forecast_origin_utc.iloc[b[0]])
        mature=pd.to_datetime(daily.target_complete_utc.iloc[a],utc=True).le(origin).to_numpy()
        a=a[mature]
        if len(a)<30 or not set(a)<=set(train_rows):raise ValueError('Invalid training-only fold rows.')
        if daily.target_date.iloc[a].max()>=daily.target_date.iloc[b].min():raise ValueError('CV chronology failed.')
        splits.append((positions.loc[a].to_numpy(),positions.loc[b].to_numpy()))
        records.append({'fold':number,'train_rows':len(a),'validation_rows':len(b),
            'last_train_target':str(daily.target_date.iloc[a].max()),'first_validation_target':str(daily.target_date.iloc[b].min()),
            'last_train_label_complete_utc':str(pd.to_datetime(daily.target_complete_utc.iloc[a],utc=True).max()),
            'first_validation_issue_utc':str(origin),'gap_calendar_days':cfg['cv_gap_calendar_days'],
            'label_maturity_pass':True,'publication_check':'Nominal source-clock benchmark; original publication remains unverified.'})
    return splits,records


def estimator_grid(family,cfg):
    if family=='ridge':
        estimator=Pipeline([('scale',StandardScaler()),('model',Ridge())])
        grid={'model__alpha':[.1,1.,10.,100.,1000.]}
    elif family=='hgb':
        estimator=Pipeline([('model',HistGradientBoostingRegressor(max_iter=200,learning_rate=.05,
            min_samples_leaf=20,random_state=cfg['seed']))])
        grid={'model__max_leaf_nodes':[7,15],'model__l2_regularization':[0.,10.]}
    else:raise ValueError('Unknown estimator family.')
    return estimator,grid


def negative_clipped_mae(estimator,values,target):
    prediction=np.maximum(0,estimator.predict(values))
    return -float(np.mean(np.abs(np.asarray(target)-prediction)))



def fit_training_and_validation(root,cfg):
    """Fit only the exported training/validation tables. No test-target file is opened."""
    inputs=root/'data/processed/evaluation_inputs'
    train=pd.read_csv(inputs/'train.csv',float_precision='round_trip')
    validation=pd.read_csv(inputs/'validation.csv',float_precision='round_trip')
    specs=json.loads((root/'outputs/results/experiment_specs.json').read_text())
    folds=[(np.asarray(item['train'],dtype=int),np.asarray(item['validation'],dtype=int))
        for item in json.loads((inputs/'cv_indices.json').read_text())]
    y=train.y_true;yv=validation.y_true
    if len(train)<30 or len(validation)<30:raise ValueError('Insufficient train/validation observations.')
    if pd.to_datetime(train.target_date).max()>pd.Timestamp(cfg['train_target_end']):raise ValueError('Training dates cross the declared boundary.')
    if pd.to_datetime(validation.target_date).max()>pd.Timestamp(cfg['validation_target_end']):raise ValueError('Validation dates cross into test.')
    tables=validation[['date','target_date','y_true']].copy()
    tables['B0_persistence']=validation.B0_persistence
    tables['B1_provider_forecast']=validation.B1_provider_forecast
    majority_validation=bool(y.gt(cfg['warning_threshold']).mean()>.5)
    combined=pd.concat([train,validation],ignore_index=True)
    majority_test=bool(combined.y_true.gt(cfg['warning_threshold']).mean()>.5)
    tables['C0_training_majority']=float(cfg['warning_threshold']+1 if majority_validation else 0)
    scores=[{'partition':'validation','family':'baseline','experiment':'B0_persistence','hypothesis':'baseline','window':1,
        **metric_values(yv,tables.B0_persistence,cfg['warning_threshold'])}]
    scores.append({'partition':'validation','family':'baseline','experiment':'B1_provider_forecast','hypothesis':'provider_reference','window':0,**metric_values(yv,tables.B1_provider_forecast,cfg['warning_threshold'])})
    warning=metric_values(yv,tables.C0_training_majority,cfg['warning_threshold'])
    scores.append({'partition':'validation','family':'baseline','experiment':'C0_training_majority','hypothesis':'warning_only','window':0,
        **{key:value for key,value in warning.items() if key not in ['MAE','RMSE']}})
    tuning=[];models=[];folder=root/'outputs/results/fitted_models';folder.mkdir(exist_ok=True)
    for family in cfg['model_families']:
        for spec in specs:
            columns=spec['features'];estimator,grid=estimator_grid(family,cfg)
            search=GridSearchCV(estimator,grid,scoring=negative_clipped_mae,cv=folds,n_jobs=1,error_score='raise')
            search.fit(train[columns],y)
            prediction=np.maximum(0,search.best_estimator_.predict(validation[columns]))
            final=clone(search.best_estimator_).fit(combined[columns],combined.y_true)
            name=family+'__'+spec['id'];path=folder/(name+'.joblib')
            joblib.dump(final,path)
            models.append({'column':name,'family':family,'experiment':spec['id'],'hypothesis':spec['hypothesis'],
                'window':spec['window'],'features':columns,'path':path.relative_to(root).as_posix()})
            tables[name]=prediction
            scores.append({'partition':'validation','family':family,'experiment':spec['id'],'hypothesis':spec['hypothesis'],'window':spec['window'],
                **metric_values(yv,prediction,cfg['warning_threshold'])})
            tuning.append({'family':family,'experiment':spec['id'],'parameters':search.best_params_,'inner_cv_MAE':float(-search.best_score_),
                'train_rows':len(train),'refit_rows':len(combined),'feature_count':len(columns),'validation_MAE':float(np.abs(yv-prediction).mean())})
            print(f'{name}: training-only tuning and validation finished; refit saved without test labels',flush=True)
    tables.to_csv(root/'outputs/results/predictions_validation.csv',index=False)
    scores=pd.DataFrame(scores);scores.to_csv(root/'outputs/results/validation_scores.csv',index=False)
    write_json(root/'outputs/results/tuning.json',tuning)
    chosen=scores[scores.family.eq(cfg['primary_family'])].sort_values(['MAE','window','experiment']).iloc[0]
    selection={'primary_family':cfg['primary_family'],'experiment':chosen.experiment,'selection_partition':'validation only',
        'selection_metric':'MAE','validation_MAE':chosen.MAE,'test_was_not_used_for_selection':True,
        'data_status':'Previously explored historical test; prediction-stage isolation does not restore an unseen holdout.'}
    write_json(root/'outputs/results/selection.json',selection)
    return models,majority_test,selection


def summarize_results(root,cfg,scores,tables):
    comparisons=[];test=tables['test']
    for family in cfg['model_families']:
        for window in cfg['windows']:
            pairs=[('H1','B0'),('H2','H1'),('H3','H1'),('H4','H2'),('H4','H3')]
            for new,old in pairs:
                new_name=f'{family}__{new}_{window}d';old_name='B0_persistence' if old=='B0' else f'{family}__{old}_{window}d'
                delta=np.abs(test[new_name]-test.y_true)-np.abs(test[old_name]-test.y_true)
                ci=paired_block_ci(delta,pd.to_datetime(test.target_date),cfg['block_days'],cfg['bootstrap_repeats'],cfg['seed'])
                status='interval_below_zero' if ci['ci_high']<0 else 'interval_above_zero' if ci['ci_low']>0 else 'inconclusive'
                comparisons.append({'family':family,'window':window,'comparison':new+'-'+old,'new':new_name,'reference':old_name,
                    'interpretation':status,'role':'exploratory pointwise interval; not multiplicity-adjusted confirmation',**ci})
    paired=pd.DataFrame(comparisons)
    paired.to_csv(root/'outputs/results/paired_comparisons.csv',index=False)
    answers=[];window_choices=[]
    for family in cfg['model_families']:
        for group in ['H1','H2','H3','H4']:
            group_validation=scores[scores.partition.eq('validation')&scores.family.eq(family)&scores.hypothesis.eq(group)]
            preferred=group_validation.sort_values(['MAE','window']).iloc[0]
            window_choices.append({'family':family,'hypothesis':group,'selected_window':int(preferred.window),'validation_MAE':preferred.MAE,'selection_partition':'validation only'})
            for window in cfg['windows']:
                comparisons_for_group={'H1':['H1-B0'],'H2':['H2-H1'],'H3':['H3-H1'],'H4':['H4-H2','H4-H3']}[group]
                messages=[]
                for label in comparisons_for_group:
                    item=paired[paired.family.eq(family)&paired.window.eq(window)&paired.comparison.eq(label)].iloc[0]
                    message={'interval_below_zero':'lower MAE with pointwise exploratory interval below zero',
                        'interval_above_zero':'higher MAE with pointwise exploratory interval above zero','inconclusive':'no clear MAE difference; interval spans zero'}[item.interpretation]
                    messages.append(f'{label}: {message}; delta={item.estimate:.4f}, 95% CI [{item.ci_low:.4f}, {item.ci_high:.4f}]')
                item=scores[scores.partition.eq('test')&scores.family.eq(family)&scores.experiment.eq(f'{group}_{window}d')].iloc[0]
                answers.append({'family':family,'experiment':f'{group}_{window}d','subhypothesis':group+{3:'a',5:'b',7:'c'}[window],
                    'MAE':item.MAE,'recall':item.recall,'FP':int(item.FP),'FN':int(item.FN),'answer':' | '.join(messages),
                    'scope':'Retrospective CAMS outcome; source-publication and independent-confirmation limits remain.'})
    pd.DataFrame(answers).to_csv(root/'outputs/results/twelve_answers.csv',index=False)
    pd.DataFrame(window_choices).to_csv(root/'outputs/results/window_selection_by_group.csv',index=False)
    # Record the remaining publication/representativeness limits without certifying an operational forecast.
    availability={'H1_source_publication':'UNVERIFIED','H2_source_publication':'UNVERIFIED','H3_source_publication':'UNVERIFIED','H4_source_publication':'UNVERIFIED',
        'operational_status':'NOT_EVALUATED_AVAILABILITY_UNVERIFIED','target':'CAMS model output; not measured station outcome',
        'test_scope':'Repeated one-step retrospective predictions with realized valid-time histories, not a multi-month forecast issued once.',
        'quality_scope':'A shared quality-screened seven-day cohort is used for all twelve settings; missingness may change representativeness.'}
    write_json(root/'outputs/results/availability_gate.json',availability)
    return scores,paired

if __name__=='__main__':
    from stages import run_model_stage
    root,cfg=load_config()
    print(run_model_stage(root,cfg))


def partition_rows(daily,eligible,cfg):
    dates=pd.to_datetime(daily.target_date)
    base=eligible.to_numpy(dtype=bool)
    masks={'train':base&dates.le(pd.Timestamp(cfg['train_target_end'])).to_numpy(),
        'validation':base&dates.ge(pd.Timestamp(cfg['validation_target_start'])).to_numpy()&dates.le(pd.Timestamp(cfg['validation_target_end'])).to_numpy(),
        'test':base&dates.ge(pd.Timestamp(cfg['test_target_start'])).to_numpy()&dates.le(pd.Timestamp(cfg['end_date'])).to_numpy()}
    rows={name:np.flatnonzero(mask) for name,mask in masks.items()}
    if any(len(r)<30 for r in rows.values()):raise ValueError('Insufficient common rows in a required partition.')
    if sum(len(r) for r in rows.values())!=int(eligible.sum()):raise ValueError('Unassigned/duplicate eligible partition rows.')
    for previous,next_name in [('train','validation'),('validation','test')]:
        cutoff=pd.Timestamp(daily.forecast_origin_utc.iloc[rows[next_name][0]])
        mature=pd.to_datetime(daily.target_complete_utc.iloc[rows[previous]],utc=True)
        if not mature.le(cutoff).all():raise ValueError('Outer labels unavailable at first '+next_name+' issue.')
    return rows
