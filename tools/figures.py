"""Export explanatory scientific figures; plotting is optional, not a core dependency."""
import json
from fractions import Fraction
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'echoproof-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echoproof import Mapping, encode
from echoproof.intervals import transitions

OUTPUT=ROOT/'artifacts/figures'
BLUE='#19638f'
GREEN='#08786c'
ORANGE='#bd5825'
INK='#18313f'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.edgecolor':'#c4d1d7','axes.labelcolor':INK,'text.color':INK,'xtick.color':INK,'ytick.color':INK,
                     'svg.fonttype':'none'})


def save(fig,name):
    fig.savefig(OUTPUT/(name+'.png'),dpi=180,bbox_inches='tight',facecolor='white')
    fig.savefig(OUTPUT/(name+'.svg'),bbox_inches='tight',facecolor='white',metadata={'Date':None})
    plt.close(fig)


def threshold_figure():
    fig,axes=plt.subplots(1,2,figsize=(12,5.2),sharey=True)
    for ax,high,title in zip(axes,(100,102),('Original input range: 0–100','Revised input range: 0–102')):
        mapping=Mapping(domain_high=str(high),pitch_step_cents=1200)
        exact_edges=[Fraction(0)]+[x for x in transitions(mapping) if 0<x<100]+[Fraction(100)]
        notes=[encode([x],mapping).events[0].pitch_cents/100 for x in exact_edges]
        edges=list(map(float,exact_edges))
        ax.step(edges,notes,where='post',color=BLUE if high==100 else GREEN,lw=3,label='Exact quantized pitch')
        ax.axvline(50,color=ORANGE,ls='--',lw=1.6,label='Threshold 50')
        ax.axvline(51,color=GREEN,ls=':',lw=1.6,label='Threshold 51')
        for value,marker in ((50.5,'o'),(51,'s')):
            pitch=encode([str(value)],mapping).events[0].pitch_cents/100
            ax.scatter([value],[pitch],s=90,marker=marker,edgecolors='white',linewidths=1,zorder=5)
        ax.set(title=title,xlabel='Input value',xlim=(0,100),ylim=(45,87),yticks=(48,60,72,84))
        ax.grid(axis='y',color='#e4eaee')
        ax.text(.03,.94,'50.5 and 51: same pitch' if high==100 else '50.5 and 51: different pitches',transform=ax.transAxes,va='top',fontsize=11)
        ax.text(.03,.83,'50 preserved; 51 lost' if high==100 else '51 preserved; 50 lost',transform=ax.transAxes,va='top',fontsize=11)
    axes[0].set_ylabel('Pitch (MIDI semitone number)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,bbox_to_anchor=(.5,-.03),frameon=False)
    fig.suptitle('Aligning one decision boundary can move another',fontweight='bold',fontsize=16,y=1.02)
    fig.subplots_adjust(bottom=.20,wspace=.12)
    save(fig,'threshold-repair')


def observed_figure():
    record=json.loads((ROOT/'artifacts/noaa-windows/selected_pair.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(12,5.3))
    for side,color,marker in (('left',BLUE,'o'),('right',ORANGE,'s')):
        window=record[side+'_window']
        label='%d–%d'%(window['years'][0],window['years'][-1])
        values=[float(x) for x in window['values']]
        axes[0].plot(range(3),values,marker=marker,color=color,lw=2.5,label=label)
        pitches=[e['pitch_cents']/100 for e in record['witness']['render']['events']]
        axes[1].plot(range(3),pitches,marker=marker,color=color,lw=2.5 if side=='left' else 1.2,
                     ls='-' if side=='left' else '--',markersize=10 if side=='left' else 5,label=label)
    axes[0].axhline(400,color=GREEN,ls=':',lw=2,label='400 ppm threshold')
    axes[0].set(title='Unmodified published annual means',ylabel='CO₂ (ppm)',ylim=(305,410))
    axes[1].set(title='Per-window normalized + quantized events',ylabel='Pitch (MIDI semitone number)',ylim=(44,88),yticks=(48,65,84))
    for ax in axes:
        ax.set(xlabel='Sample position in the 3-year window',xticks=(0,1,2))
        ax.grid(axis='y',color='#e4eaee')
        ax.legend(frameon=False,loc='center left' if ax is axes[0] else 'upper left')
    fig.suptitle('Different measured levels, identical relative-time pitch events',fontweight='bold',fontsize=15,y=1.02)
    fig.text(.02,-.04,'NOAA annual CO₂ archive; complete 1960–1962 and 2013–2015 windows. Years/ppm are not encoded in the sound.\nEvent equality is verified; no human listening result is claimed.',fontsize=10)
    fig.subplots_adjust(wspace=.22,bottom=.16)
    save(fig,'observed-windows')



def partition_figure():
    from echoproof.partition import partition_thresholds, PartitionEncoder
    original=Mapping(domain_high="100",pitch_step_cents=1200)
    record=partition_thresholds(original,[50,51],0,100)
    encoder=PartitionEncoder(record)
    fig,axes=plt.subplots(1,3,figsize=(14,4.8),sharey=True)
    original_edges=[Fraction(0),Fraction(50,3),Fraction(50),Fraction(250,3),Fraction(100)]
    partition_edges=[Fraction(0),Fraction(50),Fraction(51),Fraction(100)]
    for ax,edges,renderer,title in ((axes[0],original_edges,lambda v:encode(v,original),'Original uniform quantization'),(axes[1],partition_edges,encoder.encode,'Nonuniform task-aligned partition')):
        pitches=[renderer([x]).events[0].pitch_cents/100 for x in edges]
        ax.step(list(map(float,edges)),pitches,where='post',color=BLUE if ax is axes[0] else GREEN,lw=3)
        ax.set(title=title,xlim=(0,100),xlabel='Input value')
    zoom=axes[2]
    zoom.step([48,50,53],[60,72,72],where='post',color=BLUE,lw=2,ls='--',label='Original')
    zoom.step([48,50,51,53],[48,72,84,84],where='post',color=GREEN,lw=3,label='Partition')
    zoom.set(title='Two boundaries, one unit apart',xlim=(48,53),xticks=(48,49,50,51,52,53),xlabel='Input value (zoom)')
    zoom.legend(frameon=False,loc='upper left')
    for ax in axes:
        for cut in (50,51): ax.axvline(cut,color=ORANGE,ls=':',lw=1.2,zorder=0)
        ax.set(ylim=(45,87),yticks=(48,60,72,84))
        ax.grid(axis='y',color='#e4eaee')
    axes[0].set_ylabel('Pitch (MIDI semitone number)')
    fig.suptitle('Both threshold decisions survive within the original pitch vocabulary',fontweight='bold',fontsize=15,y=1.03)
    fig.text(.02,-.04,'3 distinct singleton answer vectors require at least 3 pitch symbols with fixed timing and one pitch per sample.\nThe partition attains this scoped bound; it does not retain exact values or prove human discriminability.',fontsize=10)
    fig.subplots_adjust(wspace=.14,bottom=.18)
    save(fig,'nonuniform-partition')



def decision_figure():
    import hashlib
    from echoproof.decision import decision_bound, verify_decision_comparison
    comparison_path=ROOT/'artifacts/decision-comparison/comparison.json'
    comparison=json.loads(comparison_path.read_text())
    if not verify_decision_comparison(comparison): raise ValueError('Invalid comparison figure input')
    fig,axes=plt.subplots(1,2,figsize=(13,5.5))
    annotations={'Original events':(.78,42),'Nonuniform partition':(.06,83),
                 'Conditional binary cues':(.95,68),'Fixed semantic cues':(2.02,79)}
    for name,metric in comparison['metrics'].items():
        x=float(Fraction(metric['weighted_mean_duration_ms']))/1000
        y=100*float(Fraction(metric['maximum_joint_accuracy']))
        color=GREEN if name in comparison['pareto_front'] else BLUE
        axes[0].scatter([x],[y],s=100,color=color,edgecolors='white',linewidths=1,zorder=5)
        text='%s\n%d used pitches' % (name,metric['used_pitch_count'])
        axes[0].annotate(text,(x,y),xytext=annotations[name],fontsize=10,
                         arrowprops={'arrowstyle':'-','color':'#92a6af'},ha='left',va='top')
    axes[0].set(title='Same 36 inputs: threshold + endpoint trend',xlabel='Weighted mean playback duration (seconds)',
                ylabel='Optimal joint event-decoder accuracy (%)',xlim=(0,2.85),ylim=(0,110),yticks=(0,25,50,75,100))
    mapping=Mapping(domain_high='100',pitch_step_cents=1200)
    domain={'series':[['50'],['51']],'threshold':'51'}
    samples=[]
    for i in range(21):
        mass=Fraction(i,20)
        base=decision_bound(mapping,domain,['threshold'],'51',[1-mass,mass])
        cues=decision_bound(mapping,domain,['threshold'],'51',[1-mass,mass],{'kind':'fixed_semantic_cues'})
        samples.append({'true_input_mass':str(mass),'original_maximum_accuracy':base['joint_bound']['maximum_accuracy'],
                        'cued_maximum_accuracy':cues['joint_bound']['maximum_accuracy']})
    xs=[float(Fraction(s['true_input_mass'])) for s in samples]
    for key,color,label in (('original_maximum_accuracy',ORANGE,'Original: two inputs, same events'),
                            ('cued_maximum_accuracy',GREEN,'Cued: two inputs, distinct events')):
        axes[1].plot(xs,[100*float(Fraction(s[key])) for s in samples],color=color,lw=2.5,label=label)
    axes[1].set(title='Separate two-input prior sensitivity example',xlabel='Declared mass on the threshold-true input',
                ylabel='Optimal threshold event-decoder accuracy (%)',xlim=(0,1),ylim=(0,110),yticks=(0,25,50,75,100))
    axes[1].legend(frameon=False,loc='lower center',fontsize=10)
    for ax in axes: ax.grid(color='#e4eaee',axis='y')
    fig.suptitle('Decision capability depends on the representation and the declared prior',fontweight='bold',fontsize=15,y=1.02)
    fig.text(.02,-.05,'Left: green points are Pareto candidates under accuracy, duration, AND pitch-count axes; this is not a listener recommendation.\nRight: exact finite input cases [50] and [51], threshold 51; sampled priors only. No measured human performance or natural frequency claim.',fontsize=10)
    fig.subplots_adjust(wspace=.28,bottom=.19)
    save(fig,'decision-tradeoffs')
    data={'comparison_sha256':hashlib.sha256(comparison_path.read_bytes()).hexdigest(),'comparison_metrics':comparison['metrics'],
          'prior_example':{'mapping':mapping.to_dict(),'domain':domain,'weight_order':['threshold_false_input','threshold_true_input'],'samples':samples},
          'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope':'Plot values computed from verified comparison and exact decision_bound calls. Connecting sampled prior values is illustrative; no human or population data.'}
    (OUTPUT/'decision-tradeoffs-data.json').write_text(json.dumps(data,indent=2)+'\n')



def observation_figure():
    from matplotlib.patches import FancyBboxPatch
    from echoproof.uncertainty import verify_observation_certificate
    path=ROOT/'artifacts/observation-uncertainty/ambiguous/observation.json'
    record=json.loads(path.read_text())
    if not verify_observation_certificate(record): raise ValueError('Invalid observation figure input')
    if record['reported']!=['50'] or record['admissible_intervals']!=[['499/10','501/10']] or record['threshold']!='50':
        raise ValueError('Observation figure requires the documented single-point synthetic case')
    mapping=Mapping(**record['mapping'])
    if encode(record['proof']['lower_world'],mapping)==encode(record['proof']['upper_world'],mapping):
        raise ValueError('Figure caption requires distinct directly encoded actual worlds')
    low,high=map(float,map(Fraction,record['admissible_intervals'][0]))
    threshold=float(Fraction(record['threshold']));reported=float(Fraction(record['reported'][0]))
    fig,axes=plt.subplots(1,2,figsize=(13.5,5.1))
    ax=axes[0]
    ax.plot([low,high],[1.35,1.35],color=BLUE,lw=6,solid_capstyle='butt')
    ax.scatter([low],[1.35],s=90,color=ORANGE,zorder=5)
    ax.scatter([high],[1.35],s=90,color=GREEN,zorder=5)
    ax.scatter([reported],[.55],s=100,color=INK,marker='s',zorder=5)
    ax.axvline(threshold,color=ORANGE,ls=':',lw=1.5)
    ax.text(low,1.57,'Admitted actual value\n%.1f: below threshold'%low,ha='center',va='bottom',fontsize=10)
    ax.text(high,1.57,'Admitted actual value\n%.1f: at/above threshold'%high,ha='center',va='bottom',fontsize=10)
    ax.text(reported,.35,'Reported value %.0f\nnominal answer: True'%reported,ha='center',va='top',fontsize=10)
    ax.text(threshold,1.02,'Threshold %.0f'%threshold,ha='center',va='top',fontsize=10,color=ORANGE)
    ax.set(xlim=(49.78,50.22),ylim=(0,2),yticks=(),xticks=(49.8,49.9,50,50.1,50.2),xlabel='Value in the synthetic declared example',title='Closed interval admits both actual answers')
    ax.spines['left'].set_visible(False)
    ax=axes[1];ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1),title='Both admitted worlds share this same report')
    def box(x,y,width,text,color):
        ax.add_patch(FancyBboxPatch((x-width/2,y-.12),width,.24,boxstyle='round,pad=0.012',facecolor='#f2f6f5',edgecolor=color,lw=1.5))
        ax.text(x,y,text,ha='center',va='center',fontsize=10)
    box(.13,.76,.22,'Actual 49.9\nanswer: False',ORANGE)
    box(.13,.25,.22,'Actual 50.1\nanswer: True',GREEN)
    box(.49,.50,.24,'Shared report\n50',BLUE)
    pitch=record['reported_only_outputs']['base']['events'][0]['pitch_cents']/100
    box(.84,.50,.28,'Shared events\n%.0f semitones\n+ nominal cue True'%pitch,INK)
    for start,end in (((.25,.76),(.36,.53)),((.25,.25),(.36,.47)),((.63,.50),(.69,.50))):
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','color':'#8298a3','lw':1.5})
    fig.suptitle('Uncertainty can arise before the sound mapping',fontweight='bold',fontsize=16,y=1.02)
    fig.text(.02,-.05,'Caller-declared Cartesian interval [49.9, 50.1], threshold 50. No probability or calibrated error coverage is assigned.\nThis is observation identifiability; directly encoding actual 49.9 and 50.1 in this mapping produces different events.',fontsize=10)
    fig.subplots_adjust(wspace=.16,bottom=.18)
    save(fig,'observation-identifiability')


if __name__=='__main__':
    OUTPUT.mkdir(parents=True,exist_ok=True)
    threshold_figure()
    observed_figure()
    partition_figure()
    decision_figure()
    observation_figure()
    print(OUTPUT)
