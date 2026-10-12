import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from real_data_partition import create_record, verify_record, direct_profiles
from echoproof.model import encode, Mapping
from echoproof.partition import PartitionEncoder

SOURCE=Path(__file__).resolve().parents[1]/'research/data/noaa/co2_annmean_mlo.csv'


class RealPartitionTests(unittest.TestCase):
    def setUp(self): self.record=create_record(SOURCE)

    def test_every_original_window_and_profile(self):
        self.assertTrue(verify_record(self.record,SOURCE))
        stats=self.record['statistics']
        self.assertEqual(stats['windows'],65)
        self.assertEqual(stats['original_render_classes'],stats['partition_render_classes'])
        self.assertTrue(all(c['original']>0 and c['partition']==0 for c in stats['profile_disagreeing_pairs'].values()))
        for window in self.record['windows']:
            self.assertEqual(window['threshold_profiles'],direct_profiles(window['values'],['350','400','420']))

    def test_selected_pairs_change_events_and_preserve_full_windows(self):
        encoder=PartitionEncoder(self.record['partition'])
        for threshold,pair in self.record['selected_examples'].items():
            left,right=[self.record['windows'][pair[side+'_window_index']] for side in ('left','right')]
            self.assertEqual(len(left['years']),3)
            self.assertEqual(left['original_render'],right['original_render'])
            self.assertNotEqual(left['partition_render'],right['partition_render'])
            self.assertNotEqual(left['threshold_profiles'][threshold],right['threshold_profiles'][threshold])
            self.assertEqual(encoder.profiles(encoder.encode(left['values'])),left['threshold_profiles'])

    def test_tampering_rejected(self):
        record=copy.deepcopy(self.record);record['windows'][0]['values'][0]='0'
        self.assertFalse(verify_record(record,SOURCE))
        record=copy.deepcopy(self.record);record['windows'][0]['years'][0]+=1
        self.assertFalse(verify_record(record,SOURCE))
        record=copy.deepcopy(self.record);record['statistics']['profile_decode_failures']=False
        self.assertFalse(verify_record(record,SOURCE))
        record=copy.deepcopy(self.record);record['source']['raw_sha256']='0'*64
        self.assertFalse(verify_record(record,SOURCE))
