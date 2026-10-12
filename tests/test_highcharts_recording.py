import copy
import unittest
from echoproof.compiled import project, audit_compiled, verify_recording_witness

SCOPE = 'highcharts_mapped_instrument'


class HighchartsRecordingTests(unittest.TestCase):
    def setUp(self):
        self.a = {'input':[50], 'events':[{'time':0,'instrumentEventOptions':{'note':72,'volume':0.2,'pan':0,'noteDuration':180}}]}
        self.b = dict(copy.deepcopy(self.a), input=[51])

    def test_identical_parameters_different_input_threshold(self):
        corpus = {'backend':{'name':'mapping harness, partial'},'records':[self.a,self.b]}
        result = audit_compiled(corpus, SCOPE, ['threshold'],51)
        witness = result['tasks']['threshold']['witness']
        self.assertTrue(verify_recording_witness(witness))
        self.assertEqual(result['tasks']['threshold']['disagreeing_pairs'],1)
        self.assertIn('partial',witness['scope'])

    def test_all_parameters_retained(self):
        self.b['events'][0]['instrumentEventOptions']['pan'] = 0.1
        result = audit_compiled({'backend':{},'records':[self.a,self.b]}, SCOPE, ['threshold'],51)
        self.assertEqual(result['projection_classes'],2)
        self.assertEqual(result['tasks']['threshold']['disagreeing_pairs'],0)

    def test_time_order_and_future_parameters_not_silently_erased(self):
        self.a['events'][0]['instrumentEventOptions']['futureParameter'] = {'gain':0.5}
        projection = project(self.a,SCOPE)
        self.assertEqual(projection,self.a['events'])
        projection[0]['instrumentEventOptions']['note'] = 80
        self.assertEqual(self.a['events'][0]['instrumentEventOptions']['note'],72)

    def test_unknown_outer_event_or_invalid_numeric_rejected(self):
        for change in ({'time':-1},{'time':True},{'time':float('nan')},{'unrecognizedMetadata':5},{'instrumentEventOptions':[]}):
            broken = copy.deepcopy(self.a)
            broken['events'][0].update(change)
            with self.assertRaises(ValueError):
                project(broken,SCOPE)

    def test_full_queue_scope_cannot_be_substituted_for_partial(self):
        with self.assertRaises(KeyError):
            project(self.a,'erie_full_queue')
        record = audit_compiled({'backend':{},'records':[self.a,self.b]},SCOPE,['threshold'],51)['tasks']['threshold']['witness']
        record['audit_scope'] = 'erie_full_queue'
        self.assertFalse(verify_recording_witness(record))


if __name__=='__main__':
    unittest.main()
