import copy
from pathlib import Path
import tempfile
import unittest
from echoproof.model import Mapping
from echoproof.partition import partition_thresholds
from echoproof.decision import decision_bound, compare_decisions, verify_decision_comparison
from echoproof.report import write_decision_comparison


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.mapping=Mapping(domain_high='100',pitch_step_cents=1200)
        self.domain={'series':[['50'],['51']],'threshold':'51'}
        self.base=decision_bound(self.mapping,self.domain,['threshold'],'51')
        self.partition=decision_bound(self.mapping,self.domain,['threshold'],'51',representation={'kind':'threshold_partition','partition':partition_thresholds(self.mapping,[50,51],0,100)})
        self.cued=decision_bound(self.mapping,self.domain,['threshold'],'51',representation={'kind':'fixed_semantic_cues'})

    def test_exact_pareto_and_tied_candidates(self):
        record=compare_decisions({'base':self.base,'partition':self.partition,'cued':self.cued})
        self.assertEqual(record['pareto_front'],['base','partition'])
        self.assertEqual(record['dominated_by']['cued'],['partition'])
        self.assertTrue(verify_decision_comparison(record))
        tied=compare_decisions({'same1':self.base,'same2':self.base})
        self.assertEqual(tied['pareto_front'],['same1','same2'])

    def test_incomparable_scopes_and_fabricated_front_rejected(self):
        changed=decision_bound(self.mapping,self.domain,['threshold'],'51',[99,1])
        with self.assertRaises(ValueError): compare_decisions({'base':self.base,'changed_prior':changed})
        changed=decision_bound(self.mapping,{'series':[['50'],['51'],['100']],'threshold':'51'},['threshold'],'51')
        with self.assertRaises(ValueError): compare_decisions({'base':self.base,'changed_domain':changed})
        changed=decision_bound(self.mapping,self.domain,['total'],'51')
        with self.assertRaises(ValueError): compare_decisions({'base':self.base,'changed_task':changed})
        record=compare_decisions({'base':self.base,'partition':self.partition})
        record['pareto_front']=['partition']
        self.assertFalse(verify_decision_comparison(record))
        for record in ({},None,[],True): self.assertFalse(verify_decision_comparison(record))

    def test_report_names_cannot_control_paths(self):
        record=compare_decisions({'../../outside':self.base,'<script>':self.partition})
        with tempfile.TemporaryDirectory() as directory:
            path=write_decision_comparison(record,directory)
            self.assertIn('&lt;script&gt;',path.read_text())
            self.assertTrue((Path(directory)/'candidate0/decision.json').is_file())
            self.assertTrue((Path(directory)/'candidate1/decision.json').is_file())
            self.assertFalse((Path(directory)/'outside').exists())
