import copy
from dataclasses import replace
import unittest
from echoproof.model import Mapping
from echoproof.diagnosis import diagnose, verify_diagnosis


class DiagnosisTests(unittest.TestCase):
    def setUp(self): self.mapping=Mapping(domain_high='100',pitch_step_cents=1200)

    def test_joint_linear_impossibility_and_partition(self):
        record=diagnose(self.mapping,[50,51],0,100)
        self.assertEqual(record['status'],'reported_mapping_collision_found')
        self.assertEqual(record['design_searches']['linear']['status'],'impossible')
        self.assertEqual(record['design_searches']['nonuniform']['status'],'preserved')
        self.assertEqual([d['kind'] for d in record['reported_mapping_designs']],['nonuniform_partition'])
        self.assertEqual(record['reported_mapping_designs'][0]['previously_preserved_thresholds_lost'],['50/3','250/3'])
        self.assertTrue(verify_diagnosis(record))

    def test_single_boundary_repair_reports_regression(self):
        record=diagnose(self.mapping,[51],0,100,reported=[50,51])
        candidate=record['reported_mapping_designs'][0]
        self.assertEqual(candidate['mapping']['domain_high'],'102')
        self.assertIn('50',candidate['previously_preserved_thresholds_lost'])
        self.assertEqual(record['nominal_answers'],{'51':True})
        joint=diagnose(self.mapping,[15,51,87],0,100)
        self.assertIn('50',joint['reported_mapping_designs'][0]['previously_preserved_thresholds_lost'])

    def test_per_series_and_sampling_source_evidence(self):
        for mapping in (replace(self.mapping,normalization='per_series'),replace(self.mapping,stride=2)):
            record=diagnose(mapping,[50],0,100)
            self.assertEqual(record['original_reported_contracts']['50']['status'],'collision_found')
            self.assertEqual(record['reported_mapping_designs'][0]['kind'],'shared_scale_and_full_sampling')
            self.assertTrue(verify_diagnosis(record))

    def test_actual_uncertainty_outweighs_nominal_designs(self):
        record=diagnose(self.mapping,[50],0,100,[50],[['49.9','50.1']],'admissible_actual')
        self.assertEqual(record['status'],'actual_answers_not_identifiable')
        self.assertEqual(record['original_reported_contracts']['50']['status'],'preserved')
        self.assertEqual(record['reported_mapping_designs'][0]['kind'],'retain_original')
        self.assertTrue(verify_diagnosis(record))
        bias=diagnose(self.mapping,[50],0,100,[100],[[0,1]],'admissible_actual')
        self.assertEqual(bias['status'],'actual_answers_determined_by_declared_intervals')
        self.assertTrue(bias['nominal_answers']['50'])
        self.assertEqual(bias['observation_certificates']['50']['possible_actual_answers'],[False])

    def test_constants_singleton_domain_and_broader_partition_cover(self):
        record=diagnose(replace(self.mapping,normalization='per_series',stride=2),[-1,101],0,100)
        self.assertEqual(record['status'],'reported_mapping_contract_preserved')
        singleton=diagnose(self.mapping,[50],50,50)
        self.assertEqual(singleton['status'],'reported_mapping_contract_preserved')
        narrow=diagnose(self.mapping,[50,51],49,51)
        self.assertEqual(narrow['design_searches']['nonuniform']['input_low'],'0')
        self.assertEqual(narrow['design_searches']['nonuniform']['input_high'],'100')

    def test_search_limit_is_not_misreported_as_impossibility(self):
        mapping=replace(self.mapping,pitch_step_cents=1)
        record=diagnose(mapping,['50.001','80.002'],0,100)
        self.assertEqual(record['design_searches']['linear']['status'],'not_searched')
        self.assertTrue(verify_diagnosis(record))

    def test_cli_roundtrip_and_report_keeps_actual_scope(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from echoproof.cli import main
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'spec.json'
            source.write_text(json.dumps({'mapping':self.mapping.to_dict(),'thresholds':[50],
                                         'reported_input_interval':[0,100],'reported':[50],
                                         'actual_intervals':[[49,51]],'question':'admissible_actual'}))
            target=Path(directory)/'report'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['diagnose',str(source),'--out',str(target)]),0)
                self.assertEqual(main(['verify',str(target/'diagnosis.json')]),0)
            self.assertIn('DIAGNOSIS_VERIFIED',output.getvalue())
            self.assertIn('当前观测无法确定',(target/'index.html').read_text())
            self.assertIn('以下映射设计只回答报告值问题',(target/'index.html').read_text())
        with self.assertRaises(ValueError): diagnose(self.mapping,'50',0,100)

    def test_invalid_scopes_and_tampering(self):
        for args in (([],0,100,None,None,'reported'),([50],0,100,[50],[[49,51]],'reported'),([50],0,100,None,None,'admissible_actual'),([50],0,100,[101],None,'reported'),([50],0,100,[None],None,'reported')):
            with self.assertRaises(ValueError): diagnose(self.mapping,*args)
        record=diagnose(self.mapping,[50,51],0,100)
        changed=copy.deepcopy(record);changed['status']='reported_mapping_contract_preserved'
        self.assertFalse(verify_diagnosis(changed))
        changed=copy.deepcopy(record);changed['reported_mapping_designs'][0]['partition']['selected_pitches_cents']=[4800,6000,8400]
        self.assertFalse(verify_diagnosis(changed))
        for bad in ({},None,[],True): self.assertFalse(verify_diagnosis(bad))
