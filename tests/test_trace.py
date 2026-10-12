import copy
import unittest
from echoproof import Mapping, audit
from echoproof.audit import witness, minimize
from echoproof.trace import verify_trace


class TraceTests(unittest.TestCase):
    def test_report_does_not_claim_reduction_for_unequal_original_lengths(self):
        from echoproof.audit import audit_explicit
        from echoproof.report import report_html
        result=audit_explicit(Mapping(missing="skip"), [[1,None],[1]], tasks=["missing_count"])
        page=report_html(result)
        self.assertIn("本例不执行成对删除",page)
        self.assertNotIn("反例经过成对删除缩减",page)

    def test_cli_distinguishes_trace_steps_from_parent_domain_verification(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        from echoproof.cli import main
        parent=audit(Mapping(normalization="per_series"),[1,2,10],lengths=[2],tasks=["threshold"],threshold=5)
        trace=parent["tasks"]["threshold"]["minimization_trace"]
        with tempfile.TemporaryDirectory() as temporary:
            trace_path=Path(temporary)/"trace.json";parent_path=Path(temporary)/"audit.json"
            trace_path.write_text(json.dumps(trace));parent_path.write_text(json.dumps(parent))
            buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(main(["verify",str(trace_path)]),0)
            self.assertIn("domain membership not checked",buffer.getvalue())
            buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(main(["verify",str(trace_path),"--audit",str(parent_path)]),0)
            self.assertIn("TRACE_AND_DOMAIN_VERIFIED",buffer.getvalue())

    def test_trace_reconstructs_kept_original_positions_and_parent_membership(self):
        record=audit(Mapping(normalization='per_series'),[1,2,10],lengths=[3],tasks=['threshold'],threshold=5)
        trace=record['tasks']['threshold']['minimization_trace']
        self.assertTrue(verify_trace(trace))
        self.assertTrue(verify_trace(trace,record))
        self.assertGreater(len(trace['removed_original_indices']),0)
        original=trace['original']
        self.assertEqual(trace['final']['left'],[original['left'][i] for i in trace['retained_left_indices']])

    def test_a_valid_final_witness_does_not_validate_fabricated_deletion_history(self):
        _,trace=minimize(witness([1,2,3],[10,20,30],Mapping(normalization='per_series'),'threshold',5),with_trace=True)
        for field,value in [('removed_original_indices',[999]),('removed_original_indices',[True]),('retained_left_indices',[0,1]),('status','globally_shortest')]:
            broken=copy.deepcopy(trace);broken[field]=value
            self.assertFalse(verify_trace(broken),field)

    def test_wrong_or_tampered_parent_audit_is_rejected(self):
        parent=audit(Mapping(normalization='per_series'),[1,2,10],lengths=[2],threshold=5)
        trace=parent['tasks']['threshold']['minimization_trace']
        other=audit(Mapping(normalization='per_series'),[1,2,20],lengths=[2],threshold=5)
        self.assertFalse(verify_trace(trace,other))
        broken=copy.deepcopy(parent);broken['search']['series_count']+=1
        self.assertFalse(verify_trace(trace,broken))

    def test_final_state_must_be_one_minimal_not_merely_a_valid_collision(self):
        original=witness([1,2,3],[10,20,30],Mapping(normalization='per_series'),'threshold',5)
        _,trace=minimize(original,with_trace=True)
        trace['removed_original_indices']=[]
        trace['retained_left_indices']=[0,1,2];trace['retained_right_indices']=[0,1,2]
        trace['final']=dict(original,minimization='paired-deletion 1-minimal')
        self.assertFalse(verify_trace(trace))

    def test_unequal_length_collision_is_explicitly_not_minimized(self):
        mapping=Mapping(missing='skip')
        original=witness([1,None],[1],mapping,'missing_count',5)
        _,trace=minimize(original,with_trace=True)
        self.assertTrue(verify_trace(trace))
        self.assertEqual(trace['status'],'not_applicable')
        self.assertEqual(trace['removed_original_indices'],[])

    def test_invalid_collision_cannot_be_minimized_into_a_certificate(self):
        original=witness([1],[2],Mapping(),'total',5)
        with self.assertRaises(ValueError):
            minimize(original)


if __name__=='__main__':
    unittest.main()
