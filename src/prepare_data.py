"""Source-specific daily construction: no target fill and no false-zero conversion."""
import json,math
import numpy as np
import pandas as pd
import eccodes as ec
from common import load_config,selected_raw_run,write_json,sha256

PM={'pm25_mean':('ug/m3','Fixed-vintage mean of 24 instantaneous CAMS hourly values.'),
    'pm25_min':('ug/m3','Minimum of the same admitted daily forecast profile.'),
    'pm25_max':('ug/m3','Maximum of the same admitted daily forecast profile.')}
WEATHER={'temperature_mean':('deg C','Mean 2 m temperature from GFS previous_day1 forecast history.'),
    'humidity_mean':('%','Mean 2 m relative humidity; association rather than causal evidence.'),
    'pressure_mean':('hPa','Mean forecast surface pressure.'),
    'wind_speed_ms':('m/s','Arithmetic mean hourly 10 m wind speed.'),
    'wind_u_ms':('m/s','Mean eastward component derived before aggregation.'),
    'wind_v_ms':('m/s','Mean northward component derived before aggregation.'),
    'precipitation_sum':('mm/day','Sum of preceding-hour intervals assigned to interval-start local day.')}
FIRE={'log_fire_power_mw':('log1p(MW-valued index)','Log1p of area-integrated daily-mean GFAS FRP power; not energy/emissions.'),
    'fire_positive_area_fraction':('fraction of bounding-box grid area','Area fraction with strictly positive GFAS analysis density; not hotspots or burnt area.')}

AUDIT_FIELDS={
    'date':('local date','History anchor D-1; calendar join key, not a predictor.'),
    'pm25_valid_hours':('hourly values (count)','Number of valid PM samples; 24 required.'),
    'rain_valid_hours':('hourly values (count)','Valid precipitation intervals in the local day; 24 required.'),
    'weather_min_valid_hours':('hourly values (count)','Minimum valid count across hourly weather fields.'),
    'fire_power_mw':('MW','Area-integrated daily mean FRP power before log1p; not energy or emissions.'),
    'fire_observation_area_fraction':('dimensionless fraction','Area fraction with native offire > 0; observation-opportunity QC, not burnt area.'),
    'fire_opportunity_weighted_mean':('dimensionless index','Area-weighted native offire QC; values above 1 are retained.'),
    'fire_zero_grid_cells':('grid cells (count)','Number of cells with zero native FRP analysis.'),
    'fire_missing_grid_cells':('grid cells (count)','Number of missing native fire cells; missing fields are rejected.'),
    'fire_project_fill_applied':('boolean','Whether the project filled fire values; false in this study.'),
    'fire_source_day_utc':('UTC date','Start date of the GFAS UTC daily averaging interval.'),
    'target_date':('local date','Forecast verification day D+1; not a predictor.'),
    'issue_date':('local date','Issue day D; issue time is 07:00 Thailand.'),
    'forecast_origin_utc':('UTC timestamp','Timezone-aware forecast issue instant.'),
    'target_complete_utc':('UTC timestamp','End of the target local day; used to check label maturity.'),
    'pm25_tomorrow':('ug/m3','Target P(D+1); history anchor+2; never a feature.'),
    'exceed_tomorrow':('binary 0/1','Derived target: PM > 37.5; unknown PM retains a missing label.'),
    'provider_forecast':('ug/m3','Direct CAMS baseline B1 for the target day; never a learned feature.'),
    'source_advisory_dependency':('boolean','Target or history intersects the prespecified advisory dependency mask.'),
    'in_study_target_calendar':('boolean','Target date falls within the declared study period.'),
    'outer_label_purge':('boolean','Boundary target excluded because its label is not mature at the next phase.')}

