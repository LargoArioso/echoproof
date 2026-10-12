from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest
from echoproof.cli import DEMOS
from echoproof.audit import audit
from echoproof.audio import wav_bytes
from echoproof.model import Mapping, encode
from echoproof.study import prepare_study, verify_study
from echoproof.study_export import write_study, check_study, render


class StudyTests(unittest.TestCase):
    def source(self):
        config=DEMOS['quantization']
        return audit(config['mapping'],config['levels'],config['lengths'],config['tasks'],config['threshold'])

    def test_seed_and_matched_cases_reproducible_with_balanced_labels(self):
        source=self.source()
        kit=prepare_study(source)
        self.assertTrue(verify_study(kit))
        self.assertEqual(kit,prepare_study(source))
        self.assertNotEqual(kit['participant_sessions'],prepare_study(source,seed=12)['participant_sessions'])
        a,b=kit['researcher_keys'].values()
        self.assertEqual([(r['case_id'],r['repetition']) for r in a],[(r['case_id'],r['repetition']) for r in b])
        for keys in (a,b):
            groups={}
            for key in keys:
                groups.setdefault(key['group_id'],Counter())[key['answer_label']]+=1
            self.assertTrue(all(len(set(counts.values()))==1 for counts in groups.values()))
        self.assertEqual(kit['statistics']['participant_results'],0)

    def test_each_ambiguous_group_has_equal_base_pcm_despite_different_answers(self):
        kit=prepare_study(self.source())
        mapping=Mapping(**kit['source_audit']['mapping'])
        for group in kit['selected_groups']:
            members=[c for c in kit['cases'] if c['group_id']==group['group_id']]
            self.assertGreater(len({c['answer_label'] for c in members}),1)
            self.assertEqual(len({wav_bytes(encode(c['values'],mapping)) for c in members}),1)
            self.assertEqual(len({wav_bytes(render(c['semantic'])) for c in members}),len(members))

    def test_participant_sheets_do_not_reveal_values_answer_or_condition(self):
        kit=prepare_study(self.source())
        for rows in kit['participant_sessions'].values():
            for row in rows:
                self.assertEqual(set(row),{'trial_id','task','prompt','choices','audio'})
        self.assertIn('does not claim participant blinding',kit['scope'])

    def test_training_and_trial_files_tampering_rejected(self):
        kit=prepare_study(self.source(),groups_per_task=1,repetitions=1)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'kit'
            write_study(kit,root)
            self.assertGreater(check_study(root)['trial_wav_verified'],0)
            training=root/'training/legend.json'
            correct=training.read_bytes()
            entries=json.loads(correct);entries[0]['answer']=True
            training.write_text(json.dumps(entries))
            with self.assertRaises(ValueError):check_study(root)
            training.write_bytes(correct)
            audio=root/kit['participant_sessions']['session-a'][0]['audio']
            audio.write_bytes(audio.read_bytes()+b'changed')
            with self.assertRaises(ValueError):check_study(root)

    def test_existing_responses_are_preserved_and_not_claimed_as_zero(self):
        kit=prepare_study(self.source(),groups_per_task=1,repetitions=1)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'kit';write_study(kit,root)
            response=root/'session-a.responses.csv'
            response.write_text('participant_id,trial_id,response,response_time_ms\np01,trial,true,1200\n')
            saved=response.read_bytes()
            with self.assertRaisesRegex(ValueError,'preserved'):write_study(kit,root)
            self.assertEqual(response.read_bytes(),saved)
            self.assertFalse(check_study(root)['participant_results_inspected'])

    def test_definition_tampering_and_large_or_unambiguous_source_rejected(self):
        kit=prepare_study(self.source())
        broken=copy.deepcopy(kit);broken['researcher_keys']['session-a'][0]['answer_label']='invented'
        self.assertFalse(verify_study(broken))
        source=self.source();source['search']['series_count']=5001
        with self.assertRaisesRegex(ValueError,'5000'):prepare_study(source)
        with self.assertRaisesRegex(ValueError,'No exact-event ambiguous'):
            prepare_study(audit(Mapping(),[0,5,10],lengths=[2],tasks=['threshold']),tasks=['threshold'])


if __name__=='__main__':
    unittest.main()
