"""Project-owned dataset checks. Designed for this lab; no additional instructor script was supplied.

PASS means an observed technical invariant passed; UNVERIFIED does not mean zero risk.
Historical publication availability remains separate from retrospective data validity.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,uuid
import numpy as np
import pandas as pd
from common import load_config,write_json,sha256,selected_raw_run


def data_fingerprints(root):
    paths=[root/'config.json',*sorted((root/'src').glob('*.py'))]
    paths+=sorted((root/'data/processed').glob('*.csv'))
    paths+=sorted((root/'data/processed').glob('*.json'))
    for name in ['selected_run.json','selected_aux_run.json']:
        paths.append(root/'data/raw'/name)
    paths.append(root/'snapshot.json')
    return {p.relative_to(root).as_posix():sha256(p) for p in paths if p.is_file()}


def _finish(root,stage,checks):
    temporal={'full_calendar_including_buffers','tomorrow_after_issue_target','issue_and_target_clock',
        'target_41hour_finish','unknown_targets_never_safe_labels','all_declared_calendar_lags',
        'all_twelve_exact_feature_contracts','fire_source_specific_day','outer_label_maturity_train','outer_label_maturity_validation'}
    observed={c['check']:c['status'] for c in checks}
    temporal_status=('PASS' if temporal.issubset(observed) and all(observed[n]=='PASS' for n in temporal)
        else 'FAIL' if any(observed.get(n)=='FAIL' for n in temporal) else 'NOT_EVALUATED')
    report={'owner':'PROJECT-OWNED DATASET CHECKER','stage':stage,
        'temporal_cutoff_status':temporal_status,
        'temporal_cutoff_scope':'Calendar, target, source offsets and outer label maturity; CV/scaling are checked in the model stage.',
        'checked_at_utc':datetime.now(timezone.utc).isoformat(),'run_id':uuid.uuid4().hex,
        'technical_status':'FAIL' if any(c['status']=='FAIL' for c in checks) else 'PASS',
        'historical_publication_status':'UNVERIFIED','operational_readiness':'NOT_PASSED',
        'checks':checks,'input_fingerprints':data_fingerprints(root)}
    write_json(root/f'outputs/results/{stage}_checks.json',report)
    pd.DataFrame(checks).to_csv(root/f'outputs/results/{stage}_checks.csv',index=False)
    return report


def require_pass(report):
    if report['technical_status']!='PASS':
        raise ValueError('Dataset checks failed: '+', '.join(c['check'] for c in report['checks'] if c['status']=='FAIL'))
    return report


def validate_fetch_script(root,path='src/fetch_data.py'):
    """Validate this study's supported entry point; never execute an arbitrary path."""
    root=Path(root).resolve();candidate=(root/Path(path)).resolve()
    if candidate!=root/'src/fetch_data.py' or candidate.suffix!='.py':
        raise ValueError('Unsupported fetch-script path; this study requires src/fetch_data.py.')
    if not candidate.is_file():raise ValueError('Fetch script does not exist: src/fetch_data.py.')
    import ast
    ast.parse(candidate.read_text(encoding='utf-8'),filename=str(candidate))
    return {'path':'src/fetch_data.py','sha256':sha256(candidate),'syntax':'PASS'}


def experiment_contract_issues(cfg,specs):
    """Independently derive every allowed source/lag set, not just its length."""
    from prepare_data import PM,WEATHER,FIRE
    groups={'H1':{'PM'},'H2':{'PM','weather'},'H3':{'PM','fire'},'H4':{'PM','weather','fire'}}
    bases={'PM':set(PM),'weather':set(WEATHER),'fire':set(FIRE)}
    issues=[]
    if sorted(cfg['windows'])!=[3,5,7]:issues.append('Configured windows must be exactly 3,5,7.')
    if not isinstance(specs,list) or len(specs)!=12:return issues+['Exactly twelve experiment records are required.']
    expected_ids={f'{h}_{k}d' for h in groups for k in [3,5,7]}
    ids=[s.get('id') for s in specs]
    if any(not isinstance(x,str) for x in ids) or set(ids)!=expected_ids or len(set(ids))!=12:
        issues.append('Missing, extra or duplicate experiment IDs.')
    for s in specs:
        h=s.get('hypothesis');k=s.get('window');name=s.get('id','unknown')
        if h not in groups or k not in [3,5,7]:
            issues.append(str(name)+': unsupported hypothesis/window.');continue
        if name!=f'{h}_{k}d':issues.append(str(name)+': ID does not match hypothesis/window.')
        features=s.get('features',[])
        if not isinstance(features,list) or any(not isinstance(x,str) for x in features):
            issues.append(str(name)+': malformed feature list.');continue
        wanted={f'{base}_lag{lag}' for group in groups[h] for base in bases[group] for lag in range(k)}
        if set(features)!=wanted or len(features)!=len(wanted):
            issues.append(str(name)+': source/lag feature set differs (missing, extra or duplicate feature).')
        sources=s.get('sources',[])
        if not isinstance(sources,list) or set(sources)!=groups[h] or len(sources)!=len(groups[h]):
            issues.append(str(name)+': declared source groups differ.')
        if s.get('feature_count')!=len(wanted):issues.append(str(name)+': feature_count differs.')
    return issues


