"""Generate the evidence-based English report and one-page proposal."""
from report_document import build_report

if __name__ == "__main__":
    from common import load_config
    root,cfg=load_config()
    print(build_report(root,cfg))
