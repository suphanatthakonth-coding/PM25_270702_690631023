"""Concise lab report, full notebook listing and grey code cells with Thai comments."""
from pathlib import Path
import ast,html,json,re,tokenize,io
import numpy as np
import pandas as pd
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
from common import write_json,sha256


class ContinuedCodeTable(Table):
    """Mark repeated code headers without changing the authentic source listing."""
    def split(self,availWidth,availHeight):
        parts=super().split(availWidth,availHeight)
        for part in parts[1:]:
            original=part._cellvalues[0][0]
            if isinstance(original,(list,tuple)):original=original[0]
            text=original.getPlainText()
            if '(continued)' not in text:
                part._cellvalues[0]=[Paragraph(html.escape(text+' (continued)'),original.style)]
        return parts


def build_report(root,cfg):
    def J(name):return json.loads((root/'outputs/results'/name).read_text(encoding='utf-8'))
    def C(name):return pd.read_csv(root/'outputs/results'/name,float_precision='round_trip')
    profile=json.loads((root/'student_profile.json').read_text(encoding='utf-8'))
    daily=pd.read_csv(root/'data/processed/final_dataset_daily.csv',parse_dates=['date','target_date'])
    scores=C('model_scores.csv');pairs=C('paired_comparisons.csv');features=C('feature_manifest.csv')
    missing=C('missingness.csv');chronology=C('chronology.csv');coverage=J('coverage_summary.json')
    diagnostic=J('diagnostic_summary.json');selection=J('selection.json');c6_rows=C('station_crosscheck.csv')
    primary=scores[(scores.partition=='test')&(scores.family==cfg['primary_family'])].set_index('experiment')
    baseline=scores[(scores.partition=='test')&(scores.experiment=='B0_persistence')].iloc[0]
    provider=scores[(scores.partition=='test')&(scores.experiment=='B1_provider_forecast')].iloc[0]
    chosen=primary.loc[selection['experiment']];contrasts=pairs[pairs.family==cfg['primary_family']]
    threshold=cfg['warning_threshold'];reduction=100*(baseline.MAE-chosen.MAE)/baseline.MAE
    provider_change=100*(provider.MAE-chosen.MAE)/provider.MAE
    annual=C('annual_summary.csv').set_index('year')
    def supported_windows(label):
        rows=contrasts[(contrasts.comparison==label)&(contrasts.ci_high<0)]
        return '/'.join(str(int(v)) for v in rows.window) or 'none'
    incremental_conclusion='Incremental answers (pointwise intervals): H1 beats persistence with an interval below 0 at k='+supported_windows('H1-B0')+'. Weather beyond PM is supported at k='+supported_windows('H2-H1')+'; fire beyond PM at k='+supported_windows('H3-H1')+'. Fire conditional on weather: k='+supported_windows('H4-H2')+'; weather conditional on fire: k='+supported_windows('H4-H3')+'. These are exploratory associations, not causal or familywise-confirmed effects.'
    old_scores=pd.read_csv(root/'reference/initial_benchmark/model_scores.csv',float_precision='round_trip')
    old_selection=json.loads((root/'reference/initial_benchmark/selection.json').read_text(encoding='utf-8'))
    old_chosen=old_scores[(old_scores.partition=='test')&(old_scores.family=='ridge')&(old_scores.experiment==old_selection['experiment'])].iloc[0]
    old_base=old_scores[(old_scores.partition=='test')&(old_scores.experiment=='B0_persistence')].iloc[0]
    comparison=pd.DataFrame([{'stage':'Initial benchmark','issue':'00 Thai at target-day start','test_days':int(old_chosen.n),'selected':old_selection['experiment'],'model_MAE':old_chosen.MAE,'own_persistence_MAE':old_base.MAE,'skill_percent_vs_own_persistence':100*(old_base.MAE-old_chosen.MAE)/old_base.MAE},
        {'stage':'Current study','issue':'07 Thai before next target day','test_days':int(chosen.n),'selected':selection['experiment'],'model_MAE':chosen.MAE,'own_persistence_MAE':baseline.MAE,'skill_percent_vs_own_persistence':reduction}])
    comparison['comparison_limit']='Different target vintage, horizon, sources, calendar and cohort; not an algorithm-only improvement estimate.'
    comparison.to_csv(root/'outputs/results/model_development_comparison.csv',index=False)
    font_path=Path('C:/Windows/Fonts')
    if (font_path/'arial.ttf').is_file():
        pdfmetrics.registerFont(TTFont('LabBody',str(font_path/'arial.ttf')))
        pdfmetrics.registerFont(TTFont('LabBold',str(font_path/'arialbd.ttf')))
    else:
        import matplotlib
        fonts=Path(matplotlib.get_data_path())/'fonts/ttf'
        pdfmetrics.registerFont(TTFont('LabBody',str(fonts/'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('LabBold',str(fonts/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('LabThai',str(root/'report/fonts/NotoSansThai-Regular.ttf')))
    width=A4[0]-84;story=[];reading=[];cell_rows=[]
    styles={}
    for name,size,leading,font in [('body',9.4,12.5,'LabBody'),('small',8.0,10.4,'LabBody'),
        ('head',14.4,18,'LabBold'),('sub',11.1,14,'LabBold'),('title',20,24,'LabBold'),
        ('cell',8.0,10.1,'LabBody'),('tiny',7.0,8.9,'LabBody'),('code',7.5,11.5,'LabBody')]:
        styles[name]=ParagraphStyle(name,fontName=font,fontSize=size,leading=leading,
            spaceAfter=6 if name in ['body','small'] else 9 if name in ['head','title'] else 3)
    styles['sub'].keepWithNext=True
    styles['head'].keepWithNext=True
    def P(text,style='body'):
        story.append(Paragraph(html.escape(str(text)),styles[style]));reading.append(str(text)+'\n')
    def B(text):P('- '+str(text))
    def H(text,style='sub'):
        story.append(Paragraph(html.escape(text),styles[style]));reading.append('\n## '+text+'\n')
    def page(title):
        if story:story.append(PageBreak())
        H(title,'head')
    def T(headers,rows,widths=None,tiny=False):
        st=styles['tiny' if tiny else 'cell']
        values=[[Paragraph(html.escape(str(v)),st) for v in row] for row in [headers,*rows]]
        table=Table(values,colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7ecef')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f8f9')]),
            ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b8bec4')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),3 if tiny else 4),('BOTTOMPADDING',(0,0),(-1,-1),3 if tiny else 4)]))
        story.extend([table,Spacer(1,7)]);reading.append('| '+' | '.join(map(str,headers))+' |\n')
        reading.extend('| '+' | '.join(map(str,row))+' |\n' for row in rows)
    def F(name,caption,height):
        from PIL import Image as PILImage
        path=root/'outputs/figures'/name
        with PILImage.open(path) as im:w,h=im.size
        factor=min(width/w,height/h)
        story.append(Image(str(path),width=w*factor,height=h*factor,hAlign='CENTER'))
        P(caption,'small');reading.append('Figure: outputs/figures/'+name+'\n')
    def E(text):P('Evidence: '+text,'small')
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('LabBody',7)
        canvas.setFillColor(colors.HexColor('#56616a'))
        canvas.drawString(42,A4[1]-24,'PM2.5 forecasting | 270702 Data Science Programming')
        canvas.drawRightString(A4[0]-42,24,profile['student_id']+' | Page '+str(doc.page));canvas.restoreState()

    H('Chiang Mai PM2.5: prediction, evidence and decisions','title')
    P(profile['name']+' | Student ID: '+profile['student_id'])
    P('270702 Data Science Programming | '+profile['report_date']+' | Four notebooks, twelve settings','small')
    H('1 Problem background')
    B('Fine particulate pollution is associated with respiratory and cardiovascular disease; children are a particularly affected group [1]. A school needs lead time to review outdoor activities and communicate with families. A useful forecast requires timely inputs as well as accuracy.')
    B('Chiang Mai source-apportionment research identifies biomass burning as important during haze periods [2]. This motivates a regional fire predictor, but does not guarantee incremental forecast skill.')
    B('This lab examines severity, timing, tomorrow prediction and an actionable recommendation for one Chiang Mai receptor. Modeled CAMS values are distinguished from measured station exposure throughout.')
    H('Study contract')
    T(['Item','Definition'],[['Location',f"{cfg['latitude']} N, {cfg['longitude']} E; one receptor"],
        ['Study targets',cfg['start_date']+' to '+cfg['end_date']+'; earlier source days are buffers'],
        ['Issue / target','D 07:00 Thailand -> modeled daily profile P(D+1), local 00:00-24:00'],
        ['Fixed threshold',str(threshold)+' ug/m3; modeled exceedance, not an official measured violation'],
        ['Scope','Nominal-source-clock-constrained retrospective benchmark; actual original publication/revision not certified']],[100,width-100])
    H('Key findings: baseline first')
    B(f"The common modeling cohort has {coverage['common_days']} of {coverage['calendar_days']} target dates. Test covers all {int(chosen.n)} days of calendar 2025.")
    B(f"Persistence test MAE is {baseline.MAE:.3f}; direct CAMS reference MAE is {provider.MAE:.3f}. Validation selects {selection['experiment']}, whose test MAE is {chosen.MAE:.3f}.")
    B(f"Selected-model missed exceedances: {int(chosen.FN)}/{int(chosen.positive_days)}; false alerts: {int(chosen.FP)}. Accuracy and operational readiness are separate conclusions.")
    E('model_scores.csv; selection.json; coverage_summary.json; source_time_contract.json.')

    page('2 Approach | questions and expected contributions')
    P('Question: what do weather and regional fire histories add beyond PM history, and does a 3-, 5- or 7-day history help? All settings use the same dates and fixed target definition.')
    T(['Group','Inputs','Paired question at each k','Features: 3 / 5 / 7'],[
        ['H1','PM','H1 - persistence','9 / 15 / 21'],['H2','PM + weather','H2 - H1','30 / 50 / 70'],
        ['H3','PM + fire','H3 - H1','15 / 25 / 35'],['H4','PM + weather + fire','H4 - H2; H4 - H3','36 / 60 / 84']],[40,105,180,width-325])
    B('Subquestions a/b/c mean k=3/5/7. PM persistence motivates H1; meteorological transport/removal motivates H2; biomass-burning activity motivates H3. H4 tests each addition conditionally. Expectations are working hypotheses, not required positive findings.')
    B('A short window may follow recent conditions; a longer one may capture persistence but adds correlated inputs. Validation selects windows, while all three test results remain visible.')
    H('Development from the original model')
    T(['Initial approach','Current approach'],[
        ['Baselines and temporal evaluation already existed','Baselines are retained; source clocks and label maturity are explicit.'],
        ['Original code used several lags and rolling windows','Compare exactly 3/5/7 days within each of four source groups.'],
        ['Covered-day zeros and unknown fire days were distinguished','Native GFAS values are distinguished from missing data, with separate QC.'],
        ['Metrics and configurations were exported','Receipts link sources, data and models; prediction and SQL checks are reproducible.']],[width/2,width/2])
    B('Structural progress is clearer timing, provenance and matched comparisons. Better accuracy must be demonstrated separately. The original H1-H4 had different fire-specific meanings; the labels have different meanings in the initial and current experiments.')
    E('reference/model_development_trace.csv; original_notebook_inventory.json; Appendix F.')

    page('3 Method | workflow and information separation')
    F('08_workflow.png','Figure 1. Shared notebook/script workflow. The availability branch keeps operational prediction blocked; technical checks are not original-release evidence.',500)
    B('Freeze -> commit predictions without test answers -> open answers and score. The SQL store preserves real records and receipts; it is not an independent ground-truth dataset.')
    B('This historical dataset was previously inspected. Interface isolation does not turn it into an untouched or prospective trial.')

    page('3 Method | sources, target and time availability')
    T(['Source / role','Native product and clock','At issue D 07:00 Thailand'],[
        ['PM history / target','ADS CAMS mc/fc/0001; run d-1 at 12 UTC; leads 5-28 form P(d)','History P(D-1)..P(D-k). Target P(D+1) is later verification output.'],
        ['Weather history','Open-Meteo gfs_global previous_day1 forecast values; local daily summaries','Days D-1..D-k. Fixed forecast offset is not an observed public-release timestamp.'],
        ['Fire history','GFAS v1.2 daily UTC means; FRP density and observation-opportunity QC','UTC days D-2..D-(k+1), reflecting the documented next-day 07 UTC schedule.'],
        ['Provider reference','CAMS run D-1 at 12 UTC, leads 29-52','Target D+1, nominally released 2h before issue; never a learned feature.']],[95,205,width-300])
    T(['API / dataset','Request identity'],[
        ['ADS /api','https://ads.atmosphere.copernicus.eu/api; datasets: cams-global-atmospheric-composition-forecasts and cams-global-fire-emissions-gfas.'],
        ['Public weather /v1/forecast','https://previous-runs-api.open-meteo.com/v1/forecast; models=gfs_global, six *_previous_day1 fields, timezone=UTC, wind_speed_unit=ms.'],
        ['Request periods','PM runs: 2023-12-23..2025-12-30; GFAS UTC days: 2023-12-23..2025-12-31; weather UTC hours: 2024-01-01..2025-12-31. Exact bounds/areas are preserved in raw plans and manifests.']],[100,width-100],tiny=True)
    H('Explicit clock example')
    B('For issue 1 January 2025 at 07:00 Thailand (=00 UTC), predict 2 January local 00:00-24:00. Target starts 17h and ends 41h after issue. The PM/weather 7-day history is 25-31 December; GFAS UTC history is 24-30 December.')
    B('CAMS 12 UTC is scheduled by 22 UTC; GFAS daily analysis by 07 UTC. Latest PM history has 26h nominal margin, fire 17h, and provider reference 2h. ADS delivery exceptions remain possible [3,4].')
    B('Section 6.2: source-day and target offsets are checked; labels must mature before evaluation and transforms fit within training folds. Documented source clocks inform the offsets. Exact historical public-release/revision was not audited, so operational replay is not certified.')
    E('source_time_contract.json; raw transfer_receipt.json; timezone_examples.csv; study_contract.json.')

    page('3 Method | preparation and row reconciliation C1-C3')
    H('C1-C2: preserve calendars, units and one-to-one joins')
    T(['Step','Rows / decision'],[['Study target calendar','731 days across full 2024-2025'],
        ['Value-complete PM/fire/weather 7-day histories','704; first usable target 28 January 2024'],
        ['Declared source-advisory dependency quarantine','15 targets: 9-23 August 2024; conservative, not confirmed local contamination'],
        ['Outer label-maturity purges','30 September and 31 December 2024: 2 days'],
        ['Common modeling cohort',str(coverage['common_days'])+' days shared by all 12 settings']],[220,width-220])
    B('The table keeps history buffers before the study and unavailable targets after it. PM/weather join on local dates; GFAS on its explicit earlier UTC mean day. Calendar lags precede exclusions, so missing dates cannot become adjacent observations.')
    join=J('join_audit.json')
    T(['Source before join','Alignment / retained calendar'],[
        [str(join['PM_profiles'])+' complete PM profiles','One local profile per date; 739 history-anchor calendar rows.'],
        [str(join['weather_raw_hours'])+' weather UTC hours','Convert to Thai time; require 24 valid hours per daily field; missing values remain missing.'],
        [str(join['GFAS_utc_days'])+' GFAS UTC days (two fields/day)','Latest source day D-2; reindex to the 739-row history calendar.'],
        ['Calendar before / after join',str(join['daily_rows_before_join'])+' / '+str(join['daily_rows_after_join'])+'; one-to-one keys, no row multiplication. Buffers and out-of-study targets stay in the ledger.']],[170,width-170],tiny=True)
    H('C3: fill/drop decisions and native zeros')
    B('No target or predictor interpolation, forward fill, median replacement or blanket zero filling. Daily PM/weather need 24 valid hours. Missing or invalid input makes its complete-history row ineligible; raw records remain preserved.')
    B('GFAS native regional FRP is all zero on 323 of 740 captured UTC days; the longest run is 59 days, 11 June-8 August 2025. These are source-analysis values, not project-imputed missing. They do not prove absence of real fires; assimilation and observation opportunity remain source limitations.')
    B('GFAS density (W/m2) is integrated with spherical cell area: mean power MW = sum(density*area)/1e6. Positive-analysis area fraction is an extent index, not hotspots or burnt area. offire may exceed 1 and is not clipped or modeled [4].')
    E('join_audit.json; row_inclusion.csv; missing_decisions.csv; gfas_daily_derived.csv; fire_area_aggregation.json.')

    page('3 Method | variables, models and evaluation')
    T(['Input group','Base variables and units'],[['PM:3','Mean / minimum / maximum of the same 24-hour profile (ug/m3)'],
        ['Weather:7','Temperature(degC), humidity(%), pressure(hPa), wind speed/u/v(m/s), precipitation total(mm/day)'],
        ['Fire:2','log1p(area-integrated mean FRP in MW); positive-analysis area fraction'],
        ['Excluded','Target, dates, quality/availability flags, offire and provider reference are not learned predictors']],[100,width-100])
    B('Hourly wind components u=-s*sin(theta), v=-s*cos(theta) are averaged after conversion. Rain intervals use their start day. A k-day setting has only its source groups and lags 0..k-1; its actual source days follow the source-clock contract.')
    B('Primary Ridge: squared error plus alpha*sum(beta squared), alpha in {0.1,1,10,100,1000}; StandardScaler fits only within training folds. HGB is secondary: 200 iterations, learning rate 0.05,minimum leaf 20; leaf nodes 7/15 and L2=0/10. Both clip predictions at 0 consistently in CV and scoring.')
    T(['Partition','Dates','N'],[[r.partition,str(r.first_target)[:10]+' to '+str(r.last_target)[:10],int(r.n)] for r in chronology.itertuples()],[90,width-135,45])
    B('Three training-only expanding calendar folds use gap 1 plus explicit label-completion checks. Two outer boundaries are purged before selection/refit, because next-phase first issue precedes completion of those target days.')
    B('Validation MAE selects the primary source/window and within-group preferred windows. Every fixed setting is reported on test; no test winner is promoted. Moving-block 95% intervals: 14 days, 1000 repeats, seed 42; 7/28-day blocks are secondary sensitivity.')
    E('feature_manifest.csv; cv_calendar_audit.csv; chronology.csv; forecast_lock.json; tuning.json.')

    page('4 Results | severity, seasonality and fire quality')
    T(['Year','Valid days','Mean PM','Maximum','Modeled exceedance days'],[[int(r.year),int(r.valid_days),f'{r.mean:.2f}',f'{r.maximum:.2f}',int(r.exceed_days)] for r in annual.reset_index().itertuples()],[45,65,85,85,width-280])
    F('02_exceedances_seasonality.png','Figure 2. Full-year modeled counts with actual denominators;2024 includes leap day. Pooled monthly means describe two archived model years, not a long-term measured trend.',200)
    F('03_fire_quality.png','Figure 3. GFAS mean FRP power and observation-opportunity area are different quantities. Native zero-analysis stretches are retained; no detection/observation completeness claim follows.',205)
    B('Severity uses the full modeled calendar; predictive scores below use the common cohort and declared partitions. These populations are not interchangeable.')
    E('annual_summary.csv; monthly_summary.csv; coverage_by_month.csv; gfas_daily_derived.csv.')

    page('4 Results | baseline first, then all twelve settings C5')
    T(['Test reference','MAE','RMSE','Recall','FP / FN'],[[str(r.experiment),'-' if pd.isna(r.MAE) else f'{r.MAE:.3f}','-' if pd.isna(r.RMSE) else f'{r.RMSE:.3f}',f'{r.recall:.3f}',f'{int(r.FP)} / {int(r.FN)}'] for r in scores[(scores.partition=='test')&(scores.family=='baseline')].itertuples()],[170,65,65,65,width-365])
    T(['Primary Ridge setting','MAE','RMSE','Recall','FP / FN'],[[str(r.experiment),f'{r.MAE:.3f}',f'{r.RMSE:.3f}',f'{r.recall:.3f}',f'{int(r.FP)} / {int(r.FN)}'] for r in scores[(scores.partition=='test')&(scores.family=='ridge')].itertuples()],[170,65,65,65,width-365])
    B(f"Validation selected {selection['experiment']}; its test MAE is {chosen.MAE:.3f}. Relative to persistence this is {abs(reduction):.1f}% {'lower' if reduction>=0 else 'higher'}. Relative to the provider forecast it is {abs(provider_change):.1f}% {'lower' if provider_change>=0 else 'higher'}.")
    B('All rows use identical 365 test dates. C0 is warning-only; its numeric encoding is not assigned a regression score. A good persistence comparison alone does not show benefit over the earlier CAMS forecast.')
    E('model_scores.csv; predictions_test.csv; selection.json; metrics.csv. Secondary HGB results appear in Appendix C.')

    page('4 Results | incremental inputs and uncertainty')
    F('04_twelve_settings.png','Figure 4. All 12 primary settings on matched dates. Color/rank does not change the validation-selected candidate.',205)
    T(['k','Increment','MAE difference','Pointwise 95% block interval'],[[int(r.window),r.comparison,f'{r.estimate:+.3f}',f'[{r.ci_low:+.3f}, {r.ci_high:+.3f}]'] for r in contrasts.itertuples()],[25,90,105,width-220],tiny=True)
    B('Negative differences favor the added group. Intervals spanning 0 are inconclusive; intervals entirely above 0 favor the reference. H4 needs both conditional comparisons to distinguish weather from fire contributions.')
    B(f"Across 7/14/28-day block sensitivity, {diagnostic['primary_contrasts_changing_classification_across_blocks']} of 15 primary contrast classifications change. These are exploratory pointwise intervals, not multiplicity-adjusted confirmations; uncertainty is not hidden when a working expectation fails.")
    E('paired_comparisons.csv; twelve_answers.csv; bootstrap_sensitivity.csv; window_selection_by_group.csv.')

    page('4 Results | warning errors and station reference C4-C6')
    F('05_warning_errors.png','Figure 5. Fixed 37.5 threshold on the same modeled test outcomes; lower MAE does not guarantee fewer missed exceedances.',165)
    B(f"Selected model: recall {chosen.recall:.3f}, precision {chosen.precision:.3f}, FP {int(chosen.FP)}, FN {int(chosen.FN)}. Persistence: FP {int(baseline.FP)}, FN {int(baseline.FN)}. Provider reference: FP {int(provider.FP)}, FN {int(provider.FN)}.")
    H('C4: one primary receptor, explicit source grids')
    B('The requested Chiang Mai receptor maps to ADS 18.8N, 98.8E on 0.4-degree output. Weather has its own source grid; the regional fire box is not another PM location. No second independent study site is invented.')
    H('C6: preserved contemporary measured reference')
    T(['Station','Reporting local time','Air4Thai 24h','CAMS 24 samples','Signed difference'],[[str(r.station_id),str(r.reported_at_local),f'{r.reference_pm25_rolling24h:.2f}',f'{r.cams_pm25_mean24_samples:.2f}',f'{r.signed_difference_cams_minus_station:+.2f}'] for r in c6_rows.itertuples()],[45,135,85,90,width-355],tiny=True)
    B('This 16 October 2026 station/Open-Meteo snapshot is outside the 2024-2025 study and uses a separate product/grid. Air4Thai rolling 24h concentration is compared with 24 modeled hourly samples at nominally matched location/time; one-hour boundary sensitivity is retained. It does not validate the historical ADS target [6].')
    B(J('station_crosscheck.json')['reference_priority']+' Differences may reflect grid and averaging-window mismatch; this point check does not validate historical ADS targets or station-level warning skill.')
    E('station_crosscheck.csv/json; spatial_resolution_audit.json; warning_day_details.csv; missed_day_details.csv.')

    page('5 Conclusion | supported actions and limitations')
    P(f"The direct answer is conditional on the modeled target and retained dates: validation chose {selection['experiment']}. Its MAE is {chosen.MAE:.3f}, persistence {baseline.MAE:.3f}, provider reference {provider.MAE:.3f}. Warning misses are {int(chosen.FN)} vs {int(baseline.FN)} and {int(provider.FN)}, respectively. Source additions and window answers are reported separately, not reduced to one winner.")
    P(incremental_conclusion,'small')
    H('What improved structurally, and what the numbers establish')
    B('The original already had baselines, temporal evaluation and multiple lags. The current design improves the inspectable contract: fixed archived vintages, actual 07:00 next-day horizon, source-specific offsets, cell-area-correct fire variables, label-maturity purges and current-run provenance.')
    B('Predictive improvement is assessed against contemporaneous baselines on matched dates. Old/new MAE also changes with product, horizon, period and cohort; it cannot isolate algorithm improvement. Appendix F preserves both results and explains this comparison limit.')
    B(f"Training/validation contain {int(chronology.loc[chronology.partition.eq('train'),'positive_days'].iloc[0])}/{int(chronology.loc[chronology.partition.eq('validation'),'positive_days'].iloc[0])} modeled exceedances, versus {int(chosen.positive_days)} in test. The validation-selected candidate is not the lowest-test-MAE setting; this shift and the short validation season limit generalization. These counts explain uncertainty, not a reason to retune the inspected test.")
    H('Who should do what, and when')
    T(['Owner / timing','Proposed action and check'],[
        ['Principal / before outdoor activities','Review current official local air-quality information under existing school policy; log source/time and the decision. Recheck when conditions change. Do not treat this prototype as an automatic warning.'],
        ['Analytics team / each 07:00 trial issue','Shadow trial only: retain source values/versions, acquisition times, issued prediction and missing-input status; do not backfill a missed issue. Score later against a separately defined local measured target.'],
        ['School + analytics / before trial and review','Agree FN/FP costs, minimum acceptable recall, review schedule and stop conditions before seeing new outcomes. Compare persistence and direct-provider forecasts; a failed source gate means no automatic release.']],[125,width-125],tiny=True)
    B('These are proposed procedures, not evidence that a school adopted them. For the current modeled test, cost=FP+r*FN gives selected-minus-persistence = -11+4r; selected is worse for r>2.75. The cost ratio is illustrative, not a measured stakeholder value. False reassurance and unnecessary disruption require explicit review.')
    H('Limits that remain open')
    B('Temporal cutoff and label-maturity checks address Section 6.2 under this retrospective design. Separate limits remain: exact historical public release/revision, one coarse-grid receptor, GFAS/CAMS source dependence, two-year/model-cycle variability and exploratory multiple comparisons.')
    E('availability_gate.json; source_time_contract.json; model_development_comparison.csv; reference_store.json. Student review/signature and actual repository/video submission remain external tasks.')

    page('Appendix A | every-column missingness and decisions')
    P('Denominators include all 739 daily history-anchor rows, with explicit buffers and out-of-study targets. Raw native source missingness and derived-calendar missingness are different quantities.','small')
    T(['Column','Missing N','Total N','Missing %'],[[r.column,int(r.missing_rows),int(r.total_rows),f'{r.missing_percent:.3f}'] for r in missing.itertuples()],[width-150,50,50,50],tiny=True)
    decisions_table=C('missing_decisions.csv')
    T(['Column','Action / reason'],[[r.column,r.action+' '+r.reason] for r in decisions_table.itertuples()],[145,width-145],tiny=True)
    page('Appendix A | daily variables, units and retain/drop rationale')
    dictionary=C('data_dictionary.csv')
    T(['Column','Unit','Purpose','Input?'],dictionary.astype(str).values.tolist(),[145,80,width-260,35],tiny=True)
    page('Appendix B | every derived predictor')
    P('Exactly 84 maximum-window predictors. PM/weather lagj uses local day D-1-j; fire uses UTC day D-2-j. Original public release remains unverified; nominal rules are explicit.','small')
    T(['Feature','Group','Lag','Unit','Purpose'],[[r.feature,r.source_group,int(r.lag_days),r.unit,r.purpose] for r in features.itertuples()],[140,35,25,90,width-290],tiny=True)
    page('Appendix C | complete experiment answers and robustness')
    answers=C('twelve_answers.csv')
    T(['Learner / setting','MAE','Recall','FP/FN','Answer'],[[r.family+' / '+r.experiment,f'{r.MAE:.3f}',f'{r.recall:.3f}',f'{int(r.FP)}/{int(r.FN)}',r.answer] for r in answers.itertuples()],[95,40,40,40,width-215],tiny=True)
    page('Appendix C | quality-policy and uncertainty sensitivity')
    for filename in ['fire_policy_sensitivity.csv','learner_robustness.csv']:
        frame=C(filename);H(filename)
        columns=[x for x in frame.columns if x not in ['scope','interpretation']]
        T(columns,frame[columns].round(4).astype(str).values.tolist(),tiny=True)
    P('The advisory policy and 14-day interval stay primary. Policy alternatives count coverage only; HGB and 7/28-day intervals do not trigger reselection. All complete interval tables remain in the CSV outputs.','small')
    page('Appendix C | additional figures and interpretation')
    F('01_daily_pm25.png','Figure A1. Full-calendar fixed-vintage CAMS profiles; modeled output at one point, not measured provincial exposure.',180)
    F('06_matched_period_coverage.png','Figure A2. Source-history availability, conservative advisory policy and maturity purges change cohort coverage.',180)
    F('07_warning_days.png','Figure A3. Selected-model forecasts, targets and missed modeled exceedances on retained test dates.',180)

    page('Appendix D | complete executed notebook code cells')
    P('English explanations describe each cell. Grey blocks reproduce every code cell with Thai inline comments. Display wrapping is not a source edit. Execution counts reflect the saved notebooks at generation time. The runner rebuilds this PDF after saving all four complete notebooks; final execution evidence is authoritative.','small')
    from workflow import NOTEBOOKS
    for bookname in NOTEBOOKS:
        book=json.loads((root/bookname).read_text(encoding='utf-8'));code_number=0;previous=''
        H(bookname)
        for index,cell in enumerate(book['cells'],1):
            source=''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
            if cell['cell_type']=='markdown':previous=source;continue
            code_number+=1
            guide=cell.get('metadata',{}).get('lab_guide',{})
            title=guide.get('purpose',next((x.lstrip('# ').strip() for x in previous.splitlines() if x.startswith('#')),'Execute this study stage'))
            variables=guide.get('variables','See names assigned in the source and feature_manifest.csv for model input definitions.')
            header=[Paragraph(html.escape(f'Cell {index} - {title}'),styles['sub']),
                    Paragraph(html.escape('Variables: '+variables),styles['small'])]
            reading.append('\n### '+bookname+' cell '+str(index)+'\n'+source+'\n')
            lines=source.splitlines();comments={t.start[0]:t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type==tokenize.COMMENT}
            data=[[header[0]],[header[1]]]
            count=cell.get('execution_count');label='In ['+('pending' if count is None else str(count))+']'
            data.append([Paragraph(html.escape(label),styles['small'])])
            for number,line in enumerate(lines,1):
                if not line.strip():data.append([Spacer(1,3)]);continue
                token=comments.get(number)
                if token:
                    before=line[:token.start[1]];comment=line[token.start[1]:]
                else:before=line;comment=''
                markup='<font name="Courier">'+html.escape(before).replace(' ','&#160;')+'</font>'
                if comment:markup+=' <font name="LabThai" color="#28633d">'+html.escape(comment)+'</font>'
                data.append([Paragraph(markup,styles['code'])])
            block=ContinuedCodeTable(data,colWidths=[width],hAlign='LEFT',repeatRows=3,rowSplitRange=(min(6,len(data)),-1))
            block.setStyle(TableStyle([('BACKGROUND',(0,2),(-1,-1),colors.HexColor('#f2f2f2')),
                ('BOX',(0,2),(-1,-1),.4,colors.HexColor('#b9b9b9')),('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                ('LEFTPADDING',(0,0),(-1,1),0),('RIGHTPADDING',(0,0),(-1,1),0),
                ('TOPPADDING',(0,0),(-1,-1),1.5),('BOTTOMPADDING',(0,0),(-1,-1),1.5)]))
            story.extend([block,Spacer(1,10)])
            cell_rows.append({'notebook':bookname,'cell':index,'purpose':title,'variables':variables,'code_lines':len(lines)})
    pd.DataFrame(cell_rows).to_csv(root/'report/cell_guide.csv',index=False)

    page('Appendix E | requirements and source references')
    mapping=[['C1 local/UTC days','Main p4-5','timezone_examples.csv; rain_interval_audit.csv; source_time_contract.json'],
        ['C2 joins / row counts','Main p5','join_audit.json; row_inclusion.csv; cohort_ledger.csv'],
        ['C3 missing / zero / drop','Main p5; Appendix A','missing_decisions.csv; gfas_daily_derived.csv; no target fill'],
        ['C4 spatial scope','Main p10','One receptor retained; source grids/region explicit'],
        ['C5 baseline / CV / test','Main p6; p8-9','Persistence+provider reference; maturity-purged CV; all 12 settings'],
        ['C6 measured reference','Main p10','Preserved separate contemporary Air4Thai/Open-Meteo point check'],
        ['Section 6.2 knowability','Main p4; p6; p11','Checked source/target offsets, mature labels and fold-local transforms; separate original-release audit not certified'],
        ['Feasibility checker','Stages01/02','Project-owned check_dataset.py; no additional instructor script'],
        ['Reproducibility','README; four notebooks','Exact raw payloads, source/data locks, SQL parity and authentic saved cells'],
        ['Personal submission','Final page','Student review/signature, actual repository access and 10-minute unlisted video remain external']]
    T(['Requirement','Where','Evidence / status'],mapping,[135,100,width-235],tiny=True)
    refs=[
        '[1] WHO. Ambient (outdoor) air pollution (2024). https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health . Health context only.',
        '[2] Chansuebsri et al. (2024). Chemical composition and origins of PM2.5 in Chiang Mai (Thailand) by integrated source apportionment and potential source areas. Atmospheric Environment 327,120517. https://doi.org/10.1016/j.atmosenv.2024.120517 . Motivation, not forecast-skill evidence.',
        '[3] ECMWF. CAMS Global atmospheric composition forecast data documentation. https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation . Native forecast identity, units and nominal release schedule; ADS delay caveat.',
        '[4] ECMWF. GFAS v1.2 data documentation. https://confluence.ecmwf.int/spaces/CKB/pages/88247734/CAMS+global+biomass+burning+emissions+based+on+fire+radiative+power+GFAS+v1.2+data+documentation . UTC means, density, assimilation and offire interpretation.',
        '[5] Open-Meteo. Previous Runs API. https://open-meteo.com/en/docs/previous-runs-api . Forecast values at fixed offsets; not station observations or a per-origin public-release ledger.',
        '[6] PCD/EPO8. Air4Thai PM2.5 rolling-period explanation. https://epo08.pcd.go.th/th/news/detail/180206 . Separate raw station snapshot and boundary sensitivity are preserved.',
        '[7] ECMWF. GFAS/CAMS contamination advisory9-14 August 2024 and corrected GFAS notice. https://forum.ecmwf.int/t/issue-with-gfas-and-cams-global-forecast-outputs-due-to-contaminated-observations/3995 . Conservative date dependencies do not prove local contamination.',
        '[8] scikit-learn. Cross-validation and common pitfalls. https://scikit-learn.org/stable/modules/cross_validation.html ; https://scikit-learn.org/stable/common_pitfalls.html . Fold-local transforms and temporal evaluation.',
        '[9] DS-270702 HW4 PM2.5 lab sheet. Required structure/checkpoints and assessment criteria. Example PDFs inform formatting only.'
    ]
    for ref in refs:P(ref,'small')
    P('Scientific counts and metrics come from the delivered raw/processed/result files. Documentation supports nominal contracts; no historical public-release timestamp is invented.','small')

    page('Appendix F | development from the original model')
    P('The original notebooks, initial benchmark and current study address related but different questions. The comparison retains the initial results and identifies changes in the evaluation conditions.','small')
    trace=pd.read_csv(root/'reference/model_development_trace.csv')
    T(['Topic','Verified original / retained strength','Development in this study'],[[r.topic,r.verified_original,r.development] for r in trace.itertuples()],[90,210,width-300],tiny=True)
    H('Historical numerical comparison: interpretation first')
    T(['Stage','N','Selected','Model MAE','Own B0 MAE','Skill vs own B0'],[[r.stage,int(r.test_days),r.selected,f'{r.model_MAE:.3f}',f'{r.own_persistence_MAE:.3f}',f'{r.skill_percent_vs_own_persistence:+.1f}%'] for r in comparison.itertuples()],[105,30,65,75,75,width-350],tiny=True)
    B('The initial benchmark tested a quality-screened 2026 subset; the current study tests full 2025 with a 17h lead to the next local day, explicit archived-vintage targets and different weather/fire products. Raw MAE and event frequency therefore change with evaluation conditions.')
    B('The comparison establishes skill for each model against its own matched persistence reference. It does not identify why every numeric difference occurred or isolate a causal improvement from the algorithm. A controlled accuracy comparison across study designs would require matching target, dates and information sets.')
    B('Structural gains are directly checked: source identities/offsets, forecast-vintage separation, area/unit calculations, mature training labels and consistent notebook/script/SQL/report evidence. Original public release and independent station forecasting remain unresolved.')
    E('model_development_comparison.csv; reference/initial_benchmark; original_notebook_inventory.json; study_contract.json.')

    page('AI disclosure and submission checklist')
    P('Final physical page; twelfth main-report page when appendices are excluded. Student review/signature are not supplied by automation.','small')
    T(['Where used','Assistance requested','Changes / rejected claims'],[
        ['Data/code','Source-clock design, acquisition/QC and all 12 comparisons.','Preserved real raw payloads; rejected target fill, false-zero conversion and invented publication timestamps.'],
        ['Analysis','Temporal split, source/window effects and verification.','Retained baselines, validation-only selection and negative/inconclusive results; distinguished modeled targets from measured reference.'],
        ['Report','English sections, figures, development trace and Thai line comments.','Kept original report style; separated structural progress from predictive outcomes. Student must review and explain submitted work.']],[100,165,width-265],tiny=True)
    checklist=[(False,'Repository is public or the instructor has access'),(True,'README explains execution order and dependencies'),
        (True,'Raw files are exact captured API responses with hashes'),(True,'Four notebooks and required scripts are included'),
        (True,'Figures and metrics are separate artifacts'),(True,'Five report sections and all C1-C6 answers are present'),
        (True,'Persistence and provider reference are reported alongside the models'),(True,'Recommendation names a decision-maker and limits'),
        (True,'AI disclosure table is supplied for student review'),(False,'I personally cloned the published repository and reran it'),
        (False,'I can explain every line and have verified the final disclosure'),(False,'The required 10-minute unlisted video and links are submitted')]
    for checked,text in checklist:P(('[x] ' if checked else '[ ] ')+text,'small')
    P('Local technical replay evidence is distinct from a student-verified published-repository clone. The required video demonstrates the report, code and fetch process. Technical PASS does not certify original historical publication, deployment readiness or student understanding.','small')
    P('Student signature: __________________________   Date: __________________','small')

    root.joinpath('report').mkdir(exist_ok=True)
    path=root/'report/report.pdf'
    SimpleDocTemplate(str(path),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42,
        title='Chiang Mai PM2.5 - twelve settings and evidence',author=profile['name']).build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(path)
    appendix_start=next(i for i,p in enumerate(reader.pages) if 'Appendix A | every-column missingness' in (p.extract_text() or ''))
    if appendix_start!=11:raise ValueError(f'Main content spilled: expected 11 pages before appendices; got {appendix_start}.')
    if 'AI disclosure and submission checklist' not in reader.pages[-1].extract_text():raise ValueError('AI disclosure must be the final physical page.')
    (root/'report/report_draft.md').write_text('\n'.join(reading),encoding='utf-8')
    proposal=[Paragraph('One-page project proposal',styles['head'])]
    proposal_text=[profile['name']+' | '+profile['student_id']+' | 270702 Data Science Programming',
        'Question: what do weather and regional fire histories add beyond PM history, and which 3/5/7-day window is useful?',
        'Issue and target: 07:00 Thailand on D -> modeled daily CAMS profile P(D+1); 17h to target start. One Chiang Mai receptor. Study target dates 2024-2025; source buffers precede the period.',
        'Sources: fixed 12 UTC CAMS forecasts, Open-Meteo GFS previous_day1 weather forecasts and GFAS v1.2 UTC daily analysis. Air4Thai/Open-Meteo provides a separate contemporary C6 reference, not historical target truth.',
        'Design: H1 PM, H2 PM+weather, H3 PM+fire, H4 all, each at 3/5/7 days on identical common dates. Source-specific clocks, 24-hour completeness, no target/predictor imputation, conservative advisory dependencies and mature-label boundary purges.',
        'Evaluation: persistence and direct CAMS references; primary Ridge, secondary HGB; training-only temporal CV and validation-only source/window choice. Full calendar 2025 test, MAE/RMSE and fixed 37.5 warning metrics; exploratory calendar-block intervals.',
        f'Coverage: 731 study target days,704 value-complete source histories,{coverage["common_days"]} common modeling dates after declared quality/maturity rules. Technical feasibility does not certify original public release/revision.',
        'Outputs: four executed notebooks, required scripts, exact raw/processed data, SQLite audit store, figures, metrics, development comparison and the English lab report.',
        'Scope: retrospective benchmark after prior exploration. Temporal cutoff, label maturity and training-only preprocessing address Section 6.2; exact historical release/revision and deployment are separate, unverified claims. Student review, repository access and video submission remain required.']
    for text in proposal_text:proposal.append(Paragraph(html.escape(text),styles['body']))
    proposal_path=root/'report/proposal.pdf'
    SimpleDocTemplate(str(proposal_path),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42,
        title='PM2.5 project proposal',author=profile['name']).build(proposal,onFirstPage=footer)
    if len(PdfReader(proposal_path).pages)!=1:raise ValueError('Proposal must remain one page.')
    excluded={'seal_verification.json','run_state.json','execution_evidence.json','raw_checks.json','dataset_checks.json','checker_cli_attempt.json','pdf_visual_review.json','acceptance_review.json','script_route_validation.json','regression_tests.json','archive_validation.json'}
    inputs=[root/'config.json',root/'student_profile.json',root/'data/processed/final_dataset_daily.csv',
        *sorted((root/'report/study_metadata').glob('*')),*sorted((root/'report/fonts').glob('*')),
        *sorted((root/'outputs/figures').glob('*')),*[p for p in (root/'outputs/results').glob('*') if p.suffix in ['.csv','.json'] and p.name not in excluded],
        path,proposal_path,root/'report/report_draft.md',root/'report/cell_guide.csv']
    source_hashes={}
    import hashlib
    for name in NOTEBOOKS:
        book=json.loads((root/name).read_text(encoding='utf-8'))
        text=json.dumps([{'cell_type':c['cell_type'],'source':c['source']} for c in book['cells']],ensure_ascii=False,sort_keys=True)
        source_hashes[name]=hashlib.sha256(text.encode('utf-8')).hexdigest()
    result={'physical_pages':len(reader.pages),'main_pages':12,'appendix_pages':len(reader.pages)-12,'proposal_pages':1,
        'listed_code_cells':len(cell_rows),'notebook_source_hashes':source_hashes,
        'inputs_and_outputs':{p.relative_to(root).as_posix():sha256(p) for p in inputs if p.is_file()},
        'scope':'Report/source consistency; original historical publication and personal/external attestations remain separate.'}
    write_json(root/'report/report_provenance.json',result)
    return {'report':str(path),**{k:result[k] for k in ['physical_pages','main_pages','appendix_pages','proposal_pages','listed_code_cells']}}
