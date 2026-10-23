"""Notebook-facing orchestration, real execution evidence and submission packaging."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,zipfile,shutil,sys,importlib.metadata
import numpy as np
import pandas as pd
from common import write_json,load_config,sha256,selected_raw_run,paired_block_ci

NOTEBOOKS=['01_fetch_data.ipynb','02_prepare_data.ipynb','03_analyse.ipynb','04_model.ipynb']


def load_prepared(root,cfg):
    metadata=json.loads((root/'data/processed/dataset_metadata.json').read_text())
    folder,manifest=selected_raw_run(root)
    path=root/'data/processed/final_dataset_daily.csv'
    if metadata['dataset_sha256']!=sha256(path) or metadata['config_sha256']!=sha256(root/'config.json') or metadata['raw_run_id']!=manifest['run_id']:
        raise ValueError('Prepared data/configuration/raw snapshot changed; rerun preparation.')
    names=['date','target_date','issue_date','fire_source_day_utc','forecast_origin_utc','target_complete_utc']
    return pd.read_csv(path,parse_dates=names,float_precision='round_trip')


def begin_run(root,cfg,mode):
    state={'status':'running','mode':mode,'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'config_sha256':sha256(root/'config.json'),'sources':{p.name:sha256(p) for p in sorted((root/'src').glob('*.py'))}}
    write_json(root/'outputs/results/run_state.json',state)
    return state


def acquire_all(root,cfg,mode='replay',key=None):
    from fetch_data import fetch
    from station_crosscheck import station_crosscheck
    if mode!='replay':raise ValueError('This study replays preserved actual ADS/weather responses. New acquisition uses tools/acquire_ads.py and a new snapshot.')
    folder,manifest=fetch(root,cfg,mode='replay')
    cross=station_crosscheck(root,mode='replay')
    from check_dataset import check_raw,require_pass
    require_pass(check_raw(root,cfg))
    return folder,manifest,cross


def verify_science(root,cfg,daily,X,specs,eligible):
    write_json(root/'outputs/results/validation.json',{'status':'RUNNING','scope':'Current run is being verified.'})
    from check_dataset import check_dataset,require_pass
    require_pass(check_dataset(root,cfg,daily,X,specs,eligible))
    from evaluate_forecast import verify_saved_results
    result=verify_saved_results(root,cfg)
    tests=['Exact twelve source/window contracts, source-specific days and full calendar lags.','No target/predictor imputation; zero GFAS values remain native analysis values.']
    from prepare_data import PM,WEATHER,FIRE
    altered=daily.copy();cut=len(daily)//2
    altered.loc[cut:,list(PM|WEATHER|FIRE)]=99999.
    for column in X:
        base,lag=column.rsplit('_lag',1)
        changed=altered.set_index('date')[base].shift(int(lag))
        np.testing.assert_allclose(X[column].iloc[:cut],changed.iloc[:cut],equal_nan=True)
    tests.append('Future value changes cannot affect earlier predictors.')
    from model import partition_rows
    rows=partition_rows(daily,eligible,cfg)
    pred=pd.read_csv(root/'outputs/results/predictions_test.csv')
    if len(pred)!=len(rows['test']) or pred.target_date.duplicated().any():raise ValueError('Test date identity/count mismatch.')
    from availability import validate_operational_inputs
    frozen=json.loads((root/'outputs/results/forecast_lock.json').read_text())
    features=pd.read_csv(root/frozen['feature_file'])
    try:validate_operational_inputs(root,frozen,features)
    except ValueError as error:
        if not str(error).startswith('Operational prediction blocked:'):raise
    else:raise ValueError('Unverified original publication must block operational prediction.')
    tests.append('Operational guard rejects nominal-only publication evidence.')
    dates=pd.date_range('2023-12-15',periods=100);delta=np.sin(np.arange(100)/7)+np.linspace(0,2,100)
    a=paired_block_ci(delta,dates.as_unit('us'),14,1000);b=paired_block_ci(delta,dates.as_unit('ns'),14,1000)
    if a!=b or not a['ci_low']<a['estimate']<a['ci_high']:raise ValueError('Calendar bootstrap invariant failed.')
    tests.append('Calendar bootstrap respects gaps/year boundaries and datetime resolution.')
    for path in (root/'src').glob('*.py'):ast.parse(path.read_text(encoding='utf-8'))
    from environment_check import check_environment
    check_environment(root,strict=True)
    sources={p.name:sha256(p) for p in sorted((root/'src').glob('*.py'))}
    final={'status':'PASS','tests':tests,'eligible_days':int(eligible.sum()),'test_days':len(pred),
        'independent_score_rows':result['independently_recomputed_metric_rows'],'source_sha256':sources,
        'scope':'Technical/scientific chronology checks for a qualified retrospective benchmark; original availability, station accuracy and external submission not certified.'}
    write_json(root/'outputs/results/validation.json',final)
    return final


def notebook_evidence(path):
    import nbformat,tokenize,io
    book=nbformat.read(path,as_version=4);nbformat.validate(book)
    code=[c for c in book.cells if c.cell_type=='code']
    errors=[o for c in code for o in c.outputs if o.output_type=='error']
    if errors:raise ValueError('The notebook contains an execution error.')
    uncommented=[]
    for number,cell in enumerate(book.cells,1):
        if cell.cell_type!='code':continue
        lines=cell.source.splitlines()
        comments={token.start[0] for token in tokenize.generate_tokens(io.StringIO(cell.source).readline) if token.type==tokenize.COMMENT}
        for row,line in enumerate(lines,1):
            if line.strip() and not line.lstrip().startswith('#') and row not in comments:uncommented.append([number,row])
    if uncommented:raise ValueError('Missing per-line notebook explanations: '+str(uncommented))
    return {'code_cells':len(code),'executed_code_cells':sum(c.execution_count is not None for c in code),'stored_errors':len(errors),
        'every_code_line_commented':True,'fully_executed':all(c.execution_count is not None for c in code)}


def verify_report_dependencies(root):
    """Recheck the saved report against its actual inputs and notebook source cells."""
    report_proof=json.loads((root/'report/report_provenance.json').read_text())
    for name,digest in report_proof['inputs_and_outputs'].items():
        if sha256(root/name)!=digest:raise ValueError('Report dependency/output changed: '+name+'; regenerate the report.')
    for name,digest in report_proof.get('notebook_source_hashes',{}).items():
        book=json.loads((root/name).read_text(encoding='utf-8'))
        text=json.dumps([{'cell_type':c['cell_type'],'source':c['source']} for c in book['cells']],ensure_ascii=False,sort_keys=True)
        if hashlib.sha256(text.encode('utf-8')).hexdigest()!=digest:raise ValueError('Notebook source changed after report generation: '+name)
    return report_proof


def make_submission(root,require_executed=False):
    root=Path(root);cfg=json.loads((root/'config.json').read_text())
    from check_dataset import check_raw,check_dataset,require_pass
    from evaluate_forecast import verify_saved_results
    from reference_store import verify_reference_store
    require_pass(check_raw(root,cfg));require_pass(check_dataset(root,cfg))
    fresh=verify_saved_results(root,cfg);reference=verify_reference_store(root)
    verify_report_dependencies(root)
    validation=json.loads((root/'outputs/results/validation.json').read_text())
    current={p.name:sha256(p) for p in sorted((root/'src').glob('*.py'))}
    if validation['status']!='PASS' or validation['source_sha256']!=current:raise ValueError('Scientific validation/source hash is stale.')
    books=[dict(notebook=name,**notebook_evidence(root/name)) for name in NOTEBOOKS]
    evidence={'notebooks':books,'notebook_count':4,'code_cells':sum(b['code_cells'] for b in books),
        'executed_code_cells':sum(b['executed_code_cells'] for b in books),'stored_errors':sum(b['stored_errors'] for b in books),
        'every_code_line_commented':all(b['every_code_line_commented'] for b in books),
        'fully_executed':all(b['fully_executed'] for b in books)}
    if require_executed and not evidence['fully_executed']:raise ValueError('Actual saved execution is required for all four notebooks.')
    from pypdf import PdfReader
    if len(PdfReader(root/'report/proposal.pdf').pages)!=1:raise ValueError('One-page proposal required.')
    write_json(root/'outputs/results/seal_verification.json',{**fresh,'reference':reference,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'report_dependencies_verified':True,'operational_gate':'NOT_PASSED','scope':'Technically reproducible retrospective package; not a declaration of full lab readiness.'})
    write_json(root/'outputs/results/execution_evidence.json',evidence)
    state=json.loads((root/'outputs/results/run_state.json').read_text())
    state.update(status='complete' if evidence['fully_executed'] else 'awaiting_saved_notebook_outputs',finished_at_utc=datetime.now(timezone.utc).isoformat())
    write_json(root/'outputs/results/run_state.json',state)
    paths=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(part in ['.git','__pycache__','.ipynb_checkpoints','.test_work'] for part in path.parts):continue
        if path.name=='submission_manifest.json' or path.suffix in ['.zip','.pyc'] or path.name.startswith('.env'):continue
        paths.append({'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':sha256(path)})
    manifest={'files':paths,'notebook_evidence':evidence,'all_four_executed_notebooks_included':evidence['fully_executed'],
        'external_submission_complete':False,'operational_availability_proven':False,'full_lab_ready_certified':False,
        'scientific_scope':cfg['source_availability_scope']}
    write_json(root/'submission_manifest.json',manifest)
    destination=root.parent/(root.name+'.zip')
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
        for entry in paths:archive.write(root/entry['path'],root.name+'/'+entry['path'])
        archive.write(root/'submission_manifest.json',root.name+'/submission_manifest.json')
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:raise ValueError('Final ZIP CRC failed.')
        for entry in paths:
            if hashlib.sha256(archive.read(root.name+'/'+entry['path'])).hexdigest()!=entry['sha256']:raise ValueError('Final ZIP payload mismatch.')
    return destination,evidence
