from pathlib import Path
import hashlib,json,platform,os,uuid
from datetime import datetime,timezone
import numpy as np
import pandas as pd

def project_root():
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / 'config.json').is_file() and (candidate / 'src').is_dir():
            return candidate
    raise FileNotFoundError('Open a notebook or terminal inside the extracted PM25 project folder.')

def load_config():
    root = project_root()
    cfg = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    if cfg.get('operational_issue_time_local')!='07:00' or cfg.get('study_contract')!='next_day_0700_thai':
        raise ValueError('This study requires the declared 07:00 local next-day contract.')
    for name in ['data/raw', 'data/interim', 'data/processed', 'outputs/figures', 'outputs/results', 'report']:
        (root / name).mkdir(parents=True, exist_ok=True)
    # Curated source/parameter documentation is a reproducible input, not a model result.
    import shutil
    for name in ['source_availability_review.json','model_variable_dictionary.csv']:
        source=root/'report/study_metadata'/name
        if source.is_file():shutil.copyfile(source,root/'outputs/results'/name)
    return root, cfg

def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    os.replace(temporary, path)

def source_config_hash(cfg):
    """Acquisition identity excludes model settings, student identity and report options."""
    keys = ['start_date', 'end_date', 'latitude', 'longitude', 'timezone', 'firms_bbox', 'pm_source', 'weather_source', 'fire_source']
    values = {key: cfg[key] for key in keys}
    values.update(pm_run='12 UTC, leads5..52',weather_model='gfs_global previous_day1',fire_product='GFAS v1.2 UTC daily',precipitation_unit='mm')
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode('utf-8')).hexdigest()

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def runtime_info():
    import importlib.metadata
    packages = {}
    for name in ['numpy', 'pandas', 'requests', 'matplotlib', 'scipy', 'scikit-learn']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = 'not installed'
    return {'python': platform.python_version(), 'packages': packages,
            'created_at_utc': datetime.now(timezone.utc).isoformat()}

def selected_raw_run(root):
    pointer = root / 'data/raw/selected_run.json'
    if not pointer.is_file():
        raise FileNotFoundError('Run 01_fetch_data.ipynb successfully first.')
    run_id = json.loads(pointer.read_text(encoding='utf-8'))['run_id']
    if Path(run_id).name != run_id:
        raise ValueError('Invalid raw run identifier.')
    folder = root / 'data/raw' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'complete':
        raise ValueError('The selected fetch run is incomplete; do not use stale files.')
    for item in manifest['files']:
        if 'sha256' in item and sha256(folder / item['file']) != item['sha256']:
            raise ValueError('Raw checksum mismatch: ' + item['file'])
    return folder, manifest

def paired_block_ci(differences, dates, block_days=14, repeats=1000, seed=42):
    """Moving-block CI with actual calendar gaps respected; last start is included."""
    diff = np.asarray(differences, dtype=float)
    dates = pd.DatetimeIndex(dates)
    boundaries = (np.asarray((dates[1:] - dates[:-1]) != pd.Timedelta(days=1))) | (dates.year[1:] != dates.year[:-1])
    cuts = np.r_[0, np.flatnonzero(boundaries) + 1, len(diff)]
    segments = [diff[a:b] for a, b in zip(cuts[:-1], cuts[1:])]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(repeats):
        sampled = []
        for segment in segments:
            length = min(block_days, len(segment))
            starts = rng.integers(0, len(segment) - length + 1, size=int(np.ceil(len(segment) / length)))
            sampled.append(np.concatenate([segment[s:s + length] for s in starts])[:len(segment)])
        means.append(np.concatenate(sampled).mean())
    return {'estimate': float(diff.mean()), 'ci_low': float(np.quantile(means, .025)),
            'ci_high': float(np.quantile(means, .975)), 'n': len(diff),
            'block_days': block_days, 'bootstrap_repeats': repeats,
            'segment_lengths': [len(segment) for segment in segments]}
