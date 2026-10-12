"""Threshold identifiability from a reported sequence and declared feasible set.

The admissible actual states share the same report. This is observation
identifiability, not an assertion that directly encoding actual states collides.
"""
from .model import Mapping, number, series, encode
from .tasks import answer
from .semantic_cues import SemanticCueEncoder
from .serialization import same_json


def observation_certificate(mapping, reported, intervals, threshold):
    if not isinstance(reported,(list,tuple)) or not 1<=len(reported)<=128:
        raise ValueError('Require 1..128 reported samples')
    values=series(reported)
    if any(x is None for x in values): raise ValueError('Reported samples must be observed numeric values')
    if not isinstance(intervals,(list,tuple)) or len(intervals)!=len(values):
        raise ValueError('One declared interval per reported sample is required')
    bounds=[]
    for pair in intervals:
        if not isinstance(pair,(list,tuple)) or len(pair)!=2:
            raise ValueError('Each interval must have two endpoints')
        low,high=map(number,pair)
        if low>high: raise ValueError('Interval endpoints must ascend or coincide')
        bounds.append((low,high))
    threshold=number(threshold)
    lower=tuple(low for low,high in bounds)
    upper=tuple(high for low,high in bounds)
    lower_answer=answer(lower,'threshold',threshold)
    upper_answer=answer(upper,'threshold',threshold)
    possible=[lower_answer] if lower_answer==upper_answer else [False,True]
    status='not_identifiable' if len(possible)==2 else 'determined_true' if possible[0] else 'determined_false'
    base=encode(values,mapping)
    cue=SemanticCueEncoder(mapping,['threshold'],threshold).encode(values)
    return {'schema_version':1,'claim_type':'interval_observation_identifiability','task':'threshold',
            'mapping':mapping.to_dict(),'reported':list(map(str,values)),
            'admissible_intervals':[[str(low),str(high)] for low,high in bounds],
            'threshold':str(threshold),'nominal_answer':answer(values,'threshold',threshold),
            'possible_actual_answers':possible,'status':status,
            'at_or_above_count_bounds':[sum(low>=threshold for low,high in bounds),sum(high>=threshold for low,high in bounds)],
            'proof':{'lower_world':list(map(str,lower)),'upper_world':list(map(str,upper)),
                     'lower_world_answer':lower_answer,'upper_world_answer':upper_answer,
                     'rule':'The threshold-any predicate is coordinatewise monotone. The lower and upper endpoint worlds attain the minimum and maximum Boolean answers; both are admitted by the closed Cartesian feasible set. No probability is assigned.'},
            'reported_only_outputs':{'base':base.to_dict(),'nominal_answer_cue':cue.to_dict()},
            'assumptions':'The caller declares that all and only the Cartesian-product interval states are admissible for this same complete reported observation. No missing actual or reported samples. Reported values need not lie in actual-value intervals (e.g. a declared bias). No unstated correlations, probability model, calibrated coverage or data-source authenticity is assumed.',
            'scope':'Question is whether an actual admitted state contains a value at or above the threshold. Nominal answer concerns reported values only. If both actual answers are possible, any deterministic representation using only this same report and feasible set has the same output in the two endpoint worlds and cannot identify their actual Boolean answer. A representation may instead convey uncertainty. This is not an exact-render-collision claim about directly encoding the two actual worlds. Fixed answer cues remain correct for nominal data; they do not supply unknown actual values. No human hearing, confidence percentage, exposure duration or risk claim.'}


def verify_observation_certificate(record):
    try:
        return same_json(record,observation_certificate(Mapping(**record['mapping']),record['reported'],record['admissible_intervals'],record['threshold']))
    except (KeyError,TypeError,ValueError,OverflowError): return False
