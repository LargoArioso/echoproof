import copy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest
from echoproof.model import Mapping, encode
from echoproof.contracts import threshold_contract, verify_threshold_contract
from echoproof.audit import verify_witness


class ContractTests(unittest.TestCase):
    def test_every_per_series_singleton_has_same_events(self):
        for stride in (1,2,8):
            mapping=Mapping(normalization='per_series',stride=stride)
            record=threshold_contract(mapping,5,0,10)
            self.assertEqual(record['proof_kind'],'per_series_singleton')
            self.assertEqual(record['status'],'collision_found')
            self.assertTrue(verify_witness(record['witness']))
            self.assertTrue(verify_threshold_contract(record))

    def test_stride_omission_and_endpoint(self):
        for stride in (2,3,10):
            record=threshold_contract(Mapping(stride=stride),10,0,10)
            self.assertEqual(record['proof_kind'],'omitted_sample')
            self.assertEqual(record['witness']['left'],['0','0'])
            self.assertEqual(record['witness']['right'],['0','10'])
            self.assertTrue(verify_witness(record['witness']))

    def test_constant_answers_independent_of_renderer(self):
        for normalization,stride in product(('fixed','per_series'),(1,2)):
            mapping=Mapping(normalization=normalization,stride=stride)
            for threshold,expected in ((0,True),(11,False)):
                record=threshold_contract(mapping,threshold,0,10)
                self.assertEqual(record['status'],'preserved')
                self.assertEqual(record['constant_answer'],expected)
                self.assertTrue(verify_threshold_contract(record))
        self.assertTrue(threshold_contract(Mapping(normalization='per_series'),5,5,5)['constant_answer'])

    def test_linear_component_keeps_old_scope_and_results(self):
        mapping=Mapping(domain_high='100',pitch_step_cents=1200)
        self.assertEqual(threshold_contract(mapping,50,0,100)['status'],'preserved')
        collision=threshold_contract(mapping,51,0,100)
        self.assertEqual(collision['status'],'collision_found')
        self.assertEqual(collision['proof_kind'],'linear_quantization')
        self.assertTrue(verify_threshold_contract(collision))

    def test_types_and_false_claims(self):
        record=threshold_contract(Mapping(stride=2),5,0,10)
        for key,value in (('status','preserved'),('proof_kind','constant_answer'),('constant_answer',True)):
            changed=copy.deepcopy(record);changed[key]=value
            self.assertFalse(verify_threshold_contract(changed))
        for invalid in ({},None,[],True): self.assertFalse(verify_threshold_contract(invalid))
        with self.assertRaises(ValueError): threshold_contract(Mapping(),5,10,0)
        with self.assertRaises(ValueError): threshold_contract(Mapping(),True,0,10)
