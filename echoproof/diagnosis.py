"""One scoped entry point for observation, mapping and threshold repair evidence."""
from dataclasses import replace
from .model import Mapping, number, series
from .contracts import threshold_contract
from .alignment import align_threshold
from .multi_alignment import align_thresholds
from .partition import partition_thresholds
from .uncertainty import observation_certificate
from .tasks import answer
from .intervals import transitions
from .serialization import same_json


def diagnose(mapping,thresholds,input_low,input_high,reported=None,actual_intervals=None,question='reported'):
    if not isinstance(thresholds,(list,tuple)):
        raise ValueError('Thresholds must be an array')
    thresholds=sorted(set(number(t) for t in thresholds))
    if not 1<=len(thresholds)<=16: raise ValueError('Require 1..16 distinct thresholds')
    low,high=number(input_low),number(input_high)
    if high<low: raise ValueError('Reversed reported input interval')
    if question not in ('reported','admissible_actual'): raise ValueError('Unknown question kind')
    if question=='reported' and actual_intervals is not None:
        raise ValueError('Actual intervals require question = admissible_actual')
    if question=='admissible_actual' and (reported is None or actual_intervals is None):
        raise ValueError('Actual question requires reported samples and declared intervals')
    if reported is not None:
        if not isinstance(reported,(list,tuple)) or not 1<=len(reported)<=128:
            raise ValueError('Require 1..128 reported samples')
        values=series(reported)
        if any(x is None or not low<=x<=high for x in values):
            raise ValueError('Reported samples must be numeric and inside the reported contract interval')
        reported=list(map(str,values))
    contracts={str(t):threshold_contract(mapping,t,low,high) for t in thresholds}
    nominal={str(t):answer(reported,'threshold',t) for t in thresholds} if reported is not None else None
    observations={str(t):observation_certificate(mapping,reported,actual_intervals,t) for t in thresholds} if question=='admissible_actual' else None
    if observations:
        actual_intervals=next(iter(observations.values()))['admissible_intervals']
    original_ok=all(c['status']=='preserved' for c in contracts.values())
    seed=replace(mapping,normalization='fixed',stride=1)
    seed_changes=[name for name in ('normalization','stride') if getattr(seed,name)!=getattr(mapping,name)]
    old_boundaries=[t for t in transitions(mapping) if low<t<=high] if mapping.normalization=='fixed' and mapping.stride==1 else []
    designs=[];searches={}
    if original_ok:
        designs.append({'kind':'retain_original','mapping':mapping.to_dict(),'changed_fields':[],
                        'contracts':contracts,'previously_preserved_thresholds_lost':[]})
    else:
        seed_contracts={str(t):threshold_contract(seed,t,low,high) for t in thresholds}
        if all(c['status']=='preserved' for c in seed_contracts.values()):
            designs.append({'kind':'shared_scale_and_full_sampling','mapping':seed.to_dict(),
                            'changed_fields':seed_changes,'contracts':seed_contracts,'previously_preserved_thresholds_lost':[]})
        else:
            active=[t for t in thresholds if low<t<=high]
            try:
                if len(active)==1:
                    linear=align_threshold(seed,active[0],low,high,limit=3)
                else:
                    linear=align_thresholds(seed,active,low,high,limit=3)
                searches['linear']=linear
                for candidate in linear['candidates']:
                    revised=Mapping(**candidate['mapping'])
                    checks={str(t):threshold_contract(revised,t,low,high) for t in thresholds}
                    if not all(c['status']=='preserved' for c in checks.values()):
                        raise AssertionError('Joint repair failed a requested contract')
                    changes=[name for name in mapping.to_dict() if mapping.to_dict()[name]!=revised.to_dict()[name]]
                    # The alignment's regression list concerns its fixed/stride-one
                    # seed. Only that same original source had those guarantees.
                    revised_boundaries=set(transitions(revised))
                    lost=[str(t) for t in old_boundaries if t not in revised_boundaries]
                    designs.append({'kind':'linear_range_alignment','mapping':revised.to_dict(),'changed_fields':changes,
                                    'contracts':checks,'previously_preserved_thresholds_lost':lost,
                                    'regression_scope':'Declared reported interval; original fixed stride-one transition thresholds only. Other tasks are not checked.'})
            except ValueError as exc:
                searches['linear']={'status':'not_searched','reason':str(exc)}
        # Broader construction interval explicitly retains original range coverage.
        covered_low=min(low,number(seed.domain_low));covered_high=max(high,number(seed.domain_high))
        partition=partition_thresholds(seed,thresholds,covered_low,covered_high)
        searches['nonuniform']=partition
        if partition['status']=='preserved':
            designs.append({'kind':'nonuniform_partition','partition':partition,'changed_fields':seed_changes+['value_to_pitch_geometry'],
                            'previously_preserved_thresholds_lost':[str(t) for t in old_boundaries if str(t) not in partition['cutpoints']],
                            'scope':'Preserves every requested reported threshold over the constructor interval covering the source range and reported contract. Does not certify trend, exact values or actual-value identifiability.'})
    if question=='admissible_actual':
        status='actual_answers_not_identifiable' if any(c['status']=='not_identifiable' for c in observations.values()) else 'actual_answers_determined_by_declared_intervals'
    else:
        status='reported_mapping_contract_preserved' if original_ok else 'reported_mapping_collision_found'
    return {'schema_version':1,'claim_type':'threshold_diagnosis','mapping':mapping.to_dict(),
            'thresholds':list(map(str,thresholds)),'reported_input_low':str(low),'reported_input_high':str(high),
            'question':question,'reported':reported,'actual_intervals':actual_intervals,
            'status':status,'nominal_answers':nominal,'observation_certificates':observations,
            'original_reported_contracts':contracts,'reported_mapping_designs':designs,'design_searches':searches,
            'scope':'Diagnosis separates actual-value identifiability for this reported observation from numeric-only reported-value mapping contracts over all positive-length input series. Designs concern reported values only, even when the selected primary question is actual. Unknown actual answers require further information or an uncertainty response, not a nominal answer cue. Linear families, pitch-alphabet capacity and constructor coverage are explicit restrictions; no global design optimum, automatic selection, human hearing, source authenticity, probability, missing-data or non-threshold-task claim.'}


def verify_diagnosis(record):
    try:
        expected=diagnose(Mapping(**record['mapping']),record['thresholds'],record['reported_input_low'],record['reported_input_high'],record['reported'],record['actual_intervals'],record['question'])
        return same_json(record,expected)
    except (KeyError,TypeError,ValueError,OverflowError): return False