def prepare_weather(folder):
    receipts=json.loads((folder/'weather/transfer_manifest.json').read_text())
    parts=[];invalid=[]
    names=['temperature_2m','relative_humidity_2m','surface_pressure','wind_speed_10m','wind_direction_10m','precipitation']
    units=['°C','%','hPa','m/s','°','mm']
    for receipt in receipts:
        path=folder/'weather'/receipt['file']
        if sha256(path)!=receipt['sha256']:raise ValueError('Weather raw changed.')
        payload=json.loads(path.read_text(encoding='utf-8'))
        if payload['utc_offset_seconds']!=0 or any(payload['hourly_units'][n+'_previous_day1']!=u for n,u in zip(names,units)):
            raise ValueError('Weather native timezone/unit mismatch.')
        frame=pd.DataFrame(payload['hourly']);frame.index=pd.to_datetime(frame.pop('time'),utc=True)
        frame=frame.rename(columns={n+'_previous_day1':n for n in names})[names].apply(pd.to_numeric,errors='raise')
        parts.append(frame)
    met=pd.concat(parts).sort_index()
    if met.index.has_duplicates:raise ValueError('Duplicate weather timestamps.')
    for name in names:
        values=met[name]
        bad=values.notna()&~np.isfinite(values)
        if name=='relative_humidity_2m':bad|=values.notna()&~values.between(0,100)
        if name=='wind_direction_10m':bad|=values.notna()&~values.between(0,360)
        if name in ['wind_speed_10m','precipitation']:bad|=values.lt(0)
        if name=='surface_pressure':bad|=values.le(0)
        invalid.append({'source':'weather','field':name,'invalid_hours':int(bad.sum()),'action':'invalidate value; never interpolate or zero-fill'})
        met.loc[bad,name]=np.nan
    met.index=met.index.tz_convert('Asia/Bangkok').tz_localize(None)
    theta=np.deg2rad(met.wind_direction_10m)
    met=met.assign(wind_speed_ms=met.wind_speed_10m,wind_u_ms=-met.wind_speed_10m*np.sin(theta),wind_v_ms=-met.wind_speed_10m*np.cos(theta))
    rename={'temperature_2m':'temperature_mean','relative_humidity_2m':'humidity_mean','surface_pressure':'pressure_mean',
        'wind_speed_ms':'wind_speed_ms','wind_u_ms':'wind_u_ms','wind_v_ms':'wind_v_ms'}
    counts=met[list(rename)].groupby(met.index.normalize()).count().rename(columns=rename)
    daily=met[list(rename)].groupby(met.index.normalize()).mean().rename(columns=rename).where(counts.eq(24))
    rain_day=(met.index-pd.Timedelta(hours=1)).normalize()
    daily['precipitation_sum']=met.precipitation.groupby(rain_day).sum(min_count=24)
    daily['rain_valid_hours']=met.precipitation.groupby(rain_day).count()
    daily['weather_min_valid_hours']=counts.min(axis=1)
    return daily,invalid,met

def prepare_fire(root,cfg,folder):
    parts=[];area_reference=None
    for path in sorted((folder/'ads/jobs').glob('gfas_*/raw.grib')):
        messages={}
        with path.open('rb') as stream:
            while True:
                handle=ec.codes_grib_new_from_file(stream)
                if handle is None:break
                try:
                    day=str(ec.codes_get(handle,'dataDate'));param=int(ec.codes_get(handle,'paramId'))
                    values=np.asarray(ec.codes_get_values(handle),dtype=float)
                    lat=np.asarray(ec.codes_get_array(handle,'latitudes'),dtype=float)
                    lon=np.asarray(ec.codes_get_array(handle,'longitudes'),dtype=float)
                    key=(day,param)
                    if key in messages:raise ValueError('Duplicate GFAS field.')
                    if ec.codes_get(handle,'numberOfMissing') or not np.isfinite(values).all():raise ValueError('GFAS missing values require a new documented eligibility decision; never sum them as zero.')
                    messages[key]=(values,lat,lon)
                finally:ec.codes_release(handle)
        for day in sorted({key[0] for key in messages}):
            power,lat,lon=messages[(day,210099)];opportunity,lat2,lon2=messages[(day,210097)]
            np.testing.assert_array_equal(lat,lat2);np.testing.assert_array_equal(lon,lon2)
            half=.05
            area=cfg['earth_radius_m']**2*np.deg2rad(.1)*(np.sin(np.deg2rad(lat+half))-np.sin(np.deg2rad(lat-half)))
            if area_reference is None:area_reference=area
            else:np.testing.assert_array_equal(area_reference,area)
            total_area=float(math.fsum(area));power_mw=float(math.fsum(power*area)/1e6)
            positive_fraction=float(math.fsum(area[power>0])/total_area)
            if (power<0).any() or (opportunity<0).any():raise ValueError('Negative GFAS native values.')
            parts.append({'fire_source_day_utc':pd.Timestamp(day),'fire_power_mw':power_mw,
                'log_fire_power_mw':float(np.log1p(power_mw)),'fire_positive_area_fraction':positive_fraction,
                'fire_observation_area_fraction':float(math.fsum(area[opportunity>0])/total_area),
                'fire_opportunity_weighted_mean':float(math.fsum(area*opportunity)/total_area),
                'fire_zero_grid_cells':int((power==0).sum()),'fire_missing_grid_cells':0,'fire_project_fill_applied':False})
    frame=pd.DataFrame(parts).set_index('fire_source_day_utc').sort_index()
    if frame.index.has_duplicates:raise ValueError('GFAS daily identity duplicated across chunks.')
    frame.to_csv(root/'data/interim/gfas_daily_derived.csv')
    write_json(root/'outputs/results/fire_area_aggregation.json',{'earth_radius_m':cfg['earth_radius_m'],'cell_width_degrees':.1,
        'total_bbox_area_m2':float(math.fsum(area_reference)),'cells':len(area_reference),
        'formula':'A=R^2*dlambda*(sin(phi+0.05deg)-sin(phi-0.05deg)); mean_power_MW=sum(FRP_Wm2*A)/1e6.',
        'positive_area':'sum(A where native analysis density > 0)/sum(A); not burnt-area fraction or hotspot count.',
        'offire':'Quality evidence only; >1 preserved, not clipped and not a predictor.',
        'source_processing':'GFAS assimilation may carry information through observation gaps; no project imputation.',
        'daily_fields':len(frame),'source_offset':'For issue D, latest UTC-mean start day D-2.'})
    return frame

