"""A project-owned SQLite audit store built from real, preserved study records.

This store is an inspection artifact, never an extra predictor or an independent
ground-truth source. Historical CAMS answers remain model output, not station truth.
"""
import json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
import pandas as pd
from common import sha256,write_json

TABLES=[('train.csv','training','training labels and features'),
    ('validation.csv','validation','validation labels and features'),
    ('test_features.csv','test_features','answer-free prediction inputs'),
    ('test_answers.csv','historical_answers','historical CAMS evaluation reference')]


def _current_prediction_identity(root):
    receipt_path=root/'outputs/results/prediction_receipt.json'
    receipt=json.loads(receipt_path.read_text())
    plan_path=root/'outputs/results/forecast_lock.json'
    plan=json.loads(plan_path.read_text())
    if receipt['run_id']!=plan['run_id'] or receipt['locked_plan_sha256']!=sha256(plan_path):
        raise ValueError('Reference receipt does not match current forecast run/plan.')
    if sha256(root/'outputs/results/predictions_test_blind.csv')!=receipt['prediction_sha256']:
        raise ValueError('Prediction receipt changed.')
    return receipt,sha256(receipt_path)


def build_reference_store(root):
    folder=root/'data/processed/evaluation_inputs'
    database=root/'data/processed/reference_store.sqlite'
    temporary=database.with_suffix('.building.sqlite')
    temporary.unlink(missing_ok=True)
    origins=[]
    with closing(sqlite3.connect(temporary)) as connection, connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('CREATE TABLE provenance(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, role TEXT NOT NULL)')
        for filename,table,role in TABLES:
            path=folder/filename
            frame=pd.read_csv(path,float_precision='round_trip')
            if frame[['date','target_date']].duplicated().any():raise ValueError('Duplicate reference-store identity.')
            if table=='test_features' and 'y_true' in frame:raise ValueError('Answers in predictor store.')
            frame.to_sql(table,connection,index=False,if_exists='fail')
            connection.execute('CREATE UNIQUE INDEX '+table+'_date ON '+table+'(date,target_date)')
            connection.execute('INSERT INTO provenance VALUES(?,?,?)',(path.relative_to(root).as_posix(),sha256(path),role))
            origins.append({'table':table,'rows':len(frame),'role':role})
        # Exact SQL identity check: feature and answer keys must match in both directions.
        for left,right in [('test_features','historical_answers'),('historical_answers','test_features')]:
            count=connection.execute('SELECT COUNT(*) FROM (SELECT date,target_date FROM '+left+
                ' EXCEPT SELECT date,target_date FROM '+right+')').fetchone()[0]
            if count:raise ValueError('Feature/answer date mismatch in reference store.')
        if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure.')
    temporary.replace(database)
    result={'status':'PASS','created_at_utc':datetime.now(timezone.utc).isoformat(),'tables':origins,
        'database_sha256':sha256(database),'source_kind':'real archived fixed-run CAMS/GFS forecast/GFAS records',
        'reference_kind':'CAMS modeled target; separate Air4Thai point check is not a historical measured target',
        'scope':'Historical audit store; no fabricated outcomes, independent test or publication proof.'}
    write_json(root/'outputs/results/reference_store.json',result)
    return result


