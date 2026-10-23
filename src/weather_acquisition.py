"""Real public GFS acquisition and shared raw validation; never replace study data silently."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
import numpy as np
import pandas as pd
import requests
from common import sha256,write_json

ENDPOINT='https://previous-runs-api.open-meteo.com/v1/forecast'
FIELDS=['temperature_2m','relative_humidity_2m','wind_speed_10m','wind_direction_10m','precipitation','surface_pressure']
UNITS=['°C','%','m/s','°','mm','hPa']

def validate_weather(payload,parameters):
    """Check the returned calendar/units without filling or altering source values."""
    wanted=[name+'_previous_day1' for name in FIELDS]
    if parameters.get('models')!='gfs_global' or parameters.get('timezone')!='UTC' or parameters.get('wind_speed_unit')!='ms':
        raise ValueError('Weather request differs from the fixed model/time/unit contract.')
    if set(parameters.get('hourly','').split(','))!=set(wanted):raise ValueError('Wrong requested weather fields/vintages.')
    if not isinstance(payload,dict) or payload.get('error'):raise ValueError('Weather response is not a successful object.')
    hourly=payload.get('hourly');units=payload.get('hourly_units',{})
    if not isinstance(hourly,dict) or set(hourly)!={'time',*wanted}:raise ValueError('Wrong weather hourly schema.')
    if payload.get('utc_offset_seconds')!=0:raise ValueError('Weather source timestamps must be UTC.')
    for name,unit in zip(wanted,UNITS):
        if units.get(name)!=unit:raise ValueError('Wrong weather unit: '+name)
    if not isinstance(hourly['time'],list):raise ValueError('Weather times must be an array.')
    expected=pd.date_range(parameters['start_date'],pd.Timestamp(parameters['end_date'])+pd.Timedelta(hours=23),freq='h',tz='UTC')
    actual=pd.DatetimeIndex(pd.to_datetime(hourly['time'],utc=True,errors='raise'))
    if len(actual)!=len(expected) or actual.has_duplicates or not np.array_equal(actual.as_unit('ns').asi8,expected.as_unit('ns').asi8):
        raise ValueError('Weather times do not match the complete requested hourly calendar.')
    nonmissing={}
    for name in wanted:
        values=hourly[name]
        if not isinstance(values,list) or len(values)!=len(expected):raise ValueError('Weather field length mismatch: '+name)
        if any(value is not None and (isinstance(value,bool) or not isinstance(value,(int,float))) for value in values):
            raise ValueError('Weather values must be JSON numbers or null: '+name)
        if any(value is not None and not np.isfinite(value) for value in values):raise ValueError('Nonfinite weather number: '+name)
        array=np.asarray(values,dtype=float)
        if np.isinf(array).any():raise ValueError('Infinite weather values: '+name)
        nonmissing[name]=int(np.isfinite(array).sum())
    for coordinate in ['latitude','longitude']:
        if coordinate not in payload or not np.isfinite(float(payload[coordinate])):raise ValueError('Missing weather response grid identity.')
    return {'status':'PASS','hourly_count':len(actual),'first_time_utc':actual[0].isoformat(),'last_time_utc':actual[-1].isoformat(),
        'nonmissing_by_field':nonmissing,'response_grid':{name:payload[name] for name in ['latitude','longitude']},
        'project_fill_count':0,'scope':'Raw schema, units and requested hours; null values remain missing. No historical publication certification.'}

def acquisition_plan(project):
    snapshot=json.loads((project/'snapshot.json').read_text(encoding='utf-8'))
    manifest=project/'data/raw'/snapshot['raw_run_id']/'weather/transfer_manifest.json'
    records=json.loads(manifest.read_text(encoding='utf-8'))
    jobs=[]
    for item in records:
        if item['requested_url']!=ENDPOINT:raise ValueError('Unexpected weather endpoint in frozen source specification.')
        if Path(item['file']).name!=item['file']:raise ValueError('Invalid weather filename.')
        jobs.append({'file':item['file'],'endpoint':ENDPOINT,'parameters':item['parameters']})
    return {'schema':1,'jobs':jobs,'source':'GFS previous_day1, exact study requests; public API',
        'scope':'New capture for inspection; does not update snapshot.json or the frozen scientific study.'}

def acquire_weather(project,capture,request_get=None):
    """GET actual responses, save exact bytes, check them, resume verified successes."""
    project=Path(project).resolve();capture=Path(capture).resolve()
    snapshot=json.loads((project/'snapshot.json').read_text(encoding='utf-8'))
    frozen=(project/'data/raw'/snapshot['raw_run_id']).resolve()
    if capture==frozen or capture.is_relative_to(frozen) or frozen.is_relative_to(capture):
        raise ValueError('New acquisition must not overwrite or contain the frozen study capture.')
    plan=acquisition_plan(project);canonical=json.dumps(plan,sort_keys=True,separators=(',',':'))
    plan_hash=hashlib.sha256(canonical.encode()).hexdigest()
    lock={'plan_sha256':plan_hash,'acquirer_sha256':sha256(Path(__file__))}
    capture.mkdir(parents=True,exist_ok=True)
    plan_path=capture/'weather_plan.json';receipt_path=capture/'transfer_manifest.json'
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding='utf-8'))!=plan:raise ValueError('Acquisition plan changed; use another capture folder.')
        if not (capture/'weather_acquisition_lock.json').is_file() or json.loads((capture/'weather_acquisition_lock.json').read_text())!=lock:raise ValueError('Weather acquisition source/lock changed; use another capture folder.')
    else:
        if any(capture.iterdir()):raise ValueError('A new weather capture must start in an empty folder.')
        write_json(plan_path,plan)
        write_json(capture/'weather_acquisition_lock.json',lock)
    receipts=json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else []
    by_file={row['file']:row for row in receipts}
    if len(by_file)!=len(receipts) or not set(by_file)<={job['file'] for job in plan['jobs']}:raise ValueError('Unexpected/duplicate weather receipts.')
    getter=request_get or requests.get
    write_json(capture/'acquisition_status.json',{'status':'RUNNING',**lock})
    try:
        for job in plan['jobs']:
            path=capture/job['file'];previous=by_file.get(job['file'])
            if previous and previous.get('status')=='COMPLETE':
                if previous['parameters']!=job['parameters'] or sha256(path)!=previous['sha256']:raise ValueError('Saved weather capture changed.')
                validate_weather(json.loads(path.read_bytes()),job['parameters'])
                continue
            started=datetime.now(timezone.utc).isoformat()
            response=getter(job['endpoint'],params=job['parameters'],timeout=(15,120))
            data=response.content
            temporary=path.with_suffix(path.suffix+'.part');temporary.write_bytes(data);os.replace(temporary,path)
            record={'file':job['file'],'requested_url':job['endpoint'],'parameters':job['parameters'],
                'request_started_at_utc':started,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                'http_status':response.status_code,'bytes':len(data),'sha256':sha256(path),'credentials_supplied_by_tool':False,
                'transport':'requests.get' if request_get is None else 'injected_test_transport','acquirer_sha256':lock['acquirer_sha256'],'status':'RECEIVED_NOT_YET_VALIDATED'}
            by_file[job['file']]=record;write_json(receipt_path,list(by_file.values()))
            if response.status_code!=200:raise ValueError('Weather HTTP request failed; exact returned body retained.')
            record['validation']=validate_weather(json.loads(data),job['parameters']);record['status']='COMPLETE'
            write_json(receipt_path,list(by_file.values()))
    except Exception as error:
        write_json(capture/'acquisition_status.json',{'status':'FAILED','error_type':type(error).__name__,'plan_sha256':plan_hash,
            'scope':'No success receipt; inspect saved raw response and receipts. Frozen study not changed.'})
        raise
    result={'status':'COMPLETE','requests':len(plan['jobs']),**lock,
        'hourly_rows':sum(row['validation']['hourly_count'] for row in by_file.values()),'new_capture':str(capture),
        'scope':'Real GETs or verified saved responses. Inspect before a new scientific revision; not original historical public-release proof.'}
    write_json(capture/'acquisition_status.json',result)
    return result
