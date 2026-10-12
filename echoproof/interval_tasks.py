"""Task preservation on a closed real interval, beyond one finite data grid."""
from .serialization import same_json
from .model import Mapping, number
from .tasks import TASKS
from .audit import witness, verify_witness
from .intervals import threshold_certificate, transitions


def task_certificate(mapping, task, input_low, input_high, threshold='5'):
    low, high, threshold = map(number, (input_low, input_high, threshold))
    if high < low:
        raise ValueError('Reversed input interval')
    if task not in TASKS:
        raise ValueError('Unsupported task')
    record = {'schema_version':1, 'claim_type':'continuous_interval_task', 'mapping':mapping.to_dict(),
              'task':task, 'input_low':str(low), 'input_high':str(high), 'threshold':str(threshold),
              'assumptions':['fixed scale','stride = 1','no missing samples','positive-length series'],
              'scope':'All positive-length original input series whose real samples lie in this closed interval under the exact EchoProof mapping. Event-level result, not an external library or human hearing proof.'}
    if mapping.normalization != 'fixed' or mapping.stride != 1:
        return dict(record,status='unsupported',reason='Require a fixed mapping and stride = 1',witness=None)
    if task == 'threshold':
        certificate = threshold_certificate(mapping, threshold, low, high)
        return dict(record,status=certificate['status'],reason=certificate['reason'],witness=certificate['witness'],threshold_certificate=certificate)
    if low == high:
        return dict(record,status='preserved',reason='There is one possible sample value. Equal render durations imply equal series lengths, and therefore equal original series and task answers.',witness=None)
    if task == 'missing_count':
        return dict(record,status='preserved',reason='No missing samples are admitted, so every missing-count answer is zero.',witness=None)
    # Pick two strict interior points of the first nonempty constant-pitch cell.
    # Strictly greater boundaries handle an input lower endpoint on a transition.
    next_boundary = next((boundary for boundary in transitions(mapping) if boundary > low), high)
    end = min(next_boundary, high)
    a, b = (2*low+end)/3, (low+2*end)/3
    if not low <= a < b <= high:
        raise AssertionError('Failed to construct a nonempty pitch-cell interval')
    if task == 'total':
        left, right = [a], [b]
    else:
        left, right = [a,b], [b,a]
    counterexample = witness(left,right,mapping,task,threshold)
    if not verify_witness(counterexample):
        raise AssertionError('Continuous task witness did not verify')
    return dict(record,status='collision_found',reason='A finite pitch quantizer has a nonempty interval with constant pitch. Two distinct values in that cell reverse trend and peak position when exchanged, or change total as singleton series.',
                cell={'lower':str(low),'upper':str(end),'interior_values':[str(a),str(b)]},witness=counterexample)


def verify_task_certificate(record):
    try:
        return same_json(record, task_certificate(Mapping(**record['mapping']),record['task'],record['input_low'],record['input_high'],record['threshold']))
    except (KeyError,TypeError,ValueError,AssertionError):
        return False
