import copy
from fractions import Fraction
from itertools import product
import unittest
from echoproof.model import Mapping, encode
from echoproof.uncertainty import observation_certificate, verify_observation_certificate


class ObservationTests(unittest.TestCase):
    def setUp(self): self.mapping=Mapping(domain_high='100',pitch_step_cents=1200)

    def test_observation_loss_despite_direct_mapping_preserving_threshold(self):
        from echoproof.intervals import threshold_certificate
        self.assertEqual(threshold_certificate(self.mapping,50,0,100)['status'],'preserved')
        record=observation_certificate(self.mapping,[50],[["49.9","50.1"]],50)
        self.assertEqual(record['status'],'not_identifiable')
        self.assertEqual(record['possible_actual_answers'],[False,True])
        self.assertTrue(record['nominal_answer'])
        self.assertNotEqual(encode(record['proof']['lower_world'],self.mapping),encode(record['proof']['upper_world'],self.mapping))
        self.assertEqual(record['reported_only_outputs']['base'],encode([50],self.mapping).to_dict())
        self.assertTrue(verify_observation_certificate(record))

    def test_definite_truth_false_and_inclusive_endpoints(self):
        true=observation_certificate(self.mapping,[48,51],[[47,49],[50,52]],50)
        self.assertEqual(true['status'],'determined_true')
        self.assertEqual(true['at_or_above_count_bounds'],[1,1])
        false=observation_certificate(self.mapping,[48,49],[[47,49],[48,"49.9"]],50)
        self.assertEqual(false['status'],'determined_false')
        boundary=observation_certificate(self.mapping,[50],[[49,50]],50)
        self.assertEqual(boundary['status'],'not_identifiable')
        singleton=observation_certificate(self.mapping,[50],[[50,50]],50)
        self.assertEqual(singleton['possible_actual_answers'],[True])
        self.assertTrue(verify_observation_certificate(singleton))

    def test_declared_bias_need_not_contain_report(self):
        record=observation_certificate(self.mapping,[100],[[0,1]],50)
        self.assertTrue(record['nominal_answer'])
        self.assertEqual(record['possible_actual_answers'],[False])
        self.assertTrue(verify_observation_certificate(record))

    def test_all_endpoint_worlds_independently_match_possible_answers_and_counts(self):
        intervals=[[0,2],[1,1],[2,3],[0,0]]
        for threshold in (Fraction(-1),Fraction(0),Fraction(1),Fraction(3,2),Fraction(2),Fraction(3),Fraction(4)):
            record=observation_certificate(self.mapping,[1,1,2,0],intervals,threshold)
            answers=set();counts=[]
            for world in product(*[set(pair) for pair in intervals]):
                truths=[x>=threshold for x in world]
                answers.add(any(truths));counts.append(sum(truths))
            self.assertEqual(record['possible_actual_answers'],sorted(answers))
            self.assertEqual(record['at_or_above_count_bounds'],[min(counts),max(counts)])

    def test_mapping_changes_do_not_resolve_input_identifiability(self):
        from dataclasses import replace
        for mapping in (self.mapping,replace(self.mapping,pitch_step_cents=1),replace(self.mapping,normalization='per_series'),replace(self.mapping,stride=2)):
            record=observation_certificate(mapping,[50,49],[[49,51],[48,49]],50)
            self.assertEqual(record['status'],'not_identifiable')
            self.assertTrue(verify_observation_certificate(record))

    def test_cli_report_and_same_observed_audio_in_both_worlds(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from echoproof.cli import main
        from echoproof.report import write_observation_report
        record=observation_certificate(self.mapping,[50],[[49,51]],50)
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'report'
            path=write_observation_report(record,target)
            for kind in ('base','nominal_answer_cue'):
                self.assertEqual((target/('lower-world.reported.%s.wav'%kind)).read_bytes(),(target/('upper-world.reported.%s.wav'%kind)).read_bytes())
            self.assertIn('区间是调用方提供',path.read_text())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['verify',str(target/'observation.json')]),0)
            self.assertIn('OBSERVATION_CERTIFICATE_VERIFIED',output.getvalue())
            source=Path(directory)/'input.json'
            source.write_text(json.dumps({'reported':[50],'intervals':[[49,51]],'threshold':'50'}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['uncertain-threshold',str(source),'--out',str(Path(directory)/'cli')]),0)
            source.write_text(json.dumps({'reported':[50],'intervals':[[49,51]],'threshold':'50','confidence':0.95}))
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error: main(['uncertain-threshold',str(source)])
            self.assertEqual(error.exception.code,2)

    def test_invalid_inputs_and_typed_tampering(self):
        for reported,intervals in (([],[]),([None],[[0,1]]),([True],[[0,1]]),('50',[[0,1],[0,1]]),([50],[]),([50],[[51,49]]),([50],[[True,51]]),([50],[[49,50,51]])):
            with self.assertRaises(ValueError): observation_certificate(self.mapping,reported,intervals,50)
        record=observation_certificate(self.mapping,[50],[[49,51]],50)
        for changed in ({},None,[],True): self.assertFalse(verify_observation_certificate(changed))
        changed=copy.deepcopy(record);changed['nominal_answer']=1
        self.assertFalse(verify_observation_certificate(changed))
        changed=copy.deepcopy(record);changed['possible_actual_answers']=[0,1]
        self.assertFalse(verify_observation_certificate(changed))
        changed=copy.deepcopy(record);changed['at_or_above_count_bounds']=[False,True]
        self.assertFalse(verify_observation_certificate(changed))
        changed=copy.deepcopy(record);changed['proof']['upper_world']=['49']
        self.assertFalse(verify_observation_certificate(changed))