def store_committed_predictions(root):
    """Called after prediction commitment; reads no answer table or answer file."""
    receipt,receipt_hash=_current_prediction_identity(root)
    path=root/'outputs/results/predictions_test_blind.csv'
    if sha256(path)!=receipt['prediction_sha256']:raise ValueError('Prediction receipt changed.')
    frame=pd.read_csv(path,float_precision='round_trip')
    if 'y_true' in frame:raise ValueError('Answer column in committed predictions.')
    if len(frame)!=receipt['rows'] or frame[['date','target_date']].duplicated().any():
        raise ValueError('Prediction row count/identities differ from receipt.')
    database=root/'data/processed/reference_store.sqlite'
    if not database.is_file():raise FileNotFoundError('Build the reference store in stage 02 first.')
    with closing(sqlite3.connect(database)) as connection, connection:
        frame.to_sql('committed_predictions',connection,index=False,if_exists='replace')
        connection.execute('CREATE UNIQUE INDEX committed_predictions_date ON committed_predictions(date,target_date)')
        stored={k:v for k,v in receipt.items() if k!='input_columns'}
        stored['receipt_sha256']=receipt_hash
        pd.DataFrame([stored]).to_sql('prediction_receipt',connection,index=False,if_exists='replace')
    result=json.loads((root/'outputs/results/reference_store.json').read_text())
    result.update(database_sha256=sha256(database),committed_prediction_rows=len(frame),
                  prediction_run_id=receipt['run_id'],prediction_receipt_sha256=receipt_hash,prediction_stage_reads_answers=False)
    write_json(root/'outputs/results/reference_store.json',result)
    return {'status':'PASS','stored_predictions':len(frame),'answer_tables_read':False}


def verify_reference_store(root):
    database=root/'data/processed/reference_store.sqlite'
    evidence=json.loads((root/'outputs/results/reference_store.json').read_text())
    if sha256(database)!=evidence['database_sha256']:raise ValueError('Reference database changed.')
    receipt,receipt_hash=_current_prediction_identity(root)
    if evidence.get('prediction_run_id')!=receipt['run_id'] or evidence.get('prediction_receipt_sha256')!=receipt_hash:
        raise ValueError('Reference store belongs to a different prediction run/receipt.')
    with closing(sqlite3.connect('file:'+database.as_posix()+'?mode=ro',uri=True)) as connection, connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure.')
        provenance=dict(connection.execute('SELECT path,sha256 FROM provenance'))
        expected_paths={(root/'data/processed/evaluation_inputs'/f).relative_to(root).as_posix() for f,_,_ in TABLES}
        if set(provenance)!=expected_paths:raise ValueError('Reference-store provenance tables are incomplete.')
        for path,digest in provenance.items():
            if sha256(root/path)!=digest:raise ValueError('Reference-store source changed: '+path)
        checked=[]
        for filename,table,_ in TABLES:
            saved_table=pd.read_sql_query('SELECT * FROM '+table+' ORDER BY date,target_date',connection)
            source=pd.read_csv(root/'data/processed/evaluation_inputs'/filename,float_precision='round_trip').sort_values(['date','target_date']).reset_index(drop=True)
            pd.testing.assert_frame_equal(saved_table,source,check_exact=True)
            checked.append({'table':table,'rows':len(source),'exact_values':'PASS'})
        stored=pd.read_sql_query('SELECT * FROM prediction_receipt',connection)
        expected={k:v for k,v in receipt.items() if k!='input_columns'};expected['receipt_sha256']=receipt_hash
        if len(stored)!=1 or set(stored.columns)!=set(expected) or any(stored.iloc[0][k]!=v for k,v in expected.items()):
            raise ValueError('SQLite prediction receipt differs from the current committed receipt.')
        saved=pd.read_sql_query('SELECT * FROM committed_predictions ORDER BY target_date',connection)
        actual=pd.read_csv(root/'outputs/results/predictions_test_blind.csv',float_precision='round_trip').sort_values('target_date').reset_index(drop=True)
        pd.testing.assert_frame_equal(saved,actual,check_exact=True)
        if len(saved)!=receipt['rows'] or evidence['committed_prediction_rows']!=len(saved):
            raise ValueError('Reference prediction row counts differ.')
        joined=pd.read_sql_query('SELECT p.target_date,a.y_true FROM committed_predictions p JOIN historical_answers a USING(date,target_date)',connection)
        if len(joined)!=len(saved):raise ValueError('Reference join lost prediction dates.')
    return {'status':'PASS','run_id':receipt['run_id'],'receipt_sha256':receipt_hash,
        'source_tables_checked':checked,'matched_prediction_answer_rows':len(joined),'reference_kind':evidence['reference_kind']}
