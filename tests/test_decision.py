import copy
from fractions import Fraction
from itertools import product
import unittest
from echoproof.decision import decision_bound, verify_decision_bound
from echoproof.model import Mapping, encode
from echoproof.partition import partition_thresholds
from echoproof.tasks import answer


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.mapping=Mapping(domain_high='100',pitch_step_cents=1200)
        self.domain={'series':[['50'],['51']],'threshold':'51'}

    def test_collision_versus_injective_and_no_event_baseline(self):
        record=decision_bound(self.mapping,self.domain,['threshold'],'51')
        self.assertEqual(record['task_bounds']['threshold']['maximum_accuracy'],'1/2')
        self.assertEqual(record['joint_bound']['minimum_error_mass'],'1')
        self.assertEqual(record['statistics']['render_classes'],1)
        self.assertTrue(verify_decision_bound(record))
        distinct=decision_bound(Mapping(domain_high='100',pitch_step_cents=10),self.domain,['threshold'],'51')
        self.assertEqual(distinct['joint_bound']['maximum_accuracy'],'1')
        self.assertEqual(distinct['joint_bound']['no_event_maximum_accuracy'],'1/2')

    def test_prior_changes_weighted_bound_without_changing_events(self):
        record=decision_bound(self.mapping,self.domain,['threshold'],'51',[99,1])
        self.assertEqual(record['joint_bound']['maximum_accuracy'],'99/100')
        self.assertEqual(record['joint_bound']['minimum_error_mass'],'1')
        self.assertFalse(record['classes'][0]['tasks']['threshold']['optimal_prediction'])
        zero=decision_bound(self.mapping,self.domain,['threshold'],'51',[0,1])
        self.assertEqual(zero['joint_bound']['maximum_accuracy'],'1')
        self.assertTrue(verify_decision_bound(zero))

    def test_cue_and_partition_repairs(self):
        for representation in ({'kind':'conditional_task_cues'},{'kind':'fixed_semantic_cues'},
                               {'kind':'threshold_partition','partition':partition_thresholds(self.mapping,[50,51],0,100)}):
            record=decision_bound(self.mapping,self.domain,['threshold'],'51',representation=representation)
            self.assertEqual(record['joint_bound']['maximum_accuracy'],'1')
            self.assertTrue(verify_decision_bound(record))
        base=decision_bound(self.mapping,self.domain,['threshold'],'51')
        cued=decision_bound(self.mapping,self.domain,['threshold'],'51',representation={'kind':'fixed_semantic_cues'})
        self.assertGreater(Fraction(cued['statistics']['weighted_mean_duration_ms']),Fraction(base['statistics']['weighted_mean_duration_ms']))

    def test_exhaustive_all_decoder_policies_independent_of_majority_formula(self):
        values=[['0'],['49'],['50'],['51'],['100']]
        weights=[1,2,3,4,5]
        domain={'series':values,'threshold':'51'}
        groups={}
        for index,v in enumerate(values): groups.setdefault(encode(v,self.mapping),[]).append(index)
        ordered=list(groups.values())
        best=0
        # Every deterministic policy assigning a true/false prediction to each
        # observed event class. Score individual inputs without histograms.
        for policy in product([False,True],repeat=len(ordered)):
            score=sum(weights[i] for prediction,members in zip(policy,ordered) for i in members if prediction==answer(values[i],'threshold','51'))
            best=max(best,score)
        record=decision_bound(self.mapping,domain,['threshold'],'51',weights)
        self.assertEqual(Fraction(record['joint_bound']['maximum_accuracy']),Fraction(best,sum(weights)))

    def test_joint_answer_differs_from_individual_accuracy(self):
        domain={'series':[['50','50.5'],['50.5','50'],['50.5','51'],['51','50.5']],'threshold':'51'}
        record=decision_bound(self.mapping,domain,['threshold','endpoint_trend'],'51')
        self.assertEqual(record['joint_bound']['maximum_accuracy'],'1/4')
        self.assertEqual(record['task_bounds']['threshold']['maximum_accuracy'],'1/2')
        self.assertEqual(record['task_bounds']['endpoint_trend']['maximum_accuracy'],'1/2')
        self.assertEqual(record['statistics']['render_classes'],1)
        for row in record['classes']:
            self.assertEqual(sum(Fraction(a['input_mass']) for a in row['joint']['answers']),Fraction(row['input_mass']))

    def test_zero_mass_classes_and_constant_answers(self):
        domain={'series':[['0'],['100']],'threshold':'200'}
        record=decision_bound(self.mapping,domain,['threshold','missing_count'],'200',[1,0])
        self.assertEqual(record['statistics']['positive_mass_render_classes'],1)
        self.assertEqual(record['joint_bound']['maximum_accuracy'],'1')
        self.assertEqual(record['joint_bound']['no_event_maximum_accuracy'],'1')
        self.assertTrue(verify_decision_bound(record))

    def test_cli_certificate_and_report_roundtrip(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from echoproof.audit import audit_explicit
        from echoproof.cli import main
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'audit.json'
            source.write_text(json.dumps(audit_explicit(self.mapping,[['50'],['51']],tasks=['threshold'],threshold='51')))
            target=Path(directory)/'report'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['decision-bound',str(source),'--out',str(target)]),0)
                self.assertEqual(main(['verify',str(target/'decision.json')]),0)
            self.assertIn('DECISION_BOUND_VERIFIED',output.getvalue())
            self.assertIn('50.00%',(target/'index.html').read_text())
            self.assertIn('不是参与者成绩',(target/'index.html').read_text())

    def test_size_limit_and_representation_types(self):
        with self.assertRaises(ValueError):
            decision_bound(self.mapping,{'levels':['0','1'],'lengths':[13],'include_missing':False},['threshold'])
        for representation in ([],1,'base'):
            record=decision_bound(self.mapping,self.domain,['threshold'],'51')
            record['representation']=representation
            self.assertFalse(verify_decision_bound(record))
        for invalid in ({},None,[],True): self.assertFalse(verify_decision_bound(invalid))

    def test_tampering_and_rejections(self):
        record=decision_bound(self.mapping,self.domain,['threshold'],'51')
        for key,value in [('maximum_accuracy','1'),('minimum_error_mass',True)]:
            changed=copy.deepcopy(record);changed['joint_bound'][key]=value
            self.assertFalse(verify_decision_bound(changed))
        changed=copy.deepcopy(record);changed['classes'][0]['tasks']['threshold']['optimal_prediction']=0
        self.assertFalse(verify_decision_bound(changed))
        for weights in ([1],[-1,2],[0,0],[True,1],'11'):
            with self.assertRaises(ValueError): decision_bound(self.mapping,self.domain,['threshold'],'51',weights)
        for representation in ({'kind':'unknown'},{'kind':'base','ignored':1}):
            with self.assertRaises(ValueError): decision_bound(self.mapping,self.domain,['threshold'],'51',representation=representation)
        with self.assertRaises(ValueError): decision_bound(self.mapping,self.domain,['threshold'],'50')
        with self.assertRaises(ValueError): decision_bound(self.mapping,self.domain,['total'],'51',representation={'kind':'fixed_semantic_cues'})
        with self.assertRaises(ValueError): decision_bound(self.mapping,{'levels':['0'],'lengths':[1],'include_missing':1},['total'])


if __name__=='__main__': unittest.main()
