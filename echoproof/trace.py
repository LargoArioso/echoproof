"""Replay deletion history; optionally bind it to a fully re-audited input domain."""
from .audit import witness, verify_witness, verify_audit, minimize
from .serialization import same_json
from .model import Mapping, encode
from .tasks import answer


def verify_trace(record, parent_audit=None):
    try:
        if record['claim_type']!='paired_deletion_trace' or type(record['schema_version']) is not int or record['schema_version']!=1:
            return False
        original,final=record['original'],record['final']
        if not verify_witness(original) or not verify_witness(final):
            return False
        left,right=list(original['left']),list(original['right'])
        retained_left,retained_right=list(range(len(left))),list(range(len(right)))
        mapping=Mapping(**original['mapping'])
        task,threshold=original['task'],original['threshold']
        for removed in record['removed_original_indices']:
            if type(removed) is not int or len(left)!=len(right) or len(left)<=1 or removed not in retained_left:
                return False
            index=retained_left.index(removed)
            left.pop(index);right.pop(index)
            retained_left.pop(index);retained_right.pop(index)
            if not verify_witness(witness(left,right,mapping,task,threshold)):
                return False
        if not same_json(retained_left,record['retained_left_indices']) or not same_json(retained_right,record['retained_right_indices']):
            return False
        expected=witness(left,right,mapping,task,threshold)
        if any(not same_json(final[key],value) for key,value in expected.items()):
            return False
        equal_lengths=len(left)==len(right)
        expected_label='paired-deletion 1-minimal' if equal_lengths else 'not applicable to unequal lengths'
        if final.get('minimization')!=expected_label or record['status']!=('one_minimal' if equal_lengths else 'not_applicable'):
            return False
        if equal_lengths and len(left)>1:
            for index in range(len(left)):
                a,b=left[:index]+left[index+1:],right[:index]+right[index+1:]
                if encode(a,mapping)==encode(b,mapping) and answer(a,task,threshold)!=answer(b,task,threshold):
                    return False
        # Scope and fields are fixed by the producer; there may be other valid
        # deletion orders, so compare only the canonical non-path metadata.
        _,definition=minimize(original,with_trace=True)
        if record['scope']!=definition['scope'] or set(record)!=set(definition):
            return False
        identity=record['audit_identity_sha256']
        if identity is not None and (not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity)):
            return False
        if parent_audit is not None:
            if not verify_audit(parent_audit) or identity!=parent_audit['search']['identity_sha256']:
                return False
            details=parent_audit['tasks'][task]
            if not same_json(record,details['minimization_trace']) or not same_json(original,details['original_witness']) or not same_json(final,details['witness']):
                return False
        return True
    except (KeyError,TypeError,ValueError,OverflowError,AttributeError):
        return False
