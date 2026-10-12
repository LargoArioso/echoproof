import copy
import json
import unittest
from echoproof import Mapping, audit, verify_audit
from echoproof.audit import audit_explicit


class AuditReplayTests(unittest.TestCase):
    def test_replays_collision_and_injective_negative_controls(self):
        for mapping in (Mapping(),Mapping(normalization='per_series'),Mapping(missing='zero')):
            record=audit(mapping,[0,5,10],lengths=[1,2],include_missing=True)
            self.assertTrue(verify_audit(record))
            reordered=json.loads(json.dumps(record,sort_keys=True))
            self.assertTrue(verify_audit(reordered))

    def test_explicit_corpus_and_source_claim_scope(self):
        record=audit_explicit(Mapping(normalization='per_series'),[[1,2],[10,20]],threshold=5,provenance={'filename':'example'})
        self.assertTrue(verify_audit(record))
        self.assertIn('explicit_corpus',record['tasks']['peak_indices']['status'])
        modified=copy.deepcopy(record)
        modified['domain']['series'].append(['1','1'])
        self.assertFalse(verify_audit(modified))

    def test_counts_absence_original_membership_and_scope_tampering(self):
        record=audit(Mapping(normalization='per_series'),[1,2,10],lengths=[2],threshold=5)
        for field in ('count','status','original','scope'):
            modified=copy.deepcopy(record)
            if field=='count':
                modified['tasks']['threshold']['disagreeing_pairs']+=1
            elif field=='status':
                modified['tasks']['threshold']['status']='preserved_for_all_real_inputs'
            elif field=='original':
                modified['tasks']['threshold']['original_witness']['left']=['1']
            else:
                modified['scope']='Works for every real input and every human listener'
            self.assertFalse(verify_audit(modified),field)

    def test_resource_limit_or_unknown_declaration_rejected(self):
        record=audit(Mapping(),[0,1],lengths=[1,2])
        modified=copy.deepcopy(record)
        modified['domain']['lengths']=[10**30]
        self.assertFalse(verify_audit(modified))
        modified=copy.deepcopy(record)
        modified['search']['mode']='sampled_but_claimed_exhaustive'
        self.assertFalse(verify_audit(modified))
        self.assertFalse(verify_audit({}))


if __name__=='__main__':
    unittest.main()