def check_raw(root,cfg):
    """Invalidate any old PASS; persist the current failure before propagating it."""
    run_id=uuid.uuid4().hex
    write_json(root/'outputs/results/raw_checks.json',{'stage':'raw','run_id':run_id,
        'checked_at_utc':datetime.now(timezone.utc).isoformat(),'technical_status':'RUNNING','checks':[]})
    pd.DataFrame(columns=['check','status','evidence']).to_csv(root/'outputs/results/raw_checks.csv',index=False)
    try:
        report=_check_raw(root,cfg)
    except Exception as error:
        report=_finish(root,'raw',[{'check':'raw_validation_exception','status':'FAIL',
            'evidence':type(error).__name__+': '+str(error)}])
        report['run_id']=run_id
        write_json(root/'outputs/results/raw_checks.json',report)
        raise
    report['run_id']=run_id
    write_json(root/'outputs/results/raw_checks.json',report)
    return report


def _check_raw(root,cfg):
    folder,manifest=selected_raw_run(root)
    proof=json.loads((root/'outputs/results/raw_decode_audit.json').read_text())
    checks=[]
    def add(name,ok,evidence):checks.append({'check':name,'status':'PASS' if bool(ok) else 'FAIL','evidence':str(evidence)})
    add('supported_fetch_script',True,validate_fetch_script(root))
    add('selected_raw_hashes',proof['raw_manifest_sha256']==sha256(folder/'manifest.json'),manifest['run_id'])
    add('native_decoder_source_identity',proof['source_sha256']==sha256(root/'src/ads_bulk_acquisition.py'),'Native source identity; raw decoder is part of the experiment lock.')
    add('fifty_actual_request_coverage',proof['requests']==50 and proof['native_messages']==36952,'50 actual transfers;36,952 native fields; no fabricated days.')
    for name,digest in proof['exports'].items():
        add('native_export_'+Path(name).name,sha256(root/name)==digest,name)
    from weather_acquisition import validate_weather
    weather=json.loads((folder/'weather/transfer_manifest.json').read_text())
    for item in weather:
        report=validate_weather(json.loads((folder/'weather'/item['file']).read_bytes()),item['parameters'])
        add('weather_schema_units_calendar_'+item['file'],report['status']=='PASS',str(report['hourly_count'])+' expected UTC hours; source nulls preserved.')
    from source_contract import materialize_source_contract
    materialize_source_contract(root,cfg)
    checks.append({'check':'historical_available_at','status':'UNVERIFIED',
        'evidence':'Source runs/units and nominal release schedules checked. Current transfer receipts do not certify original public releases or absence of revision.'})
    return _finish(root,'raw',checks)


def check_dataset(root,cfg,daily=None,X=None,specs=None,eligible=None):
    run_id=uuid.uuid4().hex
    write_json(root/'outputs/results/dataset_checks.json',{'stage':'dataset','run_id':run_id,
        'checked_at_utc':datetime.now(timezone.utc).isoformat(),'technical_status':'RUNNING','checks':[]})
    pd.DataFrame(columns=['check','status','evidence']).to_csv(root/'outputs/results/dataset_checks.csv',index=False)
    try:
        report=_check_dataset(root,cfg,daily,X,specs,eligible)
    except Exception as error:
        report=_finish(root,'dataset',[{'check':'dataset_validation_exception','status':'FAIL',
            'evidence':type(error).__name__+': '+str(error)}])
        report['run_id']=run_id
        write_json(root/'outputs/results/dataset_checks.json',report)
        (root/'feasibility_report.txt').write_text('PROJECT-OWNED DATASET CHECKER\nVerdict: NOT FEASIBLE\nCurrent validation failed: '+str(error)+'\n',encoding='utf-8')
        raise
    report['run_id']=run_id
    write_json(root/'outputs/results/dataset_checks.json',report)
    return report


