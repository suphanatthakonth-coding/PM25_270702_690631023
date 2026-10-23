"""Readable workflow and decision evidence, generated from saved project results."""
import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,Polygon
from analyse import savefig


def make_workflow(root,cfg):
    fig,ax=plt.subplots(figsize=(9,10.5));ax.set(xlim=(0,10),ylim=(-.2,12.5));ax.axis('off')
    labels=[('Fetch real responses; preserve raw bytes','Fixed-run CAMS / GFS / GFAS / station reference'),
        ('Validate schema, units, time and hashes','FAIL: stop and save a current-run audit'),
        ('Build source-specific calendars; apply quality rules','No target imputation; native GFAS zeros retained'),
        ('Construct H1-H4 x 3/5/7-day histories','Use identical eligible dates for all settings'),
        ('07 Thai issue; mature labels at every split','Training-only temporal CV; validation-only choice'),
        ('Freeze models, features and evidence','Bind source/configuration/model checksums'),
        ('Commit predictions without test answers','Save timestamp, prediction hash and SQLite copy'),
        ('Open historical answers; score every setting','Persistence first; MAE/RMSE and warning errors'),
        ('Interpret uncertainty, coverage and limitations','Write the report and inspect authentic execution')]
    yvals=[11.7-i*1.25 for i in range(len(labels))]
    for i,((title,detail),y) in enumerate(zip(labels,yvals)):
        ax.add_patch(FancyBboxPatch((.5,y-.42),7.1,.84,boxstyle='round,pad=0.02',facecolor='#eef3f7',edgecolor='#3e6b8d'))
        ax.text(4.05,y+.12,title,ha='center',va='center',fontsize=10,fontweight='bold')
        ax.text(4.05,y-.16,detail,ha='center',va='center',fontsize=8.5)
        if i<len(labels)-1:ax.annotate('',xy=(4.05,yvals[i+1]+.44),xytext=(4.05,y-.44),arrowprops={'arrowstyle':'->','color':'#3e6b8d'})
    ax.text(8.7,7.4,'Publication\nevidence\nverified?',ha='center',va='center',fontsize=9)
    ax.add_patch(Polygon([(7.8,7.4),(8.7,8.1),(9.6,7.4),(8.7,6.7)],fill=False,edgecolor='#9c5b28'))
    ax.annotate('',xy=(8.7,8.1),xytext=(7.6,8.4),arrowprops={'arrowstyle':'->','color':'#9c5b28'})
    ax.text(8.7,5.7,'Current: NO\nRetrospective only\nOperational mode\nis blocked',ha='center',va='center',fontsize=9,color='#914324',bbox={'boxstyle':'round,pad=.4','fc':'#fff3e7','ec':'#9c5b28'})
    ax.annotate('',xy=(8.7,6.2),xytext=(8.7,6.7),arrowprops={'arrowstyle':'->','color':'#9c5b28'})
    ax.set_title('Workflow and information controls',fontsize=15,pad=14)
    savefig(root,fig,'08_workflow','Historical replay workflow. Valid-time lags and answer separation are checked; historical publication availability is not proven, so operational prediction remains blocked.')


def decision_evidence(root,cfg):
    scores=pd.read_csv(root/'outputs/results/model_scores.csv')
    selected=json.loads((root/'outputs/results/selection.json').read_text())['experiment']
    chosen=scores[(scores.partition=='test')&(scores.family==cfg['primary_family'])&(scores.experiment==selected)]
    chosen=chosen.iloc[0];baseline=scores[(scores.partition=='test')&(scores.experiment=='B0_persistence')].iloc[0]
    rows=[]
    for ratio in [1,5,10]:
        a=ratio*baseline.FN+baseline.FP;b=ratio*chosen.FN+chosen.FP
        rows.append({'assumed_FN_to_FP_cost_ratio':ratio,'baseline_weighted_error':a,'selected_weighted_error':b,
            'selected_minus_baseline':b-a,'scope':'Illustrative assumed relative costs; not validated stakeholder costs or deployment benefit.'})
    pd.DataFrame(rows).to_csv(root/'outputs/results/decision_cost_scenarios.csv',index=False)
    return rows
