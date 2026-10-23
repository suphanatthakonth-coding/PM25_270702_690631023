"""Targeted regressions for the confirmed source/time/evidence defects.

All mutation tests operate only on explicit temporary copies inside this project.
"""
from pathlib import Path
import copy,json,math,shutil,sqlite3,sys,tempfile,unittest
from unittest.mock import patch
from contextlib import closing
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import sha256
from workflow import load_prepared
from prepare_data import build_experiments,PM,WEATHER,FIRE,prepare_weather
from check_dataset import experiment_contract_issues
from model import partition_rows,calendar_cv,estimator_grid
from evaluate_forecast import _verify_lock,predict_blind,verify_saved_results
from reference_store import verify_reference_store

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        cls.daily=load_prepared(ROOT,cls.cfg)
        cls.X,cls.specs,cls.eligible=build_experiments(ROOT,cls.cfg,cls.daily)
        cls.plan=json.loads((ROOT/'outputs/results/forecast_lock.json').read_text(encoding='utf-8'))
        cls.temp_base=ROOT/'.test_work';cls.temp_base.mkdir(exist_ok=True)

    def temporary(self):
        temp=tempfile.TemporaryDirectory(prefix='contract_',dir=self.temp_base)
        self.assertTrue(Path(temp.name).resolve().is_relative_to(ROOT.resolve()))
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def frozen_copy(self):
        root=self.temporary()
        names=set(self.plan['locked_artifacts'])|set(self.plan['provenance_artifacts'])|{self.plan['answer_file'],
            'outputs/results/forecast_lock.json','outputs/results/prediction_receipt.json','outputs/results/evaluation_receipt.json',
            'outputs/results/reference_store.json','data/processed/reference_store.sqlite','outputs/results/predictions_test_blind.csv',
            'outputs/results/predictions_test.csv','outputs/results/model_scores.csv','outputs/results/metrics.csv'}
        evaluation=json.loads((ROOT/'outputs/results/evaluation_receipt.json').read_text())
        names|={'outputs/results/'+name for name in evaluation['result_hashes']}
        for name in names:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        return root

    def test_01_issue_and_target_horizon(self):
        d=self.daily
        origin=pd.to_datetime(d.forecast_origin_utc,utc=True)
        start=pd.DatetimeIndex(d.target_date).tz_localize('Asia/Bangkok').tz_convert('UTC')
        finish=pd.to_datetime(d.target_complete_utc,utc=True)
        self.assertTrue(((start-origin)==pd.Timedelta(hours=17)).all())
        self.assertTrue(((finish-origin)==pd.Timedelta(hours=41)).all())
        self.assertTrue((d.target_date==d.date+pd.Timedelta(days=2)).all())

    def test_02_fire_utc_offset_including_leap_day(self):
        d=self.daily
        self.assertTrue((d.fire_source_day_utc==d.issue_date-pd.Timedelta(days=2)).all())
        row=d.loc[d.target_date.eq(pd.Timestamp('2024-02-29'))].iloc[0]
        self.assertEqual(str(row.fire_source_day_utc.date()),'2024-02-26')

    def test_03_target_unknown_tail_never_filled_safe(self):
        np.testing.assert_allclose(self.daily.pm25_tomorrow,self.daily.pm25_mean.shift(-2),equal_nan=True)
        self.assertTrue(self.daily.iloc[-2:].pm25_tomorrow.isna().all())
        self.assertTrue(self.daily.iloc[-2:].exceed_tomorrow.isna().all())

    def test_04_exact_source_and_window_contracts(self):
        self.assertEqual(experiment_contract_issues(self.cfg,self.specs),[])
        broken=copy.deepcopy(self.specs);broken[0]['features'][0]='pm25_tomorrow'
        self.assertTrue(experiment_contract_issues(self.cfg,broken))
        broken=copy.deepcopy(self.specs);broken[0]['features'].append(broken[0]['features'][0])
        self.assertTrue(experiment_contract_issues(self.cfg,broken))

    def test_05_whole_calendar_lag_does_not_bridge_missing(self):
        for column in self.X:
            name,lag=column.rsplit('_lag',1)
            np.testing.assert_allclose(self.X[column],self.daily[name].shift(int(lag)),equal_nan=True)
        self.assertFalse(self.X.loc[pd.Timestamp('2024-01-10')].notna().all())
        self.assertTrue(self.X.loc[pd.Timestamp('2024-01-26')].notna().all())

    def test_06_advisory_masks_selection_not_raw_values(self):
        d=self.daily
        affected=d.in_study_target_calendar&d.source_advisory_dependency
        self.assertEqual(int(affected.sum()),15)
        self.assertEqual(str(d.loc[affected,'target_date'].min().date()),'2024-08-09')
        self.assertEqual(str(d.loc[affected,'target_date'].max().date()),'2024-08-23')
        self.assertTrue(d.loc[affected,'pm25_mean'].notna().all())
        self.assertFalse(self.eligible.iloc[np.flatnonzero(affected)].any())

    def test_07_common_cohort_and_calendar_partitions(self):
        self.assertEqual(int(self.eligible.sum()),687)
        rows=partition_rows(self.daily,self.eligible,self.cfg)
        self.assertEqual({k:len(v) for k,v in rows.items()},{'train':231,'validation':91,'test':365})
        dates=self.daily.target_date.iloc[rows['test']]
        self.assertEqual(dates.tolist(),list(pd.date_range('2025-01-01','2025-12-31')))

    def test_08_outer_unmatured_label_is_rejected(self):
        cfg=copy.deepcopy(self.cfg);cfg['train_target_end']='2024-09-30'
        eligibility=self.eligible.copy()
        pos=np.flatnonzero(self.daily.target_date.eq(pd.Timestamp('2024-09-30')))[0]
        eligibility.iloc[pos]=True
        with self.assertRaisesRegex(ValueError,'Outer labels unavailable'):
            partition_rows(self.daily,eligibility,cfg)

    def test_09_every_cv_label_complete_before_issue(self):
        rows=partition_rows(self.daily,self.eligible,self.cfg)
        folds,proof=calendar_cv(self.daily,self.eligible,rows['train'],self.cfg)
        self.assertEqual(len(folds),3)
        for (a,b),record in zip(folds,proof):
            self.assertTrue(record['label_maturity_pass'])
            actual=rows['train'][a];validation=rows['train'][b]
            self.assertTrue(pd.to_datetime(self.daily.target_complete_utc.iloc[actual],utc=True).le(pd.Timestamp(self.daily.forecast_origin_utc.iloc[validation[0]])).all())

    def test_10_area_integration_has_correct_units_and_extent(self):
        proof=json.loads((ROOT/'outputs/results/fire_area_aggregation.json').read_text())
        expected=self.cfg['earth_radius_m']**2*math.radians(4)*(math.sin(math.radians(21))-math.sin(math.radians(17.5)))
        self.assertAlmostEqual(proof['total_bbox_area_m2']/expected,1.0,places=12)
        fire=pd.read_csv(ROOT/'data/interim/gfas_daily_derived.csv')
        np.testing.assert_allclose(fire.log_fire_power_mw,np.log1p(fire.fire_power_mw))
        self.assertTrue(fire.fire_positive_area_fraction.between(0,1).all())

    def test_11_native_zeros_and_offire_above_one_preserved(self):
        fire=pd.read_csv(ROOT/'data/interim/gfas_daily_derived.csv',parse_dates=['fire_source_day_utc'])
        streak=fire.fire_source_day_utc.between('2025-06-11','2025-08-08')
        self.assertEqual(int(streak.sum()),59)
        self.assertTrue(fire.loc[streak,'fire_power_mw'].eq(0).all())
        self.assertTrue(fire.loc[streak,'fire_observation_area_fraction'].gt(0).all())
        self.assertTrue(fire.fire_opportunity_weighted_mean.gt(1).any())
        self.assertFalse(fire.fire_project_fill_applied.any())

    def test_12_wind_components_before_averaging(self):
        d=self.daily
        length=np.hypot(d.wind_u_ms,d.wind_v_ms)
        self.assertTrue((length.le(d.wind_speed_ms+1e-12)|length.isna()).all())
        self.assertNotIn('wind_direction_10m',self.X.columns)

    def test_13_scaling_and_grids_preserved(self):
        ridge,grid=estimator_grid('ridge',self.cfg)
        self.assertEqual(list(ridge.named_steps),['scale','model'])
        self.assertEqual(grid['model__alpha'],[.1,1.,10.,100.,1000.])
        hgb,secondary=estimator_grid('hgb',self.cfg)
        self.assertEqual(hgb['model'].max_iter,200)
        self.assertEqual(secondary['model__max_leaf_nodes'],[7,15])

    def test_14_nominal_clock_does_not_unlock_operational_prediction(self):
        from availability import validate_operational_inputs
        feature=pd.read_csv(ROOT/self.plan['feature_file'])
        with self.assertRaisesRegex(ValueError,'Operational prediction blocked:'):
            validate_operational_inputs(ROOT,self.plan,feature)

    def test_15_prediction_runs_when_answer_file_cannot_be_opened(self):
        root=self.frozen_copy();(root/self.plan['answer_file']).unlink()
        import builtins
        original=builtins.open
        def guarded(file,*args,**kwargs):
            if str(file).endswith('test_answers.csv'):raise AssertionError('Prediction attempted to read answers.')
            return original(file,*args,**kwargs)
        with patch('builtins.open',side_effect=guarded):
            receipt=predict_blind(root)
        self.assertFalse(receipt['test_answers_opened_by_prediction_stage'])
        self.assertEqual(receipt['rows'],365)

    def test_16_source_change_invalidates_frozen_prediction(self):
        root=self.frozen_copy();path=root/'src/report_document.py'
        path.write_text(path.read_text(encoding='utf-8')+'\n# mutation\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Frozen artifact changed'):_verify_lock(root,self.plan)

    def test_17_sql_tamper_detected_even_after_database_hash_update(self):
        root=self.frozen_copy();database=root/'data/processed/reference_store.sqlite'
        with closing(sqlite3.connect(database)) as conn,conn:
            conn.execute('UPDATE training SET y_true=y_true+1 WHERE rowid=1');conn.commit()
        path=root/'outputs/results/reference_store.json';evidence=json.loads(path.read_text());evidence['database_sha256']=sha256(database)
        path.write_text(json.dumps(evidence),encoding='utf-8')
        with self.assertRaises(AssertionError):verify_reference_store(root)

    def test_18_every_saved_score_recomputed(self):
        evidence=verify_saved_results(ROOT,self.cfg)
        self.assertEqual(evidence['independently_recomputed_metric_rows'],54)

    def test_19_changed_metrics_cannot_reuse_receipt(self):
        root=self.frozen_copy();path=root/'outputs/results/model_scores.csv'
        frame=pd.read_csv(path);frame.loc[0,'MAE']+=1;frame.to_csv(path,index=False)
        with self.assertRaisesRegex(ValueError,'Evaluated output changed'):verify_saved_results(root,self.cfg)

if __name__=='__main__':unittest.main(verbosity=2)
