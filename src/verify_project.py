"""Verify the saved scientific/SQL/report evidence without making forecasts again."""
from common import load_config
from evaluate_forecast import verify_saved_results
from reference_store import verify_reference_store
from workflow import verify_report_dependencies

if __name__=='__main__':
    root,cfg=load_config()
    print(verify_saved_results(root,cfg))
    print(verify_reference_store(root))
    print(verify_report_dependencies(root)['main_pages'])
