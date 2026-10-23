"""Regression cases for the confirmed raw-validation/acquisition/ledger gaps."""
from pathlib import Path
from types import SimpleNamespace
import copy,json,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from weather_acquisition import validate_weather,acquisition_plan,acquire_weather
from prepare_data import build_experiments
from workflow import load_prepared
from common import sha256

class AcquisitionAndLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=acquisition_plan(ROOT);cls.job=cls.plan['jobs'][0]
        snapshot=json.loads((ROOT/'snapshot.json').read_text());cls.frozen=ROOT/'data/raw'/snapshot['raw_run_id']/'weather'
        cls.body=(cls.frozen/cls.job['file']).read_bytes();cls.payload=json.loads(cls.body)
        cls.work=ROOT/'.test_work';cls.work.mkdir(exist_ok=True)

    def temporary(self):
        temp=tempfile.TemporaryDirectory(dir=self.work);self.addCleanup(temp.cleanup);return Path(temp.name)/'capture'

    def getter(self,url,params,timeout):
        job=next(j for j in self.plan['jobs'] if j['parameters']==params)
        return SimpleNamespace(status_code=200,content=(self.frozen/job['file']).read_bytes())

    def test_20_original_weather_units_and_calendar(self):
        report=validate_weather(self.payload,self.job['parameters'])
        self.assertEqual(report['hourly_count'],8784)
        self.assertEqual(report['nonmissing_by_field']['temperature_2m_previous_day1'],8340)

    def test_21_wrong_weather_unit_rejected_before_preparation(self):
        value=copy.deepcopy(self.payload);value['hourly_units']['wind_speed_10m_previous_day1']='km/h'
        with self.assertRaisesRegex(ValueError,'unit'):validate_weather(value,self.job['parameters'])

    def test_22_duplicate_and_wrong_calendar_rejected(self):
        value=copy.deepcopy(self.payload);value['hourly']['time'][1]=value['hourly']['time'][0]
        with self.assertRaisesRegex(ValueError,'calendar'):validate_weather(value,self.job['parameters'])

    def test_23_wrong_forecast_vintage_rejected(self):
        value=copy.deepcopy(self.payload);value['hourly']['temperature_2m_previous_day2']=value['hourly'].pop('temperature_2m_previous_day1')
        with self.assertRaisesRegex(ValueError,'schema'):validate_weather(value,self.job['parameters'])

    def test_24_truncated_weather_field_rejected(self):
        value=copy.deepcopy(self.payload);value['hourly']['surface_pressure_previous_day1'].pop()
        with self.assertRaisesRegex(ValueError,'length'):validate_weather(value,self.job['parameters'])

    def test_25_nulls_preserved_and_nonnumeric_or_nan_rejected(self):
        value=copy.deepcopy(self.payload);before=json.dumps(value,sort_keys=True)
        validate_weather(value,self.job['parameters']);self.assertEqual(json.dumps(value,sort_keys=True),before)
        for bad in ['1.0',float('nan'),True]:
            value=copy.deepcopy(self.payload);value['hourly']['temperature_2m_previous_day1'][500]=bad
            with self.assertRaises(ValueError):validate_weather(value,self.job['parameters'])

    def test_26_real_get_interface_resume_and_frozen_snapshot_preserved(self):
        target=self.temporary();original=sha256(self.frozen/'transfer_manifest.json');calls=[]
        def getter(*args,**kwargs):calls.append(args[0]);return self.getter(*args,**kwargs)
        report=acquire_weather(ROOT,target,request_get=getter)
        self.assertEqual(report['hourly_rows'],17544);self.assertEqual(len(calls),2)
        def no_network(*args,**kwargs):raise AssertionError('Verified resume must not fetch again.')
        self.assertEqual(acquire_weather(ROOT,target,request_get=no_network)['status'],'COMPLETE')
        self.assertEqual(sha256(self.frozen/'transfer_manifest.json'),original)

    def test_27_http_failure_cannot_create_success_status(self):
        target=self.temporary()
        with self.assertRaisesRegex(ValueError,'HTTP'):
            acquire_weather(ROOT,target,request_get=lambda *a,**k:SimpleNamespace(status_code=503,content=b'{"error":true}'))
        self.assertEqual(json.loads((target/'acquisition_status.json').read_text())['status'],'FAILED')
        self.assertNotEqual(json.loads((target/'transfer_manifest.json').read_text())[0]['status'],'COMPLETE')

    def test_28_tampered_resume_rejected(self):
        target=self.temporary();acquire_weather(ROOT,target,request_get=self.getter)
        (target/self.job['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):acquire_weather(ROOT,target,request_get=self.getter)

    def test_29_missing_provider_has_correct_exclusion_reason(self):
        cfg=json.loads((ROOT/'config.json').read_text());daily=load_prepared(ROOT,cfg).copy()
        index=np.flatnonzero(daily.target_date.eq(pd.Timestamp('2025-03-01')))[0];daily.loc[index,'provider_forecast']=np.nan
        target=self.temporary();(target/'outputs/results').mkdir(parents=True);(target/'data/processed').mkdir(parents=True)
        _,_,eligible=build_experiments(target,cfg,daily)
        ledger=pd.read_csv(target/'outputs/results/row_inclusion.csv')
        self.assertFalse(eligible.iloc[index]);self.assertEqual(ledger.first_failure.iloc[index],'provider_reference_missing')
        self.assertTrue(np.array_equal(ledger.first_failure.eq('retained_common'),eligible))

    def test_30_http_200_with_wrong_units_cannot_be_complete(self):
        target=self.temporary();value=copy.deepcopy(self.payload);value['hourly_units']['surface_pressure_previous_day1']='Pa'
        with self.assertRaisesRegex(ValueError,'unit'):
            acquire_weather(ROOT,target,request_get=lambda *a,**k:SimpleNamespace(status_code=200,content=json.dumps(value).encode()))
        self.assertEqual(json.loads((target/'acquisition_status.json').read_text())['status'],'FAILED')

    def test_31_frozen_capture_cannot_be_download_destination(self):
        original=sha256(self.frozen/'transfer_manifest.json')
        with self.assertRaisesRegex(ValueError,'frozen'):
            acquire_weather(ROOT,self.frozen,request_get=self.getter)
        self.assertEqual(sha256(self.frozen/'transfer_manifest.json'),original)

if __name__=='__main__':unittest.main(verbosity=2)
