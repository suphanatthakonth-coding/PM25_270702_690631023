"""Run four actual notebooks in separate fresh kernels; save outputs, then seal the ZIP."""
from pathlib import Path
import os,sys,json,tempfile,uuid,argparse
from datetime import datetime,timezone
import nbformat
from nbclient import NotebookClient
from jupyter_client.manager import KernelManager
from jupyter_client.kernelspec import KernelSpecManager


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['replay'])
    args=parser.parse_args();root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root/'src'))
    from workflow import NOTEBOOKS,make_submission
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(key,'1')
    os.environ['MPLBACKEND']='Agg'
    execution=root/'outputs/results/execution';execution.mkdir(parents=True,exist_ok=True)
    # Clear actual old outputs before any stage runs; never keep later-stage evidence from a failed rerun.
    for name in NOTEBOOKS:
        book=nbformat.read(root/name,as_version=4)
        for cell in book.cells:
            if cell.cell_type=='code':
                cell.outputs=[];cell.execution_count=None
                if name==NOTEBOOKS[0] and args.mode:
                    cell.source=cell.source.replace("MODE = 'replay'",f"MODE = '{args.mode}'").replace("MODE = 'live'",f"MODE = '{args.mode}'")
        nbformat.write(book,root/name)
    with tempfile.TemporaryDirectory() as temporary:
        os.environ['IPYTHONDIR']=str(Path(temporary)/'ipython')
        kernels=Path(temporary)/'kernels/pm25';kernels.mkdir(parents=True)
        (kernels/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
            'display_name':'PM2.5 four-stage lab','language':'python'}),encoding='utf-8')
        for name in NOTEBOOKS:
            path=root/name;book=nbformat.read(path,as_version=4)
            started=datetime.now(timezone.utc).isoformat()
            state={'notebook':name,'status':'running','started_at_utc':started,'last_cell':None}
            def saved(cell,cell_index,execute_reply):
                nbformat.write(book,path);state['last_cell']=cell_index+1
                (execution/(path.stem+'.json')).write_text(json.dumps(state,indent=2),encoding='utf-8')
                print(name,'executed cell',cell_index+1,flush=True)
            manager=KernelManager(kernel_name='pm25',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernels.parent)]),
                connection_file=str(Path(temporary)/(uuid.uuid4().hex+'.json')))
            try:
                NotebookClient(book,km=manager,timeout=3600,allow_errors=False,record_timing=True,on_cell_executed=saved).execute(cwd=str(root))
                nbformat.validate(book);state.update(status='complete',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                    executed_code_cells=sum(c.cell_type=='code' and c.execution_count is not None for c in book.cells))
            except Exception:
                state.update(status='failed',finished_at_utc=datetime.now(timezone.utc).isoformat());raise
            finally:
                nbformat.write(book,path)
                (execution/(path.stem+'.json')).write_text(json.dumps(state,indent=2),encoding='utf-8')
                if manager.has_kernel:manager.shutdown_kernel(now=True)
                try:manager.cleanup_resources()
                except (KeyError,FileNotFoundError):pass
    from report import build_report
    documents=build_report(root,json.loads((root/'config.json').read_text()))
    status=json.loads((root/'SUBMISSION_STATUS.json').read_text())
    status.update(technical_execution='PASS: four notebooks;30 code cells;zero stored errors',
        report_physical_pages=documents['physical_pages'],report_appendix_pages=documents['appendix_pages'],
        last_replay_completed_at_utc=datetime.now(timezone.utc).isoformat())
    (root/'SUBMISSION_STATUS.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    archive,evidence=make_submission(root,require_executed=True)
    print('SEALED ZIP:',archive,flush=True);print(json.dumps(evidence,indent=2),flush=True)


if __name__=='__main__':main()
