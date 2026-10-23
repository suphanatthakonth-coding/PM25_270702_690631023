"""Question-led figures, annual coverage and complete same-test model comparisons."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from common import write_json


def savefig(root,fig,name,caption):
    fig.tight_layout();folder=root/'outputs/figures'
    fig.savefig(folder/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(folder/(name+'.pdf'),bbox_inches='tight')
    (folder/(name+'_caption.txt')).write_text(caption,encoding='utf-8');plt.close(fig)


def describe(root,cfg,daily):
    selected=daily[daily.date.between(cfg['start_date'],cfg['end_date'])].copy()
    selected['year']=selected.date.dt.year;selected['month']=selected.date.dt.month
    annual=selected.groupby('year').agg(valid_days=('pm25_mean','count'),mean=('pm25_mean','mean'),maximum=('pm25_mean','max'),exceed_days=('pm25_mean',lambda x:int(x.gt(cfg['warning_threshold']).sum())))
    annual['exceed_percent']=100*annual.exceed_days/annual.valid_days
    annual.to_csv(root/'outputs/results/annual_summary.csv')
    monthly=selected.groupby('month').pm25_mean.agg(['mean','count','min','max']);monthly.to_csv(root/'outputs/results/monthly_summary.csv')
    fig,ax=plt.subplots(figsize=(10,3.5));ax.plot(selected.date,selected.pm25_mean,lw=.8,label='Fixed-vintage CAMS daily profile')
    ax.axhline(cfg['warning_threshold'],ls='--',color='firebrick',label='Fixed lab threshold37.5')
    ax.axvspan(pd.Timestamp('2024-08-09'),pd.Timestamp('2024-08-16'),alpha=.15,color='orange',label='Source-advisory date window')
    ax.set(xlabel='Thailand local profile day',ylabel='PM2.5 (ug/m3)',title='Daily modeled PM2.5 at the fixed Chiang Mai ADS grid');ax.legend(fontsize=8)
    savefig(root,fig,'01_daily_pm25','CAMS profiles at one grid point, not station observations. Shading marks a provider-advisory date range, not verified local contamination.')
    fig,axes=plt.subplots(1,2,figsize=(10,3.5));axes[0].bar(annual.index.astype(str),annual.exceed_days)
    axes[0].set(xlabel='Full calendar year',ylabel='Modeled exceedance days',title='Full-year counts;2024 is leap year')
    for i,(_,r) in enumerate(annual.iterrows()):axes[0].text(i,r.exceed_days+1,f'n={int(r.valid_days)}',ha='center',fontsize=8)
    axes[1].plot(monthly.index,monthly['mean'],marker='o');axes[1].set(xlabel='Calendar month',ylabel='Mean modeled PM2.5 (ug/m3)',xticks=range(1,13),title='Pooled2024-2025 monthly means')
    savefig(root,fig,'02_exceedances_seasonality','Full-calendar modeled profiles; leap-year denominators are shown. Two years and evolving CAMS cycles do not establish a secular pollution trend.')
    fire=pd.read_csv(root/'data/interim/gfas_daily_derived.csv',parse_dates=['fire_source_day_utc'])
    fire=fire[fire.fire_source_day_utc.between(cfg['start_date'],cfg['end_date'])]
    fig,axes=plt.subplots(2,1,figsize=(10,4.8),sharex=True)
    axes[0].plot(fire.fire_source_day_utc,fire.fire_power_mw,lw=.7,color='#a34f17')
    axes[0].set(ylabel='Mean FRP power (MW)',title='GFAS UTC-day analysis: native zeros are not project-filled missing values')
    axes[1].plot(fire.fire_source_day_utc,fire.fire_observation_area_fraction,lw=.7,color='#376f8b')
    axes[1].set(xlabel='UTC averaging start day',ylabel='Area with observation opportunity',ylim=(-.03,1.03))
    savefig(root,fig,'03_fire_quality','Area-integrated daily-mean FRP and observation-opportunity area are separate. The latter is a QC fraction of cells with offire>0, not the raw offire value, which may exceed1. Neither series proves true absence of fires.')
    pm_grid=pd.read_csv(root/'data/interim/native_exports/pm_hourly.csv',usecols=['latitude','longitude']).drop_duplicates()
    if len(pm_grid)!=1:raise ValueError('Expected one native PM receptor grid.')
    weather_audit=json.loads((root/'outputs/results/weather_raw_audit.json').read_text())
    grids=[row['response_grid'] for row in weather_audit['sources']]
    if not grids or any(grid!=grids[0] for grid in grids):raise ValueError('Weather grid identity changes across captured years.')
    spatial={'status':'ONE_RECEPTOR_RETAINED','requested_receptor':{'latitude':cfg['latitude'],'longitude':cfg['longitude']},
        'PM_native_ADS_point':{'latitude':float(pm_grid.iloc[0].latitude),'longitude':float(pm_grid.iloc[0].longitude),'grid_degrees':.4},
        'weather_response_grid':grids[0],
        'station_coordinate_comparison':json.loads((root/'outputs/results/station_coordinate_grid_audit.json').read_text()),
        'fire_region':{'west':97.0,'south':17.5,'east':101.0,'north':21.0,'native_grid_degrees':.1},
        'C4':'One receptor; no invented second independent site. Weather and regional fire source locations are not extra PM study receptors.',
        'C6':'Separate preserved contemporary station comparison; not a historical multi-station accuracy study.'}
    write_json(root/'outputs/results/spatial_resolution_audit.json',spatial)
    return annual,monthly


def model_figures(root,cfg,scores):
    test=scores.loc[scores.partition.eq('test')&scores.family.eq(cfg['primary_family'])]
    matrix=test.pivot(index='hypothesis',columns='window',values='MAE').reindex(['H1','H2','H3','H4'])
    fig,ax=plt.subplots(figsize=(7,3.8));im=ax.imshow(matrix.to_numpy(),cmap='viridis_r',aspect='auto')
    for r in range(4):
        for c in range(3):ax.text(c,r,f'{matrix.iloc[r,c]:.3f}',ha='center',va='center',color='black',bbox={'facecolor':'white','alpha':.7,'edgecolor':'none'})
    ax.set(xticks=range(3),xticklabels=matrix.columns,yticks=range(4),yticklabels=['H1 PM','H2 PM+weather','H3 PM+fire','H4 PM+weather+fire'],
        xlabel='Historical window (days)',ylabel='Source group',title='Primary '+cfg['primary_family']+': twelve settings on identical test days')
    fig.colorbar(im,ax=ax,label='MAE (ug/m3)')
    savefig(root,fig,'04_twelve_settings','All twelve Ridge settings use exactly the same quality-screened test dates. MAE is primary; the validation-selected candidate remains fixed regardless of this test ranking.')
    selected=json.loads((root/'outputs/results/selection.json').read_text())['experiment']
    chosen=test.loc[test.experiment.eq(selected)].iloc[0]
    baseline=scores.loc[scores.partition.eq('test')&scores.experiment.eq('B0_persistence')].iloc[0]
    fig,ax=plt.subplots(figsize=(7,3.5));positions=np.arange(2)
    ax.bar(positions-.18,[baseline.FP,chosen.FP],width=.36,label='False alerts (FP)')
    ax.bar(positions+.18,[baseline.FN,chosen.FN],width=.36,label='Missed exceedances (FN)')
    ax.set(xticks=positions,xticklabels=['Persistence',selected+' (validation selected)'],ylabel='Test days (count)',title='Warning errors at the same 37.5 threshold');ax.legend()
    savefig(root,fig,'05_warning_errors','Primary warning decisions use >37.5 for every regression prediction. Reduced MAE does not guarantee fewer missed exceedance days. Thresholds are not tuned to the test set.')
    return matrix


if __name__=='__main__':
    from common import load_config
    from workflow import load_prepared
    root,cfg=load_config();daily=load_prepared(root,cfg)
    describe(root,cfg,daily)
