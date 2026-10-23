"""Declared secondary diagnostics; never reselect models, masks or block length on test scores."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from common import write_json,paired_block_ci
from analyse import savefig


def preparation_diagnostics(root,cfg,daily,X,eligible):
    work=daily[['date','target_date','pm25_tomorrow','in_study_target_calendar','source_advisory_dependency','outer_label_purge']].copy()
    work['eligible_common']=eligible.to_numpy();work['target_present']=work.pm25_tomorrow.notna()
    work=work[work.in_study_target_calendar].copy()
    work['target_exceedance']=work.pm25_tomorrow.gt(cfg['warning_threshold'])&work.target_present
    work['retained_exceedance']=work.target_exceedance&work.eligible_common
    work['target_month']=work.target_date.dt.to_period('M').astype(str)
    monthly=work.groupby('target_month').agg(calendar_origins=('date','size'),available_targets=('target_present','sum'),
        retained_targets=('eligible_common','sum'),available_exceedances=('target_exceedance','sum'),retained_exceedances=('retained_exceedance','sum'))
    monthly['retention_percent']=100*monthly.retained_targets/monthly.calendar_origins
    monthly.to_csv(root/'outputs/results/coverage_by_month.csv')
    yearly=work.groupby(work.target_date.dt.year).agg(available_targets=('target_present','sum'),common_targets=('eligible_common','sum'),
        available_exceedances=('target_exceedance','sum'),common_exceedances=('retained_exceedance','sum'))
    yearly.index.name='target_year';yearly.to_csv(root/'outputs/results/cohort_representativeness.csv')
    fig,axes=plt.subplots(1,2,figsize=(10,3.5));axes[0].bar(yearly.index.astype(str),yearly.available_exceedances,color='#b9c3cc',label='All available targets')
    axes[0].bar(yearly.index.astype(str),yearly.common_exceedances,color='#477da1',label='Retained common targets')
    axes[0].set(xlabel='Target year',ylabel='Modeled exceedance days',title='Coverage before/after declared quality rules');axes[0].legend(fontsize=8)
    axes[1].plot(range(len(monthly)),monthly.retention_percent,marker='.',lw=.8)
    ticks=np.arange(0,len(monthly),3);axes[1].set(xticks=ticks,xticklabels=monthly.index[ticks],xlabel='Target month',ylabel='Common-day retention (%)',ylim=(0,105),title='Missing history, advisory and maturity purges')
    axes[1].tick_params(axis='x',rotation=35)
    savefig(root,fig,'06_matched_period_coverage','Full study target calendar vs common eligible dates. Forecast skill is conditional on retained dates; two outer maturity-purge days are not imputed.')
    flag=work.target_exceedance
    groups=flag.ne(flag.shift(fill_value=False)).cumsum()
    episodes=[]
    for _,part in work.loc[flag].groupby(groups[flag]):
        episodes.append({'first_local_day':str(part.target_date.min().date()),'last_local_day':str(part.target_date.max().date()),'days':len(part),
            'mean_pm25':part.pm25_tomorrow.mean(),'maximum_pm25':part.pm25_tomorrow.max(),'kind':'CAMS modeled exceedance episode, not measured station violations'})
    pd.DataFrame(episodes,columns=['first_local_day','last_local_day','days','mean_pm25','maximum_pm25','kind']).to_csv(root/'outputs/results/exceedance_episodes.csv',index=False)
    values=X.notna().all(axis=1).to_numpy()&daily.pm25_tomorrow.notna().to_numpy()&daily.provider_forecast.notna().to_numpy()&daily.in_study_target_calendar.to_numpy()
    policy=pd.DataFrame([{'policy':'value_complete_before_advisory_and_outer_purges','common_history_rows':int(values.sum()),'used_for_primary_model':False},
        {'policy':'after_conservative_advisory_before_outer_purges','common_history_rows':int((values&~daily.source_advisory_dependency.to_numpy()).sum()),'used_for_primary_model':False},
        {'policy':'primary_with_advisory_and_label_maturity_purges','common_history_rows':int(eligible.sum()),'used_for_primary_model':True}])
    policy['scope']='Coverage sensitivity only; no model selection or known-local-contamination assertion.'
    policy.to_csv(root/'outputs/results/fire_policy_sensitivity.csv',index=False)
    summary={'calendar_days':len(work),'history_calendar_rows':len(daily),'common_days':int(eligible.sum()),'retention_percent':100*int(eligible.sum())/len(work),
        'longest_exceedance_episode_days':max([r['days'] for r in episodes],default=0),
        'value_complete_before_quality_purges':int(values.sum()),'source_advisory_excluded_rows':int((values&daily.source_advisory_dependency.to_numpy()).sum()),
        'outer_maturity_purge_rows':int((values&~daily.source_advisory_dependency.to_numpy()&daily.outer_label_purge.to_numpy()).sum()),
        'interpretation':'Shared source-clock retrospective cohort. Native values complete does not certify actual historical publication.'}
    write_json(root/'outputs/results/coverage_summary.json',summary)
    return summary


def model_diagnostics(root,cfg):
    test=pd.read_csv(root/'outputs/results/predictions_test.csv',parse_dates=['date','target_date'],float_precision='round_trip')
    paired=pd.read_csv(root/'outputs/results/paired_comparisons.csv',float_precision='round_trip')
    rows=[]
    for item in paired.itertuples():
        delta=np.abs(test[item.new]-test.y_true)-np.abs(test[item.reference]-test.y_true)
        for block in cfg['bootstrap_sensitivity_days']:
            ci=paired_block_ci(delta,test.target_date,block,cfg['bootstrap_repeats'],cfg['seed'])
            status='interval_below_zero' if ci['ci_high']<0 else 'interval_above_zero' if ci['ci_low']>0 else 'inconclusive'
            rows.append({'family':item.family,'window':item.window,'comparison':item.comparison,'interpretation':status,
                'is_primary_block':block==cfg['block_days'],'scope':'Secondary sensitivity, not a basis for changing primary block or model',**ci})
    sensitivity=pd.DataFrame(rows);sensitivity.to_csv(root/'outputs/results/bootstrap_sensitivity.csv',index=False)
    primary=sensitivity[sensitivity.family.eq(cfg['primary_family'])]
    changes=int(primary.groupby(['window','comparison']).interpretation.nunique().gt(1).sum())
    selection=json.loads((root/'outputs/results/selection.json').read_text());name=cfg['primary_family']+'__'+selection['experiment']
    details=test[['date','target_date','y_true','B0_persistence',name]].copy()
    truth=details.y_true.gt(cfg['warning_threshold']);warning=details[name].gt(cfg['warning_threshold'])
    baseline=details.B0_persistence.gt(cfg['warning_threshold'])
    details['model_error']=details[name]-details.y_true;details['actual_above_threshold']=details.y_true-cfg['warning_threshold']
    details['model_outcome']=np.select([truth&warning,~truth&~warning,~truth&warning],['TP','TN','FP'],default='FN')
    details['baseline_outcome']=np.select([truth&baseline,~truth&~baseline,~truth&baseline],['TP','TN','FP'],default='FN')
    details.to_csv(root/'outputs/results/warning_day_details.csv',index=False)
    missed=details.loc[details.model_outcome.eq('FN')]
    missed.to_csv(root/'outputs/results/missed_day_details.csv',index=False)
    fig,ax=plt.subplots(figsize=(10,3.3))
    # Markers avoid connecting observations across missing calendar gaps.
    ax.scatter(details.target_date,details.y_true,s=12,label='CAMS target')
    ax.scatter(details.target_date,details[name],s=10,marker='x',label=selection['experiment'])
    ax.scatter(missed.target_date,missed.y_true,s=65,facecolors='none',edgecolors='red',label='Missed exceedance')
    ax.axhline(cfg['warning_threshold'],ls='--',color='gray')
    ax.set(xlabel='Thailand target date (retained test days)',ylabel='PM2.5 (ug/m3)',title='Selected-model errors; calendar gaps are not connected');ax.legend(fontsize=8)
    savefig(root,fig,'07_warning_days','Circled CAMS exceedances were missed by the validation-selected model. Plotting retained-day points avoids implying continuous coverage. This is not a station-validated warning trial.')
    scores=pd.read_csv(root/'outputs/results/model_scores.csv',float_precision='round_trip')
    ridge=scores[scores.partition.eq('test')&scores.family.eq('ridge')]
    hgb=scores[scores.partition.eq('test')&scores.family.eq('hgb')]
    robustness=ridge[['experiment','MAE']].merge(hgb[['experiment','MAE']],on='experiment',suffixes=('_ridge','_hgb'),validate='one_to_one')
    robustness['delta_hgb_minus_ridge']=robustness.MAE_hgb-robustness.MAE_ridge
    robustness.to_csv(root/'outputs/results/learner_robustness.csv',index=False)
    result={'primary_contrasts_changing_classification_across_blocks':changes,'primary_contrast_count':15,
        'primary_block_days':cfg['block_days'],'block_lengths':cfg['bootstrap_sensitivity_days'],
        'segment_lengths':json.loads(str(primary.iloc[0].segment_lengths).replace("'",'"')) if isinstance(primary.iloc[0].segment_lengths,str) else primary.iloc[0].segment_lengths,
        'hgb_lower_MAE_settings':int(robustness.delta_hgb_minus_ridge.lt(0).sum()),'learner_comparisons':len(robustness),
        'selected_FN':len(missed),'missed_target_min':float(missed.y_true.min()) if len(missed) else None,
        'missed_target_max':float(missed.y_true.max()) if len(missed) else None,
        'scope':'Secondary diagnostics only. No selection of hypotheses, learners, blocks, masks or warning cutoffs by test results.'}
    write_json(root/'outputs/results/diagnostic_summary.json',result)
    return result
