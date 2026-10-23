"""Run the four required scripts in separate real processes using shared logic."""
import os,sys,json,subprocess
from pathlib import Path
from datetime import datetime,timezone

def main():
    root=Path(__file__).resolve().parent
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(name,'1')
    os.environ['MPLBACKEND']='Agg'
    sys.path.insert(0,str(root/'src'))
    from common import load_config,write_json,sha256
    from workflow import begin_run
    os.chdir(root);root,cfg=load_config();begin_run(root,cfg,'replay')
    stages=[]
    for name in ['fetch_data.py','prepare_data.py','analyse.py','model.py']:
        started=datetime.now(timezone.utc).isoformat()
        completed=subprocess.run([sys.executable,str(root/'src'/name)],cwd=root,check=False)
        stages.append({'script':'src/'+name,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'exit_code':completed.returncode})
        if completed.returncode:raise RuntimeError('Script stage failed: '+name)
    from evaluate_forecast import verify_saved_results
    from reference_store import verify_reference_store
    from workflow import verify_report_dependencies
    proof={'status':'PASS','stages':stages,'metrics':verify_saved_results(root,cfg),'SQL':verify_reference_store(root),
        'report_pages':verify_report_dependencies(root)['physical_pages'],
        'source_sha256':{p.name:sha256(p) for p in sorted((root/'src').glob('*.py'))},
        'scope':'Actual script process execution; notebook execution counts are separate.'}
    write_json(root/'outputs/results/script_route_evidence.json',proof)
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