def _check_dataset(root,cfg,daily=None,X=None,specs=None,eligible=None):
    from prepare_data import PM,WEATHER,FIRE,build_experiments
    if daily is None:
        from workflow import load_prepared
        daily=load_prepared(root,cfg)
    if X is None:X,specs,eligible=build_experiments(root,cfg,daily)
    checks=[]
    def add(name,ok,evidence):checks.append({'check':name,'status':'PASS' if bool(ok) else 'FAIL','evidence':str(evidence)})
    expected_dates=pd.Series(pd.date_range(cfg['history_calendar_start'],cfg['history_calendar_end']),name='date')
    add('full_calendar_including_buffers',daily.date.equals(expected_dates) and daily.date.is_unique,f'{len(daily)} calendar rows; no compressed-day lagging.')
    target=daily.pm25_mean.shift(-2)
    add('tomorrow_after_issue_target',np.allclose(daily.pm25_tomorrow,target,equal_nan=True),'History anchor =D-1; issue=D07; target=D+1, hence anchor+2.')
    origin=pd.to_datetime(daily.forecast_origin_utc,utc=True)
    expected=pd.DatetimeIndex(daily.date+pd.Timedelta(days=1)).tz_localize(cfg['timezone']).tz_convert('UTC')+pd.Timedelta(hours=7)
    add('issue_and_target_clock',np.array_equal(origin.to_numpy(),expected.to_numpy()) and daily.target_date.equals(daily.date+pd.Timedelta(days=2)),'07 Thai issue; target starts17h and ends41h later.')
    finish=pd.to_datetime(daily.target_complete_utc,utc=True)
    add('target_41hour_finish',np.array_equal((finish-origin).to_numpy(),np.repeat(pd.Timedelta(hours=41).to_timedelta64(),len(daily))),'Label completion distinct from public availability.')
    event=target.gt(cfg['warning_threshold']).astype('Int64');event.loc[target.isna()]=pd.NA
    add('unknown_targets_never_safe_labels',daily.exceed_tomorrow.astype('Int64').equals(event),'Unknown labels retain NA.')
    wanted={f'{name}_lag{lag}' for name in PM|WEATHER|FIRE for lag in range(7)}
    exact=set(X.columns)==wanted
    for column in X:
        name,lag=column.rsplit('_lag',1)
        exact=exact and np.allclose(X[column],daily[name].shift(int(lag)),equal_nan=True)
    add('all_declared_calendar_lags',exact,f'{len(X.columns)} exact columns; metadata and provider reference are excluded from learned features.')
    issues=experiment_contract_issues(cfg,specs)
    add('all_twelve_exact_feature_contracts',not issues,issues or 'Every source/lag set independently reconstructed.')
    expected=X.notna().all(axis=1)&daily.pm25_tomorrow.notna().to_numpy()&daily.provider_forecast.notna().to_numpy()
    expected=expected.to_numpy()&daily.in_study_target_calendar.to_numpy()&~daily.source_advisory_dependency.to_numpy()&~daily.outer_label_purge.to_numpy()
    add('shared_cohort_exact',np.array_equal(eligible.to_numpy(),expected),'Same max-window source/date eligibility for all12settings.')
    inclusion=pd.read_csv(root/'outputs/results/row_inclusion.csv')
    add('row_ledger_retention_matches_eligibility',np.array_equal(inclusion.first_failure.eq('retained_common').to_numpy(),eligible.to_numpy()),'No excluded row may be labelled retained, including missing provider references.')
    add('minimum_500_common_days',eligible.sum()>=500,int(eligible.sum()))
    add('fire_source_specific_day',daily.fire_source_day_utc.equals(daily.date-pd.Timedelta(days=1)),'Latest GFAS day at issue D07 is nominal UTC D-2, not D-1.')
    add('fire_log_and_native_fraction',np.allclose(daily.log_fire_power_mw,np.log1p(daily.fire_power_mw),equal_nan=True) and daily.fire_positive_area_fraction.dropna().between(0,1).all(),'Area-weighted density integration; no hotspot-count substitution.')
    numeric=daily.select_dtypes(include='number')
    add('finite_or_explicit_missing',not np.isinf(numeric.to_numpy(dtype=float,na_value=np.nan)).any() and not np.isinf(X.to_numpy(dtype=float)).any(),'NaN is missing, never infinity or false zero.')
    missing=pd.read_csv(root/'outputs/results/missingness.csv').set_index('column').reindex(daily.columns)
    add('all_column_missing_accounting',np.array_equal(missing.missing_rows,daily.isna().sum()) and missing.total_rows.eq(len(daily)).all() and np.allclose(missing.missing_percent,daily.isna().mean()*100),'Every column has numerator/denominator, including zero-missing columns.')
    from model import partition_rows
    partitions=partition_rows(daily,eligible,cfg)
    for previous,next_partition in [('train','validation'),('validation','test')]:
        a,b=partitions[previous],partitions[next_partition]
        cutoff=pd.to_datetime(daily.forecast_origin_utc.iloc[b[0]],utc=True)
        add('outer_label_maturity_'+previous,finish.iloc[a].le(cutoff).all(),f'{previous} labels complete before first{next_partition} issue.')
    records=[]
    for row in pd.read_csv(root/'outputs/results/feature_manifest.csv').itertuples():
        records.append({'feature':row.feature,'source_group':row.source_group,'availability_status':'UNVERIFIED',
            'nominal_schedule_admissible':True,'documented_latency_conflict':False,'operational_use_allowed':False,
            'valid_date_rule':row.time_rule,'historical_available_at':None,
            'evidence_context':'Actual native forecast/analysis identity plus documented nominal source clock; per-origin actual publication and archive revisions not certified.'})
    records.append({'feature':'B1_provider_forecast','source_group':'PM_provider_reference','availability_status':'UNVERIFIED',
        'nominal_schedule_admissible':True,'documented_latency_conflict':False,'operational_use_allowed':False,
        'valid_date_rule':'For issue D07 use run D-1 at12UTC, leads29..52; nominal release D-1 at22UTC.',
        'historical_available_at':None,'evidence_context':'Nominal2h pre-issue margin; actual ADS delays remain possible.'})
    pd.DataFrame(records).to_csv(root/'outputs/results/feature_availability.csv',index=False)
    checks.append({'check':'historical_publication_and_revision','status':'UNVERIFIED','evidence':'Exact historical public-release/revision audit is unverified; temporal-cutoff checks are reported separately. Operational use remains blocked.'})
    report=_finish(root,'dataset',checks)
    lines=['PROJECT-OWNED DATASET CHECKER','Verdict: FEASIBLE WITH ISSUES' if report['technical_status']=='PASS' else 'Verdict: NOT FEASIBLE',
        'Scope: qualified retrospective benchmark only; not an operational-availability PASS.',
        f'Technical status: {report["technical_status"]}',f'Temporal cutoff status: {report["temporal_cutoff_status"]}',f'Common daily rows: {int(eligible.sum())}',
        'Original historical public release/revision not certified; operational mode blocked.',
        *[f'{c["status"]}: {c["check"]}: {c["evidence"]}' for c in checks]]
    (root/'feasibility_report.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    root,cfg=load_config()
    class CurrentAttemptParser(argparse.ArgumentParser):
        def error(self,message):raise ValueError(message)
    parser=CurrentAttemptParser(description=__doc__)
    parser.add_argument('data',nargs='?');parser.add_argument('--stage',choices=['raw','dataset'],default='dataset')
    parser.add_argument('--target',default='pm25_tomorrow');parser.add_argument('--time',default='date');parser.add_argument('--fetch-script',default='src/fetch_data.py')
    stage='dataset';attempt={'status':'RUNNING','run_id':uuid.uuid4().hex,
        'started_at_utc':datetime.now(timezone.utc).isoformat()}
    write_json(root/'outputs/results/checker_cli_attempt.json',attempt)
    try:
        args=parser.parse_args(argv);stage=args.stage
        if args.data and Path(args.data).resolve()!=(root/'data/processed/final_dataset_daily.csv').resolve():
            raise ValueError('This local checker implements this study contract only.')
        if (args.target,args.time)!=('pm25_tomorrow','date'):raise ValueError('Unsupported target/time contract.')
        fetch=validate_fetch_script(root,args.fetch_script)
        result=check_raw(root,cfg) if stage=='raw' else check_dataset(root,cfg)
        require_pass(result)
        attempt.update(status='PASS',validation_run_id=result['run_id'],fetch_script=fetch)
        print(json.dumps(result,indent=2))
    except Exception as error:
        result=_finish(root,stage,[{'check':'cli_attempt','status':'FAIL','evidence':type(error).__name__+': '+str(error)}])
        (root/'feasibility_report.txt').write_text('PROJECT-OWNED DATASET CHECKER\nVerdict: NOT FEASIBLE\nCurrent CLI validation failed: '+str(error)+'\n',encoding='utf-8')
        attempt.update(status='FAIL',validation_run_id=result['run_id'],reason=str(error))
        raise
    except SystemExit as error:
        attempt.update(status='HELP_NO_VALIDATION' if error.code==0 else 'FAIL',reason='Argument parser exit.')
        raise
    finally:
        attempt['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        write_json(root/'outputs/results/checker_cli_attempt.json',attempt)
    return result


if __name__=='__main__':main()
