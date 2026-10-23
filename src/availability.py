"""Fail-closed publication-evidence checks; calendar lags alone are insufficient."""
from pathlib import Path
import pandas as pd
from common import sha256


def validate_operational_inputs(root, plan, features):
    prefix = 'Operational prediction blocked: '
    required = {name for model in plan['models'] for name in model['features']}
    required.add('B1_provider_forecast')
    required.add('pm25_mean_lag0')  # The persistence value needs the same publication proof.
    path = root/'outputs/results/feature_availability.csv'
    summary = pd.read_csv(path)
    columns = {'feature','availability_status','operational_use_allowed','documented_latency_conflict'}
    if not columns.issubset(summary) or summary.empty:
        raise ValueError(prefix+'empty or malformed feature-availability table.')
    if summary.feature.duplicated().any() or set(summary.feature) != required:
        raise ValueError(prefix+'missing, extra or duplicate feature identities.')
    if not summary.operational_use_allowed.eq(True).all() or not summary.availability_status.eq('VERIFIED').all():
        raise ValueError(prefix+'feature publication evidence remains unverified.')
    if not summary.documented_latency_conflict.eq(False).all():
        raise ValueError(prefix+'documented source latency conflicts are unresolved.')
    evidence_path = root/'data/processed/availability_evidence.csv'
    key = evidence_path.relative_to(root).as_posix()
    if key not in plan['locked_artifacts'] or not evidence_path.is_file():
        raise ValueError(prefix+'no frozen per-forecast publication evidence.')
    evidence = pd.read_csv(evidence_path)
    fields = {'target_date','feature','available_at_utc','source_product','evidence_file','evidence_sha256','availability_status'}
    if evidence.empty or not fields.issubset(evidence):
        raise ValueError(prefix+'empty or malformed publication records.')
    if evidence[['target_date','feature']].duplicated().any():
        raise ValueError(prefix+'duplicate publication records.')
    dates = features[['target_date','forecast_origin_utc']].copy()
    if dates.target_date.duplicated().any():
        raise ValueError(prefix+'duplicate forecast dates.')
    wanted = pd.MultiIndex.from_product([dates.target_date, sorted(required)], names=['target_date','feature'])
    actual = pd.MultiIndex.from_frame(evidence[['target_date','feature']])
    if len(actual) != len(wanted) or set(actual) != set(wanted):
        raise ValueError(prefix+'publication records do not cover every forecast and input.')
    aligned = evidence.merge(dates, on='target_date', validate='many_to_one')
    for column in ['available_at_utc','forecast_origin_utc']:
        for value in aligned[column]:
            try: valid = pd.notna(value) and pd.Timestamp(value).tzinfo is not None
            except (ValueError, TypeError): valid = False
            if not valid:raise ValueError(prefix+'publication timestamps must include an explicit timezone.')
    available = pd.to_datetime(aligned.available_at_utc, utc=True, errors='coerce')
    origin = pd.to_datetime(aligned.forecast_origin_utc, utc=True, errors='coerce')
    if available.isna().any() or origin.isna().any() or available.gt(origin).any():
        raise ValueError(prefix+'missing or post-origin publication timestamps.')
    if not aligned.availability_status.eq('VERIFIED').all() or aligned.source_product.fillna('').str.strip().eq('').any():
        raise ValueError(prefix+'unverified source-product identity.')
    base = root.resolve()
    for row in aligned[['evidence_file','evidence_sha256']].drop_duplicates().itertuples(index=False):
        candidate = (base/str(row.evidence_file)).resolve()
        if not candidate.is_relative_to(base) or not candidate.is_file() or sha256(candidate) != row.evidence_sha256:
            raise ValueError(prefix+'missing, changed or out-of-project evidence.')
        if candidate.relative_to(base).as_posix() not in plan['locked_artifacts']:
            raise ValueError(prefix+'evidence file was not frozen with the experiment.')
    return {'status':'PASS','feature_count':len(required),'forecast_count':len(dates),
            'scope':'Record completeness, chronology and integrity; source-document authenticity still requires review.'}
