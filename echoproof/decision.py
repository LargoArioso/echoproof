"""Exact finite-prior accuracy ceiling for an ideal event-only decoder.

Standard zero-one decision theory, applied to the audited representation. This
is a counting certificate, not measured human accuracy or a distribution fit.
"""
from collections import defaultdict
from fractions import Fraction
from .model import Mapping, encode, number
from .tasks import TASKS, answer, json_answer
from .cues import domain_corpus, build_plan, CueEncoder
from .semantic_cues import SemanticCueEncoder
from .partition import PartitionEncoder
from .serialization import canonical_json, same_json

MAX_CASES = 5000


def _encoder(mapping, domain, tasks, threshold, representation):
    if not isinstance(representation,dict):
        raise ValueError('Representation must be an object')
    kind = representation.get('kind')
    if kind == 'base' and set(representation) == {'kind'}:
        return lambda values: encode(values,mapping)
    if kind == 'conditional_task_cues' and set(representation) == {'kind'}:
        return CueEncoder(build_plan(mapping,domain,tasks,threshold)).encode
    if kind == 'fixed_semantic_cues' and set(representation) == {'kind'}:
        return SemanticCueEncoder(mapping,tasks,threshold).encode
    if kind == 'threshold_partition' and set(representation) == {'kind','partition'}:
        encoder=PartitionEncoder(representation['partition'])
        if not same_json(mapping.to_dict(),encoder.mapping.to_dict()):
            raise ValueError('Partition source mapping must match the decision-bound mapping')
        return encoder.encode
    raise ValueError('Unknown representation or unsupported representation fields')


def _histogram(labels, indices, masses):
    buckets=defaultdict(list)
    for index in indices:
        buckets[canonical_json(labels[index])].append(index)
    rows=[]
    for key in sorted(buckets):
        members=buckets[key]
        rows.append({'answer':labels[members[0]],'input_count':len(members),
                     'input_mass':str(sum((masses[i] for i in members),Fraction(0)))})
    # Canonical label order resolves exact ties; zero-mass classes are harmless.
    best=max(rows,key=lambda row:number(row['input_mass']))
    return {'answers':rows,'optimal_prediction':best['answer'],'correct_mass':best['input_mass']}


def decision_bound(mapping,domain,tasks=TASKS,threshold='5',weights=None,representation=None):
    tasks=tuple(dict.fromkeys(tasks))
    if not tasks or any(t not in TASKS for t in tasks):
        raise ValueError('Require at least one supported task')
    threshold=str(number(threshold))
    if 'threshold' in domain and number(domain['threshold']) != number(threshold):
        raise ValueError('Domain and analysis thresholds must agree')
    if 'series' not in domain and type(domain.get('include_missing')) is not bool:
        raise ValueError('Grid include_missing must be a Boolean')
    if 'series' in domain:
        declared_count=len(domain['series'])
    else:
        levels=set(str(number(x)) for x in domain['levels'])
        lengths=set(domain['lengths'])
        if not lengths or any(type(n) is not int or not 1<=n<=128 for n in lengths):
            raise ValueError('Require integer lengths in 1..128')
        alphabet_size=len(levels)+(1 if domain['include_missing'] else 0)
        declared_count=sum(alphabet_size**n for n in lengths)
    if declared_count>MAX_CASES:
        raise ValueError('Decision certificate exceeds 5000 declared input cases')
    corpus=domain_corpus(domain)
    if len(corpus)>MAX_CASES:
        raise ValueError('Decision certificate exceeds 5000 distinct input cases')
    if weights is None:
        masses=(Fraction(1),)*len(corpus)
        prior={'kind':'uniform_distinct_inputs','total_mass':str(len(corpus))}
    else:
        if not isinstance(weights,(list,tuple)) or len(weights)!=len(corpus):
            raise ValueError('Weights must align with the normalized distinct input order')
        masses=tuple(number(w) for w in weights)
        if any(m<0 for m in masses) or sum(masses)<=0:
            raise ValueError('Weights must be nonnegative and have positive total mass')
        prior={'kind':'declared_rational_weights','weights':list(map(str,masses)),
               'total_mass':str(sum(masses))}
    total=sum(masses)
    representation={'kind':'base'} if representation is None else representation
    renderer=_encoder(mapping,domain,tasks,threshold,representation)
    groups=defaultdict(list)
    renders={}
    task_labels={t:[] for t in tasks}
    joint_labels=[]
    weighted_duration=Fraction(0)
    maximum_duration=0
    pitch_vocabulary=set()
    for index,values in enumerate(corpus):
        rendered=renderer(values)
        signature=canonical_json(rendered.to_dict())
        groups[signature].append(index);renders[signature]=rendered.to_dict()
        labels=[json_answer(answer(values,t,threshold)) for t in tasks]
        for t,label in zip(tasks,labels): task_labels[t].append(label)
        joint_labels.append(labels)
        weighted_duration+=masses[index]*rendered.duration_ms
        maximum_duration=max(maximum_duration,rendered.duration_ms)
        pitch_vocabulary.update(e.pitch_cents for e in rendered.events)
    classes=[]
    correct={t:Fraction(0) for t in tasks}
    joint_correct=Fraction(0)
    for signature in sorted(groups):
        indices=groups[signature]
        table={t:_histogram(task_labels[t],indices,masses) for t in tasks}
        joint=_histogram(joint_labels,indices,masses)
        for t in tasks: correct[t]+=number(table[t]['correct_mass'])
        joint_correct+=number(joint['correct_mass'])
        classes.append({'render':renders[signature],'input_indices':indices,
                        'input_mass':str(sum(masses[i] for i in indices)),
                        'tasks':table,'joint':joint})
    def summary(labels,correct_mass):
        baseline=_histogram(labels,range(len(corpus)),masses)
        return {'maximum_correct_mass':str(correct_mass),
                'minimum_error_mass':str(total-correct_mass),
                'maximum_accuracy':str(correct_mass/total),
                'minimum_error_probability':str((total-correct_mass)/total),
                'no_event_maximum_accuracy':str(number(baseline['correct_mass'])/total),
                'no_event_optimal_prediction':baseline['optimal_prediction']}
    return {'schema_version':1,'claim_type':'finite_prior_decision_bound',
            'mapping':mapping.to_dict(),'domain':domain,'tasks':list(tasks),'threshold':threshold,
            'representation':representation,'prior':prior,'classes':classes,
            'statistics':{'distinct_inputs':len(corpus),'render_classes':len(classes),'zero_mass_inputs':sum(m==0 for m in masses),
                          'positive_mass_render_classes':sum(number(c['input_mass'])>0 for c in classes),
                          'weighted_mean_duration_ms':str(weighted_duration/total),
                          'maximum_duration_ms':maximum_duration,'pitch_vocabulary_cents':sorted(pitch_vocabulary)},
            'task_bounds':{t:summary(task_labels[t],correct[t]) for t in tasks},
            'joint_bound':summary(joint_labels,joint_correct),
            'proof':'An event-only decoder must choose one label per render class. It can correctly cover at most the largest label mass in that class; the saved majority-label lookup attains this. Sum those maxima and divide by the declared total mass. Randomization cannot improve zero-one expected accuracy.',
            'scope':'Exact optimum under the declared finite input prior and exact events, with no input identity, dates, numeric labels or other side information. Uniform distinct-input weights are a chosen analysis assumption, not observed population frequencies. Weighted priors are caller declarations, not estimated probabilities. Joint score requires all listed answers correct together. Zero-weight inputs do not affect accuracy, so perfect accuracy does not certify their recoverability. No source authenticity, human accuracy, hearing model, training benefit or held-out generalization claim.'}


