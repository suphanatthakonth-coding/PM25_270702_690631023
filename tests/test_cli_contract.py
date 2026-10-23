"""Regression coverage for the previously confirmed CLI/stale-PASS defects."""
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]

class CLIContractTests(unittest.TestCase):
    def exercise(self,arguments):
        base=ROOT/'.test_work';base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='cli_',dir=base) as temporary:
            root=Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(base.resolve()))
            shutil.copytree(ROOT/'src',root/'src',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(ROOT/'config.json',root/'config.json')
            results=root/'outputs/results';results.mkdir(parents=True)
            (results/'dataset_checks.json').write_text(json.dumps({'technical_status':'PASS','run_id':'stale_fixture'})+'\n',encoding='utf-8')
            command=[sys.executable,'src/check_dataset.py',*arguments]
            run=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            self.assertNotEqual(run.returncode,0)
            report=json.loads((results/'dataset_checks.json').read_text(encoding='utf-8'))
            attempt=json.loads((results/'checker_cli_attempt.json').read_text(encoding='utf-8'))
            self.assertEqual(report['technical_status'],'FAIL')
            self.assertEqual(attempt['status'],'FAIL')
            self.assertNotEqual(report['run_id'],'stale_fixture')
            self.assertEqual(report['temporal_cutoff_status'],'NOT_EVALUATED')
            self.assertIn('NOT FEASIBLE',(root/'feasibility_report.txt').read_text(encoding='utf-8'))
            return attempt['reason']

    def test_32_nonexistent_fetch_script_rejected(self):
        self.assertIn('fetch-script',self.exercise(['--fetch-script','does_not_exist_12345.py']))

    def test_33_unsupported_fetch_script_rejected(self):
        self.assertIn('fetch-script',self.exercise(['--fetch-script','src/model.py']))

    def test_34_unsupported_target_rejected(self):
        self.assertIn('target/time',self.exercise(['--target','not_this_target']))

if __name__=='__main__':unittest.main()
