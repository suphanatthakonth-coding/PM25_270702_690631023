"""Verify actual ADS/weather raw snapshots and regenerate native source exports."""
import json
from pathlib import Path
import pandas as pd
from common import load_config,selected_raw_run,source_config_hash,write_json,sha256
from ads_bulk_acquisition import inspect_file,make_plan,canonical

def fetch(root,cfg,mode='replay',key=None):
    if mode!='replay':
        raise ValueError('Use the supplied ADS acquisition helper with personal authentication for new transfers; import its complete immutable snapshot as a separately reviewed snapshot. This reproducible study replays the actual captured responses.')
    folder=root/'data/raw'/json.loads((root/'snapshot.json').read_text())['raw_run_id']
    original=json.loads((folder/'ads/manifest.json').read_text())
    for name,digest in original.items():
        if sha256(folder/'ads'/name)!=digest:raise ValueError('ADS raw manifest mismatch: '+name)
    plan=json.loads((folder/'ads/plan.json').read_text())
    if plan!=make_plan():raise ValueError('ADS acquisition plan differs from reviewed plan.')
    lock=json.loads((folder/'ads/acquisition_lock.json').read_text())
    import hashlib
    if hashlib.sha256(canonical(plan).encode()).hexdigest()!=lock['plan_sha256']:raise ValueError('Plan lock mismatch.')
    hourly=[];daily=[];fields=[];receipt_rows=[]
    for number,job in enumerate(plan['jobs'],1):
        rawfolder=folder/'ads/jobs'/job['job_key']
        receipt=json.loads((rawfolder/'transfer_receipt.json').read_text())
        if receipt['job']!=job or receipt['lock']!=lock or receipt['sha256']!=sha256(rawfolder/'raw.grib'):
            raise ValueError('Transfer receipt mismatch: '+job['job_key'])
        if receipt['original_publication_time_observed'] is not False:raise ValueError('Unsupported original-release claim.')
        decoded=inspect_file(rawfolder/'raw.grib',job)
        saved=json.loads((rawfolder/'qc.json').read_text())
        if decoded!=saved:raise ValueError('Native raw and saved QC differ: '+job['job_key'])
        hourly.extend(decoded['pm_hourly']);daily.extend(decoded['pm_daily'])
        fields.extend(dict(item,family=job['family'],job_key=job['job_key']) for item in decoded['fields'])
        receipt_rows.append({'job':job['job_key'],'messages':decoded['messages'],'missing_grid_values':decoded['missing_or_nonfinite_grid_values'],'raw_sha256':receipt['sha256']})
        print('Raw source check',number,'/50:',job['job_key'],flush=True)
    exports=root/'data/interim/native_exports';exports.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(hourly).to_csv(exports/'pm_hourly.csv',index=False)
    pd.DataFrame(daily).to_csv(exports/'pm_profiles.csv',index=False)
    write_json(exports/'field_metadata.json',fields)
    weather_manifest=json.loads((folder/'weather/transfer_manifest.json').read_text())
    from weather_acquisition import validate_weather
    weather_audit=[]
    for item in weather_manifest:
        if item['http_status']!=200 or sha256(folder/'weather'/item['file'])!=item['sha256']:raise ValueError('Weather raw hash mismatch.')
        checked=validate_weather(json.loads((folder/'weather'/item['file']).read_bytes()),item['parameters'])
        weather_audit.append({'file':item['file'],'sha256':item['sha256'],**checked})
    write_json(root/'outputs/results/weather_raw_audit.json',{'status':'PASS','sources':weather_audit,'scope':'Original captured weather schema/units/calendar validated before preparation; no values changed.'})
    files=[]
    for path in sorted(folder.rglob('*')):
        if path.is_file() and path!=folder/'manifest.json':
            files.append({'file':path.relative_to(folder).as_posix(),'sha256':sha256(path),'bytes':path.stat().st_size,'status':'success'})
    manifest={'run_id':folder.name,'status':'complete','config':cfg,'source_config_hash':source_config_hash(cfg),'files':files,
        'purpose':'Exact actual API responses and original acquisition receipts; current retrieval is not historical publication.'}
    write_json(folder/'manifest.json',manifest)
    write_json(root/'data/raw/selected_run.json',{'run_id':folder.name})
    proof={'status':'PASS','requests':50,'native_messages':len(fields),'PM_runs':len(daily)//2,
        'raw_manifest_sha256':sha256(folder/'manifest.json'),'source_sha256':sha256(root/'src/ads_bulk_acquisition.py'),
        'exports':{p.relative_to(root).as_posix():sha256(p) for p in exports.glob('*')},'records':receipt_rows,
        'scientific_scope':'Real native data validation; no historical public-release certificate.'}
    write_json(root/'outputs/results/raw_decode_audit.json',proof)
    return folder,manifest

if __name__=='__main__':
    import argparse,subprocess,sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquire-new',type=Path,help='Run real authenticated ADS acquisition into this persistent capture folder; do not replace the frozen study silently.')
    parser.add_argument('--max-new-jobs',type=int,default=50)
    parser.add_argument('--acquire-weather',type=Path,help='Download the exact public GFS study requests into a separate persistent raw capture; never overwrite the frozen study.')
    args=parser.parse_args()
    if args.acquire_new is not None and args.acquire_weather is not None:parser.error('Choose one acquisition product at a time.')
    if args.acquire_weather is not None:
        from weather_acquisition import acquire_weather
        print(json.dumps(acquire_weather(Path(__file__).resolve().parents[1],args.acquire_weather),indent=2))
        raise SystemExit(0)
    if args.acquire_new is not None:
        project=Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable,str(project/'tools/acquire_ads.py'),'--root',str(args.acquire_new),
            '--max-new-jobs',str(args.max_new_jobs)],check=True)
    else:
        root,cfg=load_config()
        from workflow import acquire_all
        acquire_all(root,cfg,mode='replay')
