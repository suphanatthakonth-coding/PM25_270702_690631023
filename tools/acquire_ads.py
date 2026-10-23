"""Optional real authenticated acquisition into a persistent new capture folder.

This tool does not silently replace the frozen study snapshot. Inspect/export the
complete capture first. Reuse --root on interruption; never submit concurrent runs.
"""
from pathlib import Path
import argparse,getpass,json,sys,warnings

def main():
    project=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(project/'src'))
    import ads_bulk_acquisition as acq
    from ecmwf.datastores import Client
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='New persistent capture folder; keep it for resume.')
    parser.add_argument('--max-new-jobs',type=int,default=50)
    args=parser.parse_args()
    source=project/'src/ads_bulk_acquisition.py'
    plan=acq.prepare(args.root,source)
    print('Fixed monthly requests:',len(plan['jobs']))
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        token=getpass.getpass('ADS personal access token (hidden): ').strip()
    client=failure=None
    try:
        if not token:raise ValueError('Actual ADS token required.')
        client=Client(url='https://ads.atmosphere.copernicus.eu/api',key=token,progress=False,cleanup=False,
            maximum_tries=1,timeout=60,log_callback=lambda *args,**kwargs:None)
        client.check_authentication()
        print(json.dumps(acq.run_jobs(args.root,client,source,max_new_jobs=args.max_new_jobs),indent=2))
    except Exception as error:
        failure=acq.safe_error(error,token)
    finally:
        token=None;client=None
    if failure:
        print(json.dumps(failure,indent=2))
        raise RuntimeError('Acquisition stopped; preserve the capture folder and inspect its existing ADS jobs.') from None
    archive,summary=acq.export_evidence(args.root,source)
    print('Exported:',archive)
    return summary

if __name__=='__main__':main()
