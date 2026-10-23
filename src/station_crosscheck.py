"""C6: independent station reference versus a matched rolling 24-hour CAMS window.

This contemporary comparison is kept separate from historical H1-H4 modelling.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
from common import write_json, sha256

STATION_ENDPOINT = 'https://air4thai.pcd.go.th/services/getNewAQI_JSON.php'
PERIOD_SOURCE = 'https://epo08.pcd.go.th/th/news/detail/180206'
AQ_ENDPOINT = 'https://air-quality-api.open-meteo.com/v1/air-quality'


def verified_download(endpoint, params, path, windows_fallback=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {'endpoint': endpoint, 'params': params, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
    try:
        response = requests.get(endpoint, params=params, timeout=(15, 60))
        path.write_bytes(response.content)
        response.raise_for_status()
        metadata.update({'http_status': response.status_code, 'transport': 'requests; TLS verified'})
    except requests.exceptions.SSLError:
        if not windows_fallback or os.name != 'nt':
            raise
        executable = shutil.which('pwsh') or shutil.which('powershell')
        if not executable:
            raise RuntimeError('No verified Windows HTTPS fallback is available.') from None
        env = dict(os.environ, PM25_CROSSCHECK_URL=requests.Request('GET', endpoint, params=params).prepare().url,
                   PM25_CROSSCHECK_PATH=str(path.resolve()))
        command = "$ErrorActionPreference='Stop'; Invoke-WebRequest -Uri $env:PM25_CROSSCHECK_URL -OutFile $env:PM25_CROSSCHECK_PATH -TimeoutSec 60 -UseBasicParsing"
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=env, capture_output=True, text=True, timeout=80)
        if result.returncode != 0:
            raise RuntimeError('Windows HTTPS request failed; certificate verification was not disabled.')
        metadata.update({'http_status': 200, 'transport': 'Windows native HTTPS; TLS verified',
                         'reason': 'Python CA bundle could not build the server certificate chain.'})
    metadata.update({'file': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size})
    return metadata


def station_crosscheck(root, mode='replay'):
    if mode not in ['replay', 'fresh']:
        raise ValueError('C6 mode must be replay or fresh.')
    snapshot = json.loads((root / 'snapshot.json').read_text(encoding='utf-8'))
    run_id = (snapshot['crosscheck_raw_run_id'] if mode == 'replay'
              else datetime.now(timezone.utc).strftime('crosscheck_%Y%m%dT%H%M%SZ'))
    folder = root / 'data/raw' / run_id
    if mode == 'fresh':
        folder.mkdir(parents=True, exist_ok=False)
    manifest = {'run_id': run_id, 'status': 'running', 'files': [],
                'purpose': 'C6 only: contemporary comparison outside the historical modelling interval'}
    if mode == 'replay':
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['status'] != 'complete':
            raise ValueError('Incomplete C6 snapshot.')
        for item in manifest['files']:
            if sha256(folder / item['file']) != item['sha256']:
                raise ValueError('C6 source checksum mismatch.')
    else:
        write_json(folder / 'manifest.json', manifest)
    try:
        station_path = folder / 'air4thai_snapshot.json'
        if mode == 'fresh':
            manifest['files'].append(verified_download(STATION_ENDPOINT, {}, station_path, windows_fallback=True))
        snapshot = json.loads(station_path.read_text(encoding='utf-8-sig'))
        indexed = {str(s.get('stationID', '')).lower(): s for s in snapshot['stations']}
        rows = []
        # Primary 36t is closest to the original receptor. 35t is a declared spatial comparison.
        for station_id in ['36t', '35t']:
            if station_id not in indexed:
                continue
            station = indexed[station_id]
            latest = station['AQILast']
            measured = pd.to_numeric(latest.get('PM25', {}).get('value'), errors='coerce')
            if not np.isfinite(measured) or measured < 0:
                continue
            stamp = pd.Timestamp(latest['date'] + ' ' + latest['time'])
            latitude, longitude = float(station['lat']), float(station['long'])
            params = {'latitude': latitude, 'longitude': longitude, 'hourly': 'pm2_5',
                      'domains': 'cams_global', 'timezone': 'Asia/Bangkok',
                      'start_date': str((stamp.normalize() - pd.Timedelta(days=2)).date()),
                      'end_date': str(stamp.date())}
            aq_path = folder / f'cams_{station_id}_hourly.json'
            if mode == 'fresh':
                manifest['files'].append(verified_download(AQ_ENDPOINT, params, aq_path))
            aq = json.loads(aq_path.read_text(encoding='utf-8'))
            if aq.get('utc_offset_seconds') != 25200 or aq['hourly_units']['pm2_5'] not in ['μg/m³', 'µg/m³', 'ug/m3']:
                raise ValueError('Unexpected timezone or PM2.5 unit in the cross-check.')
            hours = pd.DataFrame(aq['hourly'])
            hours['time'] = pd.to_datetime(hours['time'])
            hours['pm2_5'] = pd.to_numeric(hours['pm2_5'], errors='raise')
            if hours['time'].duplicated().any():
                raise ValueError('Duplicate cross-check hours.')
            series = hours.set_index('time')['pm2_5']
            expected = pd.date_range(stamp - pd.Timedelta(hours=23), stamp, freq='h')
            window = series.reindex(expected)
            alternative = series.reindex(expected - pd.Timedelta(hours=1))
            if window.notna().sum() != 24 or alternative.notna().sum() != 24:
                raise ValueError('Cross-check requires 24 valid hours in both boundary conventions.')
            model = float(window.mean())
            rows.append({'station_id': station_id, 'primary': station_id == '36t', 'station_name': station.get('nameEN'),
                         'station_latitude': latitude, 'station_longitude': longitude,
                         'reported_at_local': stamp.isoformat(), 'timezone': 'Asia/Bangkok',
                         'unit': 'ug/m3', 'reference_pm25_rolling24h': float(measured),
                         'cams_pm25_mean24_samples': model, 'signed_difference_cams_minus_station': model - measured,
                         'absolute_difference': abs(model - measured),
                         'cams_one_hour_earlier_window_mean': float(alternative.mean()),
                         'difference_with_earlier_boundary': float(alternative.mean() - measured),
                         'matched_hour_count': 24, 'cams_grid_latitude': aq.get('latitude'),
                         'cams_grid_longitude': aq.get('longitude'), 'model_window_first_sample': expected[0].isoformat(),
                         'model_window_last_sample': expected[-1].isoformat()})
            exports = root / 'data/interim/source_exports' / run_id
            exports.mkdir(parents=True, exist_ok=True)
            series.rename('cams_pm25_ug_m3').to_csv(exports / f'cams_{station_id}_hourly_derived.csv')
        if not rows:
            raise ValueError('No valid Chiang Mai station PM2.5 reference is available.')
        result = {'status': 'COMPLETED_POINT_COMPARISON_WITH_PERIOD_BOUNDARY_LIMITATION', 'raw_run_id': run_id,
                  'period_definition_source': PERIOD_SOURCE,
                  'period_definition': 'Air4Thai PM2.5 is a rolling 24-hour concentration updated hourly; not the AQI number.',
                  'matching': 'Same station coordinates, units and nominal reporting time; mean of 24 hourly CAMS samples ending at the station timestamp.',
                  'boundary_uncertainty': 'Exact station hourly-bin inclusion is not specified by the snapshot. Also report the one-hour-earlier window; not an exact replicated instrument aggregation.',
                  'reference_priority': 'Subject to station QA, the ground monitor is the local empirical reference; CAMS is a coarse-grid model product.',
                  'conclusion_limit': 'One contemporary comparison cannot establish historical CAMS accuracy, station-level forecast skill, or operational forecasting readiness. It is excluded from model fitting.',
                  'stations': rows}
        manifest['status'] = 'complete'
        if mode == 'fresh':
            write_json(folder / 'manifest.json', manifest)
        write_json(root / 'outputs/results/station_crosscheck.json', result)
        pd.DataFrame(rows).to_csv(root / 'outputs/results/station_crosscheck.csv', index=False)
        spatial_evidence(root, folder, result)
        print(pd.DataFrame(rows)[['station_id', 'reported_at_local', 'reference_pm25_rolling24h',
                                  'cams_pm25_mean24_samples', 'signed_difference_cams_minus_station']].to_string(index=False))
        return result
    except Exception:
        if mode == 'fresh':
            manifest['status'] = 'failed'
            write_json(folder / 'manifest.json', manifest)
        raise


def spatial_evidence(root, folder, c6):
    required=[folder/'cams_36t_hourly.json',folder/'cams_35t_hourly.json']
    valid={row['station_id'] for row in c6['stations']}
    if not {'36t','35t'}.issubset(valid) or not all(path.is_file() for path in required):
        evidence={'status':'NOT_EVALUATED_TWO_VALID_COORDINATE_SERIES_UNAVAILABLE',
            'valid_station_ids':sorted(valid),'C4_conclusion':'One-receptor study; no spatial contrast is claimed. The valid C6 point comparison is retained.'}
        write_json(root/'outputs/results/station_coordinate_grid_audit.json',evidence)
        write_json(root/'outputs/results/spatial_resolution_audit.json',evidence)
        return evidence
    left = json.loads((folder/'cams_36t_hourly.json').read_text(encoding='utf-8'))
    right = json.loads((folder/'cams_35t_hourly.json').read_text(encoding='utf-8'))
    values_a=np.asarray(left['hourly']['pm2_5'],dtype=float)
    values_b=np.asarray(right['hourly']['pm2_5'],dtype=float)
    aligned=left['hourly']['time']==right['hourly']['time']
    identical=bool(aligned and np.array_equal(values_a,values_b,equal_nan=True))
    evidence={'status':'COMPLETED','requested_stations':['36t','35t'],'returned_grid_36t':[left['latitude'],left['longitude']],
        'returned_grid_35t':[right['latitude'],right['longitude']],
        'hourly_time_axes_equal':aligned,
        'hourly_values_identical':identical,
        'hours_compared':len(values_a) if aligned else 0,'maximum_absolute_grid_difference':float(np.nanmax(np.abs(values_a-values_b))) if aligned else None,
        'measured_station_values':[s['reference_pm25_rolling24h'] for s in c6['stations']],
        'C4_conclusion':('The main study has one receptor. Both station-coordinate requests return identical CAMS series; no spatial contrast is justified.' if identical else
            'The main study has one receptor. These diagnostic requests do not establish province-wide spatial representativeness; inspect time alignment and returned grids before any spatial comparison.')}
    write_json(root/'outputs/results/station_coordinate_grid_audit.json',evidence)
    write_json(root/'outputs/results/spatial_resolution_audit.json',evidence)
    return evidence