def prepare_daily(root,cfg):
    folder,manifest=selected_raw_run(root)
    proof=json.loads((root/'outputs/results/raw_decode_audit.json').read_text())
    for name,digest in proof['exports'].items():
        if sha256(root/name)!=digest:raise ValueError('Native exports changed; rerun fetch stage.')
    profiles=pd.read_csv(root/'data/interim/native_exports/pm_profiles.csv',float_precision='round_trip')
    fixed=profiles[profiles.role.eq('fixed_vintage_profile')].copy();fixed.index=pd.to_datetime(fixed.local_day)
    if fixed.index.has_duplicates or not fixed.complete_24h.all():raise ValueError('PM profiles incomplete or duplicate.')
    pm=fixed[['mean_ug_m3','minimum_ug_m3','maximum_ug_m3']].rename(columns=dict(zip(['mean_ug_m3','minimum_ug_m3','maximum_ug_m3'],PM)))
    pm['pm25_valid_hours']=24
    weather,invalid,met=prepare_weather(folder)
    fire=prepare_fire(root,cfg,folder)
    calendar=pd.date_range(cfg['history_calendar_start'],cfg['history_calendar_end'],freq='D',name='date')
    daily=pd.DataFrame(index=calendar).join(pm,validate='one_to_one').join(weather,validate='one_to_one')
    fire_aligned=fire.reindex(calendar-pd.Timedelta(days=1));fire_aligned.index=calendar
    daily=daily.join(fire_aligned,validate='one_to_one')
    daily['fire_source_day_utc']=calendar-pd.Timedelta(days=1)
    daily['target_date']=calendar+pd.Timedelta(days=2)
    daily['issue_date']=calendar+pd.Timedelta(days=1)
    daily['forecast_origin_utc']=pd.DatetimeIndex(daily.issue_date).tz_localize(cfg['timezone']).tz_convert('UTC')+pd.Timedelta(hours=7)
    daily['target_complete_utc']=pd.DatetimeIndex(daily.target_date+pd.Timedelta(days=1)).tz_localize(cfg['timezone']).tz_convert('UTC')
    daily['pm25_tomorrow']=daily.pm25_mean.shift(-2)
    daily['exceed_tomorrow']=daily.pm25_tomorrow.gt(cfg['warning_threshold']).astype('Int64')
    daily.loc[daily.pm25_tomorrow.isna(),'exceed_tomorrow']=pd.NA
    provider=profiles[profiles.role.eq('provider_forecast_reference')].set_index('local_day')
    daily['provider_forecast']=provider.mean_ug_m3.reindex(daily.target_date.dt.strftime('%Y-%m-%d')).to_numpy()
    first,last=pd.Timestamp(cfg['advisory_start_utc_day']),pd.Timestamp(cfg['advisory_end_utc_day'])
    # PM profile valid UTC dates are local date-1 and local date; GFAS dates are their UTC averaging start.
    native_pm_flag=pd.Series(calendar.to_series().between(first,last).to_numpy()|(calendar-pd.Timedelta(days=1)).to_series().between(first,last).to_numpy(),index=calendar)
    native_fire_flag=daily.fire_source_day_utc.between(first,last)
    target_pm_flag=daily.target_date.between(first,last)|(daily.target_date-pd.Timedelta(days=1)).between(first,last)
    history_flag=native_pm_flag.rolling(7,min_periods=7).max().fillna(0).astype(bool)|native_fire_flag.rolling(7,min_periods=7).max().fillna(0).astype(bool)
    daily['source_advisory_dependency']=history_flag|target_pm_flag
    # fillna above initializes an audit flag before a complete window; it never fills a predictor or target.
    daily['in_study_target_calendar']=daily.target_date.between(cfg['start_date'],cfg['end_date'])
    daily['outer_label_purge']=daily.target_date.isin(pd.to_datetime(cfg['outer_label_purge_target_days']))
    result=daily.reset_index()
    result.to_csv(root/'data/processed/final_dataset_daily.csv',index=False)
    pd.DataFrame(invalid).to_csv(root/'outputs/results/invalid_values.csv',index=False)
    missing=pd.DataFrame({'column':result.columns,'missing_rows':result.isna().sum().to_numpy(),'total_rows':len(result),
        'missing_percent':result.isna().mean().to_numpy()*100})
    missing.to_csv(root/'outputs/results/missingness.csv',index=False)
    decisions=[];dictionary=[]
    for row in missing.itertuples():
        column=row.column
        if column in PM|WEATHER|FIRE:
            action='No imputation; preserve missing and require complete calendar windows.'
            reason='Avoid invented history or target-dependent eligibility. Native GFAS zeros are retained, not filled.'
        elif column in ['pm25_tomorrow','exceed_tomorrow']:
            action='No target fill; require the exact next-day-after-issue profile.';reason='Unknown outcomes cannot become safe labels.'
        elif column=='provider_forecast':
            action='Retain baseline; no imputation; require a present reference on common dates.';reason='Compare every baseline and setting on identical dates; never use B1 as a learned feature.'
        else:action='Retain audit identity/QC; exclude it from learned features.';reason=AUDIT_FIELDS[column][1]
        decisions.append({'column':column,'missing_rows':row.missing_rows,'missing_percent':row.missing_percent,'action':action,'reason':reason})
        unit,purpose=(PM|WEATHER|FIRE|AUDIT_FIELDS)[column]
        dictionary.append({'column':column,'unit':unit,'purpose':purpose,'used_as_daily_predictor':column in PM|WEATHER|FIRE})
    pd.DataFrame(decisions).to_csv(root/'outputs/results/missing_decisions.csv',index=False)
    pd.DataFrame(dictionary).to_csv(root/'outputs/results/data_dictionary.csv',index=False)
    flow={'pm_native_runs':len(profiles)//2,'PM_profiles':len(fixed),'GFAS_utc_days':len(fire),'weather_raw_hours':len(met),
        'daily_rows_before_join':len(calendar),'daily_rows_after_join':len(result),'study_target_calendar_days':int(result.in_study_target_calendar.sum()),
        'joins':'Unique calendar keys; PM/weather on local day; GFAS UTC day is local history anchor minus1.',
        'target_shift_calendar_days_from_anchor':2,'project_predictor_fill_count':0,'project_target_fill_count':0,
        'source_advisory_policy':cfg['advisory_policy'],'outer_purge_target_days':cfg['outer_label_purge_target_days']}
    write_json(root/'outputs/results/join_audit.json',flow)
    examples=result.iloc[[0,36,-3]][['date','issue_date','forecast_origin_utc','fire_source_day_utc','target_date','target_complete_utc']]
    examples.to_csv(root/'outputs/results/timezone_examples.csv',index=False)
    rain=pd.DataFrame({'correct_rain_total':weather.precipitation_sum,'incorrect_timestamp_day_mean':met.precipitation.groupby(met.index.normalize()).mean()})
    rain.to_csv(root/'outputs/results/rain_interval_audit.csv')
    write_json(root/'data/processed/dataset_metadata.json',{'raw_run_id':manifest['run_id'],
        'dataset_sha256':sha256(root/'data/processed/final_dataset_daily.csv'),'config_sha256':sha256(root/'config.json'),
        'target_kind':'CAMS fixed-vintage modeled output','publication_availability':'Nominal release schedule only; actual historical release unverified.'})
    return result,flow