def verify_decision_bound(record):
    try:
        prior=record['prior']
        if prior['kind']=='uniform_distinct_inputs': weights=None
        elif prior['kind']=='declared_rational_weights': weights=prior['weights']
        else: return False
        expected=decision_bound(Mapping(**record['mapping']),record['domain'],record['tasks'],record['threshold'],weights,record['representation'])
        return same_json(expected,record)
    except (KeyError,TypeError,ValueError,OverflowError):
        return False


def compare_decisions(records):
    if not isinstance(records,dict) or not 2<=len(records)<=8 or any(not isinstance(k,str) or not k for k in records):
        raise ValueError('Require 2..8 named decision certificates')
    for record in records.values():
        if not verify_decision_bound(record): raise ValueError('Invalid decision comparison candidate')
    common_fields=('mapping','domain','tasks','threshold','prior')
    first=next(iter(records.values()))
    if any(not same_json({k:r[k] for k in common_fields},{k:first[k] for k in common_fields}) for r in records.values()):
        raise ValueError('Comparison requires identical mapping, domain, tasks and prior')
    metrics={name:{'maximum_joint_accuracy':r['joint_bound']['maximum_accuracy'],
                   'weighted_mean_duration_ms':r['statistics']['weighted_mean_duration_ms'],
                   'used_pitch_count':len(r['statistics']['pitch_vocabulary_cents'])} for name,r in records.items()}
    dominated={name:[] for name in records}
    for name,b in metrics.items():
        for other,a in metrics.items():
            if other==name: continue
            weak=(number(a['maximum_joint_accuracy'])>=number(b['maximum_joint_accuracy']) and
                  number(a['weighted_mean_duration_ms'])<=number(b['weighted_mean_duration_ms']) and
                  a['used_pitch_count']<=b['used_pitch_count'])
            strict=any(a[k]!=b[k] for k in ('maximum_joint_accuracy','weighted_mean_duration_ms','used_pitch_count'))
            if weak and strict: dominated[name].append(other)
        dominated[name].sort()
    return {'schema_version':1,'claim_type':'finite_prior_decision_comparison','candidates':records,
            'metrics':metrics,'dominated_by':dominated,'pareto_front':sorted(n for n,d in dominated.items() if not d),
            'scope':'Same declared finite domain, prior and answers for every candidate. Pareto axes are ideal joint accuracy (maximize), weighted playback duration and count of pitches used in that domain (minimize). These chosen engineering axes are not measured cognitive load, audibility, aesthetic quality or a recommendation. Source mapping is shared; candidate representation rules may change.'}


def verify_decision_comparison(record):
    try: return same_json(record,compare_decisions(record['candidates']))
    except (KeyError,TypeError,ValueError,OverflowError): return False
