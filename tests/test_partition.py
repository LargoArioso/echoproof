import copy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest
from echoproof.model import Mapping, Event, Render, encode
from echoproof.partition import partition_thresholds, verify_partition, PartitionEncoder
from echoproof.multi_alignment import align_thresholds
from echoproof.audio import wav_bytes


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.mapping = Mapping(domain_high="100", pitch_step_cents=1200)
        self.record = partition_thresholds(self.mapping, [50, 51], 0, 100)
        self.encoder = PartitionEncoder(self.record)

    def test_resolves_linear_infeasibility_without_new_pitches(self):
        self.assertEqual(align_thresholds(self.mapping, [50,51], 0,100)["status"],"impossible")
        self.assertEqual(self.record["status"],"preserved")
        self.assertEqual(self.record["selected_pitches_cents"],[4800,7200,8400])
        self.assertEqual(self.record["lower_bound"]["required_pitch_symbols"],3)
        self.assertEqual(encode([50],self.mapping),encode([51],self.mapping))
        self.assertNotEqual(wav_bytes(self.encoder.encode([50])),wav_bytes(self.encoder.encode([51])))
        self.assertTrue(verify_partition(self.record))

    def test_all_sequences_in_exact_boundary_grid(self):
        levels = [0,Fraction(499999,10000),50,Fraction(509999,10000),51,100]
        for length in (1,2,3,4):
            for values in product(levels,repeat=length):
                answers = self.encoder.decode(self.encoder.encode(values))
                self.assertEqual(answers,{"50":any(x>=50 for x in values),"51":any(x>=51 for x in values)})

    def test_profiles_recover_positions_and_counts(self):
        values=[0,50,51,100,50,0]
        result=self.encoder.profiles(self.encoder.encode(values))
        for threshold in (50,51):
            indices=[i for i,x in enumerate(values) if x>=threshold]
            self.assertEqual(result[str(threshold)],{"sample_count":6,"at_or_above_count":len(indices),"indices":indices,"any":True,"all":False,"first_index":indices[0],"last_index":indices[-1]})
        constants=PartitionEncoder(partition_thresholds(self.mapping,[-1,101],0,100))
        self.assertEqual(constants.profiles(constants.encode([0,100]))["-1"]["indices"],[0,1])
        self.assertTrue(constants.profiles(constants.encode([0,100]))["-1"]["all"])
        self.assertEqual(constants.profiles(constants.encode([0,100]))["101"]["first_index"],None)
        for threshold in self.record["thresholds"]:
            for values in product([0,49,50,51,52,100],repeat=3):
                profile=self.encoder.profiles(self.encoder.encode(values))[threshold]
                self.assertEqual(profile["indices"],[i for i,x in enumerate(values) if x>=Fraction(threshold)])

    def test_constants_duplicates_and_singleton_high_bin(self):
        record = partition_thresholds(self.mapping, [-1,0,50,50,100,101],0,100)
        encoder = PartitionEncoder(record)
        self.assertEqual(record["cutpoints"],["50","100"])
        self.assertEqual(record["lower_bound"]["required_pitch_symbols"],3)
        self.assertEqual(encoder.decode(encoder.encode([100])),{"-1":True,"0":True,"50":True,"100":True,"101":False})
        self.assertFalse(encoder.decode(encoder.encode([Fraction(99999,1000)]))["100"])
        constant = partition_thresholds(self.mapping,[-1,101],0,100)
        self.assertEqual(constant["selected_pitches_cents"],[4800])
        self.assertEqual(PartitionEncoder(constant).encode([0]),PartitionEncoder(constant).encode([100]))

    def test_capacity_and_clamped_last_pitch(self):
        impossible = partition_thresholds(self.mapping,[10,20,30,40],0,100)
        self.assertEqual(impossible["status"],"impossible")
        self.assertTrue(verify_partition(impossible))
        with self.assertRaises(ValueError): PartitionEncoder(impossible)
        clamped = partition_thresholds(replace(self.mapping,pitch_step_cents=1000),[20,40,60,80],0,100)
        self.assertEqual(clamped["available_pitches_cents"],[4800,5800,6800,7800,8400])
        self.assertEqual(clamped["selected_pitches_cents"],clamped["available_pitches_cents"])
        huge = partition_thresholds(replace(self.mapping,pitch_step_cents=8000),[50],0,100)
        self.assertEqual(huge["status"],"impossible")

    def test_assumptions_and_bad_inputs(self):
        for mapping,low,high in [(replace(self.mapping,stride=2),0,100),(replace(self.mapping,normalization="per_series"),0,100),(self.mapping,1,100),(self.mapping,0,99),(self.mapping,0,0)]:
            with self.assertRaises(ValueError): partition_thresholds(mapping,[50],low,high)
        for thresholds in ([],[True],range(65)):
            with self.assertRaises(ValueError): partition_thresholds(self.mapping,thresholds,0,100)
        for values in ([],[None],[-1],[101],[True]):
            with self.assertRaises(ValueError): self.encoder.encode(values)

    def test_cli_roundtrip_and_report_wav(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from echoproof.cli import main
        from echoproof.report import write_partition_report
        with tempfile.TemporaryDirectory() as directory:
            path = write_partition_report(self.record,directory)
            self.assertIn("不宣称听辨距离",path.read_text())
            self.assertNotEqual((Path(directory)/"case1.partition.wav").read_bytes(),(Path(directory)/"case2.partition.wav").read_bytes())
            self.assertEqual((Path(directory)/"case1.base.wav").read_bytes(),(Path(directory)/"case2.base.wav").read_bytes())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["verify",str(Path(directory)/"partition.json")]),0)
            self.assertIn("VERIFIED",output.getvalue())

    def test_tampering_and_decoder_types(self):
        for path,value in [("status","impossible"),("selected_pitches_cents",[4800,6000,8400]),("cutpoints",["49","51"])]:
            record=copy.deepcopy(self.record);record[path]=value
            self.assertFalse(verify_partition(record))
        record=copy.deepcopy(self.record);record["lower_bound"]["required_pitch_symbols"]=True
        self.assertFalse(verify_partition(record))
        record=copy.deepcopy(self.record);record["lower_bound"]["distinct_answer_vectors"][0][0]=0
        self.assertFalse(verify_partition(record))
        valid=self.encoder.encode([0,100])
        for invalid in (Render((),0),replace(valid,duration_ms=True),replace(valid,duration_ms=480.0),replace(valid,events=(replace(valid.events[0],pitch_cents=6000),valid.events[1])),replace(valid,events=(replace(valid.events[0],onset_ms=False),valid.events[1])),replace(valid,events=(replace(valid.events[0],kind="missing"),valid.events[1]))):
            with self.assertRaises(ValueError): self.encoder.decode(invalid)


if __name__ == "__main__": unittest.main()
