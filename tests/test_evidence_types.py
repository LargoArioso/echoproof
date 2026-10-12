import copy
import unittest
from echoproof import Mapping, audit, verify_audit, verify_witness
from echoproof.audit import witness
from echoproof.intervals import threshold_certificate, verify_threshold_certificate
from echoproof.compiled import recording_witness, verify_recording_witness
from echoproof.serialization import same_json


class EvidenceTypeTests(unittest.TestCase):
    def test_json_semantics_do_not_treat_boolean_and_number_as_same(self):
        self.assertFalse(same_json(True,1))
        self.assertFalse(same_json(False,0))
        self.assertTrue(same_json({'a':1,'b':True},{'b':True,'a':1}))
        self.assertFalse(same_json(float('nan'),float('nan')))

    def test_answer_and_integral_event_type_tampering_rejected(self):
        original=witness([1],[10],Mapping(normalization='per_series'),'threshold',5)
        self.assertTrue(verify_witness(original))
        broken=copy.deepcopy(original);broken['right_answer']=1
        self.assertFalse(verify_witness(broken))
        broken=copy.deepcopy(original);broken['render']['events'][0]['duration_ms']=180.0
        self.assertFalse(verify_witness(broken))

    def test_false_count_and_true_schema_are_not_accepted_as_zero_and_one(self):
        result=audit(Mapping(),[0,5,10],lengths=[1])
        broken=copy.deepcopy(result);broken['search']['collision_classes']=False
        self.assertFalse(verify_audit(broken))
        certificate=threshold_certificate(Mapping(),5,0,10)
        certificate['schema_version']=True
        self.assertFalse(verify_threshold_certificate(certificate))

    def test_recorded_parameters_cannot_be_retyped_to_equivalent_python_values(self):
        event={'time':0,'instrumentEventOptions':{'note':72,'pan':0}}
        left={'input':[50],'events':[event]}
        right={'input':[51],'events':[copy.deepcopy(event)]}
        record=recording_witness(left,right,{},'highcharts_mapped_instrument','threshold',51)
        self.assertTrue(verify_recording_witness(record))
        record['right']['events'][0]['instrumentEventOptions']['pan']=False
        self.assertFalse(verify_recording_witness(record))


if __name__=='__main__':
    unittest.main()
