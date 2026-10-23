"""Materialize the approved source clocks without manufacturing publication timestamps."""
import json
from common import write_json,selected_raw_run,sha256

def materialize_source_contract(root,cfg):
    if cfg['operational_issue_time_local']!='07:00' or cfg['prediction_mode']!='retrospective':
        raise ValueError('This study implements only07Thai next-day retrospective scope.')
    folder,manifest=selected_raw_run(root)
    path=root/'report/study_metadata/study_contract.json'
    sources=[{'source':'PM','product':'ADS CAMS operational forecasts; mc/fc/0001','source_window':'P(D-1)..P(D-k); local days',
        'nominal_latest_release_relative_to_issue_hours':-26,'original_release_observed':False,
        'evidence_url':'https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation'},
        {'source':'weather','product':'Open-Meteo GFS previous_day1 forecast history','source_window':'Local daysD-1..D-k; rain interval end can reach next00local.',
        'nominal_latest_prediction_time_relative_to_issue_hours':-31,'prediction_time_is_observed_public_release':False,'original_release_observed':False,
        'evidence_url':'https://open-meteo.com/en/docs/previous-runs-api'},
        {'source':'fire','product':'GFAS v1.2 daily analysis','source_window':'UTC mean daysD-2..D-(k+1)',
        'nominal_latest_release_relative_to_issue_hours':-17,'original_release_observed':False,
        'evidence_url':'https://confluence.ecmwf.int/spaces/CKB/pages/88247734/CAMS+global+biomass+burning+emissions+based+on+fire+radiative+power+GFAS+v1.2+data+documentation'},
        {'source':'provider_reference','product':'Same ADS PM product, earlier run','source_window':'Run D-1 at12UTC, leads29..52; targetD+1',
        'nominal_latest_release_relative_to_issue_hours':-2,'original_release_observed':False}]
    result={'status':'NOMINAL_SOURCE_CLOCKS_ENFORCED_RETROSPECTIVE_SCOPE','sources':sources,
        'contract_sha256':sha256(path),'raw_manifest_sha256':sha256(folder/'manifest.json'),
        'target':'P(D+1), local midnight-to-midnight;17h to start and41h to end.',
        'historical_publication_verified':False,'operational_use_allowed':False,
        'interpretation':'A defensible source-clock benchmark, not a guarantee against ADS delays, current archive revisions or original release exceptions.'}
    write_json(root/'outputs/results/source_time_contract.json',result)
    write_json(root/'report/study_metadata/source_time_contract.json',result)
    return result
