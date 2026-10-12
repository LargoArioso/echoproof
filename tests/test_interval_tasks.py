import copy
import unittest
from echoproof import Mapping, encode
from echoproof.audit import verify_witness
from echoproof.interval_tasks import task_certificate, verify_task_certificate
from echoproof.tasks import TASKS
from echoproof.model import number


class ContinuousTaskTests(unittest.TestCase):
    def test_fine_step_does_not_preserve_continuous_trend_peaks_or_total(self):
        mapping=Mapping(pitch_step_cents=1)
        for task in ('endpoint_trend','peak_indices','total'):
            result=task_certificate(mapping,task,0,10)
            self.assertEqual(result['status'],'collision_found')
            self.assertTrue(verify_witness(result['witness']))
            self.assertTrue(verify_task_certificate(result))

    def test_cell_construction_handles_clipped_tails_and_boundary_endpoints(self):
        mapping=Mapping(pitch_step_cents=1200)
        for low,high in ((-100,-10),(11,20),('5/3',5),(5,'25/3'),('2/3','7/3')):
            for task in ('endpoint_trend','peak_indices','total'):
                result=task_certificate(mapping,task,low,high)
                self.assertTrue(verify_task_certificate(result))
                values=result['cell']['interior_values']
                self.assertNotEqual(number(values[0]),number(values[1]))
                self.assertEqual(encode([values[0]],mapping),encode([values[1]],mapping))
                self.assertTrue(all(number(low)<=number(x)<=number(high) for x in values))

    def test_constant_quantizer_still_finds_distinct_numeric_values(self):
        result=task_certificate(Mapping(pitch_step_cents=10000),'total',0,10)
        self.assertEqual(result['status'],'collision_found')
        self.assertTrue(verify_witness(result['witness']))

    def test_singleton_input_interval_preserves_all_tasks_via_duration(self):
        for task in TASKS:
            result=task_certificate(Mapping(),task,5,5)
            self.assertEqual(result['status'],'preserved')
            self.assertTrue(verify_task_certificate(result))

    def test_no_missing_assumption_and_threshold_boundary_distinguished(self):
        mapping=Mapping(domain_high='100',pitch_step_cents=1200)
        self.assertEqual(task_certificate(mapping,'missing_count',0,100)['status'],'preserved')
        self.assertEqual(task_certificate(mapping,'threshold',0,100,50)['status'],'preserved')
        self.assertEqual(task_certificate(mapping,'threshold',0,100,51)['status'],'collision_found')

    def test_unsupported_and_tampered_certificates(self):
        for mapping in (Mapping(normalization='per_series'),Mapping(stride=2)):
            self.assertEqual(task_certificate(mapping,'total',0,10)['status'],'unsupported')
        record=task_certificate(Mapping(),'endpoint_trend',0,10)
        broken=copy.deepcopy(record)
        broken['witness']['left'][0]='999'
        self.assertFalse(verify_task_certificate(broken))
        with self.assertRaises(ValueError):
            task_certificate(Mapping(),'not-a-task',0,10)
        with self.assertRaises(ValueError):
            task_certificate(Mapping(),'total',10,0)


if __name__=='__main__':
    unittest.main()