def build_experiments(root,cfg,daily):
    indexed=daily.set_index('date');values={};dictionary=[]
    for name,(unit,purpose) in (PM|WEATHER|FIRE).items():
        group='PM' if name in PM else 'weather' if name in WEATHER else 'fire'
        for lag in range(7):
            feature=f'{name}_lag{lag}';values[feature]=indexed[name].shift(lag)
            dictionary.append({'feature':feature,'source_group':group,'daily_field':name,'lag_days':lag,'unit':unit,'purpose':purpose,
                'time_rule':f'Issue D07 Thai: source day D-{lag+2 if group=="fire" else lag+1}; fire days UTC, others local.',
                'publication_status':'Nominal schedule constrained; actual historical public release not certified.'})
    X=pd.DataFrame(values,index=indexed.index);table=pd.DataFrame(dictionary)
    table.to_csv(root/'outputs/results/feature_manifest.csv',index=False)
    specs=[]
    for group,sources in [('H1',['PM']),('H2',['PM','weather']),('H3',['PM','fire']),('H4',['PM','weather','fire'])]:
        for window in [3,5,7]:
            columns=table.loc[table.source_group.isin(sources)&table.lag_days.lt(window),'feature'].tolist()
            specs.append({'id':f'{group}_{window}d','hypothesis':group,'window':window,'sources':sources,'features':columns,'feature_count':len(columns)})
    complete=X.notna().all(axis=1)&indexed.pm25_tomorrow.notna()&indexed.provider_forecast.notna()
    eligible=complete&indexed.in_study_target_calendar&~indexed.source_advisory_dependency&~indexed.outer_label_purge
    ledger=pd.DataFrame(index=indexed.index,data={'target_date':indexed.target_date,'first_window_complete':np.arange(len(indexed))>=6,
        'in_study_target_calendar':indexed.in_study_target_calendar,'all_input_values_present':X.notna().all(axis=1),
        'target_present':indexed.pm25_tomorrow.notna(),'provider_reference_present':indexed.provider_forecast.notna(),
        'values_complete':complete,'source_advisory_dependency':indexed.source_advisory_dependency,
        'outer_label_purge':indexed.outer_label_purge,'eligible_common':eligible})
    ledger['first_failure']=np.select([~ledger.in_study_target_calendar,~ledger.first_window_complete,~ledger.target_present,
        ~ledger.all_input_values_present,~ledger.provider_reference_present,ledger.source_advisory_dependency,ledger.outer_label_purge],
        ['outside_target_study_calendar','seven_day_history_warmup','target_missing','invalid_or_missing_input_history','provider_reference_missing',
         'conservative_source_advisory_dependency','outer_label_maturity_purge'],default='retained_common')
    ledger.to_csv(root/'outputs/results/row_inclusion.csv')
    ledger[ledger.in_study_target_calendar].first_failure.value_counts().rename_axis('status').reset_index(name='rows').to_csv(root/'outputs/results/cohort_ledger.csv',index=False)
    X.reset_index().to_csv(root/'data/processed/all_seven_day_features.csv',index=False)
    write_json(root/'outputs/results/experiment_specs.json',specs)
    if len(specs)!=12 or eligible.sum()<500:raise ValueError('Twelve settings and500+ common rows required.')
    write_json(root/'outputs/results/cohort_contract.json',{'value_complete_study_days':int((complete&indexed.in_study_target_calendar).sum()),
        'after_advisory_quarantine':int((complete&indexed.in_study_target_calendar&~indexed.source_advisory_dependency).sum()),
        'common_after_outer_label_purges':int(eligible.sum()),'advisory_excluded_target_dates':indexed.loc[complete&indexed.in_study_target_calendar&indexed.source_advisory_dependency,'target_date'].astype(str).tolist(),
        'outer_label_purge_target_days':cfg['outer_label_purge_target_days'],'availability_scope':cfg['source_availability_scope']})
    return X,specs,eligible

if __name__=='__main__':
    root,cfg=load_config();daily,_=prepare_daily(root,cfg);X,specs,eligible=build_experiments(root,cfg,daily)
    from stages import prepare_handoff
    print(prepare_handoff(root,cfg,daily,X,specs,eligible))
