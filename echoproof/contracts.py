"""Threshold contracts over every current numeric-only Mapping variant.

Extends the narrow linear checker with constructive singleton/omission witnesses;
its existing certificate format and verifier remain unchanged.
"""
from .model import Mapping, number
from .audit import witness, verify_witness
from .intervals import threshold_certificate
from .serialization import same_json


def threshold_contract(mapping,threshold,input_low,input_high):
    threshold,low,high=map(number,(threshold,input_low,input_high))
    if high<low: raise ValueError('Reversed contract interval')
    base={'schema_version':1,'claim_type':'numeric_threshold_contract','mapping':mapping.to_dict(),
          'threshold':str(threshold),'input_low':str(low),'input_high':str(high),
          'scope':'All positive-length numeric-only series with every value in the declared closed interval. No missing samples. Exact EchoProof events and known contract interval only; no human, source authenticity, input-uncertainty or other-task claim.'}
    if threshold<=low or threshold>high:
        return dict(base,status='preserved',proof_kind='constant_answer',
                    constant_answer=threshold<=low,witness=None,linear_certificate=None)
    if mapping.normalization=='per_series':
        # Every singleton is normalized to the same midpoint, even when stride>1.
        left,right=[(low+threshold)/2],[threshold]
        proof_kind='per_series_singleton'
    elif mapping.stride>1:
        # The second position is unobserved by the renderer for every stride>1.
        left,right=[low,low],[low,threshold]
        proof_kind='omitted_sample'
    else:
        certificate=threshold_certificate(mapping,threshold,low,high)
        return dict(base,status=certificate['status'],proof_kind='linear_quantization',
                    constant_answer=None,witness=certificate['witness'],linear_certificate=certificate)
    record=witness(left,right,mapping,'threshold',threshold)
    if not verify_witness(record): raise AssertionError('Constructive contract witness failed')
    return dict(base,status='collision_found',proof_kind=proof_kind,
                constant_answer=None,witness=record,linear_certificate=None)


def verify_threshold_contract(record):
    try: return same_json(record,threshold_contract(Mapping(**record['mapping']),record['threshold'],record['input_low'],record['input_high']))
    except (KeyError,TypeError,ValueError,OverflowError): return False
