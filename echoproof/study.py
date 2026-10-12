"""Prepare matched task-answer stimuli; no participant results are generated."""
from collections import defaultdict
import hashlib
import json
import random
from .audit import verify_audit
from .audio import wav_bytes
from .cues import domain_corpus
from .model import Mapping, encode
from .semantic_cues import SemanticCueEncoder, SUPPORTED
from .serialization import canonical_json, same_json
from .tasks import answer

MAX_STUDY_SOURCE = 5000


def label_key(value):
    return str(value).lower() if isinstance(value,bool) else value


def prepare_study(source, tasks=SUPPORTED, groups_per_task=2, repetitions=2, seed=20261012):
    if source['search']['series_count'] > MAX_STUDY_SOURCE:
        raise ValueError('Study preparation accepts at most 5000 source series')
    if not verify_audit(source):
        raise ValueError('Study source must be a completely verified finite EchoProof audit')
    tasks=tuple(dict.fromkeys(tasks))
    if not tasks or any(t not in SUPPORTED or t not in source['tasks'] for t in tasks):
        raise ValueError('Choose threshold/trend tasks present in the source audit')
    if type(groups_per_task) is not int or not 1<=groups_per_task<=4 or type(repetitions) is not int or not 1<=repetitions<=8:
        raise ValueError('Require 1..4 groups per task and 1..8 repetitions')
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError('Seed must be an unsigned 32-bit integer')
    mapping=Mapping(**source['mapping'])
    threshold=source['domain']['threshold']
    corpus=domain_corpus(source['domain'])
    selected=[]
    cases=[]
    for task in tasks:
        buckets=defaultdict(dict)
        renders={}
        for values in corpus:
            rendered=encode(values,mapping)
            signature=canonical_json(rendered.to_dict())
            renders[signature]=rendered
            buckets[signature].setdefault(label_key(answer(values,task,threshold)),list(values))
        ambiguous=[signature for signature in buckets if len(buckets[signature])>1]
        if not ambiguous:
            raise ValueError('No exact-event ambiguous group for study task '+task)
        ambiguous.sort(key=lambda signature:(-len(buckets[signature]),signature))
        repertoire=set(buckets[ambiguous[0]])
        compatible=[signature for signature in ambiguous if set(buckets[signature])==repertoire][:groups_per_task]
        for group_index,signature in enumerate(compatible):
            group_id=task+'-'+str(group_index)
            selected.append({'group_id':group_id,'task':task,'answer_labels':sorted(repertoire),
                             'base_render':renders[signature].to_dict(),
                             'base_wav_sha256':hashlib.sha256(wav_bytes(renders[signature])).hexdigest()})
            for label in sorted(repertoire):
                values=buckets[signature][label]
                cued=SemanticCueEncoder(mapping,tasks=(task,),threshold=threshold).encode(values)
                cases.append({'case_id':'case-'+str(len(cases)),'group_id':group_id,'task':task,'values':values,
                              'expected_answer':answer(values,task,threshold),'answer_label':label,
                              'base':renders[signature].to_dict(),'semantic':cued.to_dict(),
                              'semantic_wav_sha256':hashlib.sha256(wav_bytes(cued)).hexdigest()})
    rng=random.Random(seed)
    order=[(case_index,repetition) for case_index in range(len(cases)) for repetition in range(repetitions)]
    rng.shuffle(order)
    assignment={'session-a':'base','session-b':'semantic'}
    if rng.getrandbits(1):
        assignment={'session-a':'semantic','session-b':'base'}
    sessions={}
    keys={}
    used_trial_ids=set()
    for session,condition in assignment.items():
        rows=[];private=[]
        for case_index,repetition in order:
            case=cases[case_index]
            trial_id='%016x'%rng.getrandbits(64)
            while trial_id in used_trial_ids:
                trial_id='%016x'%rng.getrandbits(64)
            used_trial_ids.add(trial_id)
            prompt=('序列里是否至少有一个数值达到 '+str(threshold)+'？') if case['task']=='threshold' else '首尾已观测数值的趋势是什么？'
            choices=['false','true'] if case['task']=='threshold' else ['falling','flat','rising','undefined']
            rows.append({'trial_id':trial_id,'task':case['task'],'prompt':prompt,'choices':choices,
                         'audio':'audio/'+trial_id+'.wav'})
            private.append({'trial_id':trial_id,'case_id':case['case_id'],'group_id':case['group_id'],
                            'repetition':repetition,'condition':condition,'expected_answer':case['expected_answer'],
                            'answer_label':case['answer_label']})
        sessions[session]=rows;keys[session]=private
    return {'schema_version':1,'claim_type':'matched_study_materials','source_audit':source,
            'parameters':{'tasks':list(tasks),'groups_per_task':groups_per_task,'repetitions':repetitions,'seed':seed},
            'selected_groups':selected,'cases':cases,'participant_sessions':sessions,'researcher_keys':keys,
            'session_assignment':assignment,
            'statistics':{'source_series':len(corpus),'selected_groups':len(selected),'cases':len(cases),
                          'trials_per_session':len(order),'balanced_within_each_group':True,
                          'participant_results':0},
            'scope':'Preparation only. Sessions have matched original cases and order; one condition per participant avoids switching-condition carryover by design. Each group has equal repetitions per task answer and byte-identical base WAV. Participant sheets omit case values, expected answers and condition labels; cue availability is audible, so this does not claim participant blinding. No human outcome, effect size, power or perceptual benefit is established.'}


def verify_study(record):
    try:
        return same_json(record,prepare_study(record['source_audit'],**record['parameters']))
    except (KeyError,TypeError,ValueError,OverflowError,AttributeError):
        return False
