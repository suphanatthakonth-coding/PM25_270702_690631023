"""Check installed versions against delivered pins instead of silently relabelling them."""
import importlib.metadata
import json,platform
from common import write_json


def check_environment(root,strict=True):
    rows=[]
    for line in (root/'requirements.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        name,wanted=line.split('==',1)
        try:actual=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:actual='NOT_INSTALLED'
        rows.append({'package':name,'required':wanted,'installed':actual,'status':'PASS' if actual==wanted else 'FAIL'})
    result={'status':'PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL','python':platform.python_version(),
        'requirements':rows,'scope':'Package version check in this environment; see separate clean-environment reproduction evidence.'}
    write_json(root/'outputs/results/dependency_check.json',result)
    if strict and result['status']!='PASS':raise RuntimeError('Dependency versions differ. Install requirements.txt in a fresh Python 3.12 environment and restart the kernel.')
    return result


if __name__=='__main__':
    from common import load_config
    root,cfg=load_config();print(json.dumps(check_environment(root),indent=2))
