import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('real_data_case',ROOT/'tools/real_data_case.py')
case=importlib.util.module_from_spec(spec)
spec.loader.exec_module(case)


class RealDataTests(unittest.TestCase):
    def test_saved_full_windows_match_actual_archived_rows(self):
        source=ROOT/'research/data/noaa/co2_annmean_mlo.csv'
        pair=ROOT/'artifacts/noaa-windows/selected_pair.json'
        self.assertTrue(case.verify_selected(pair,source))
        raw,rows=case.read_annual(source)
        self.assertEqual(len(rows),67)
        record=json.loads(pair.read_text())
        self.assertEqual(record['left_window']['years'],[1960,1961,1962])
        self.assertEqual(record['right_window']['years'],[2013,2014,2015])
        self.assertFalse(record['witness']['left_answer'])
        self.assertTrue(record['witness']['right_answer'])

    def test_date_value_source_and_complete_length_tampering_rejected(self):
        source=ROOT/'research/data/noaa/co2_annmean_mlo.csv'
        record=json.loads((ROOT/'artifacts/noaa-windows/selected_pair.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'pair.json'
            for field,value in [('years',[1960,1962,1963]),('years',[1960,1961]),('values',['1','2','3'])]:
                modified=copy.deepcopy(record)
                modified['left_window'][field]=value
                path.write_text(json.dumps(modified))
                self.assertFalse(case.verify_selected(path,source))
            modified=copy.deepcopy(record)
            modified['source']['url']='https://unrelated.example/'
            path.write_text(json.dumps(modified))
            self.assertFalse(case.verify_selected(path,source))
            changed_source=Path(temporary)/'changed.csv'
            changed_source.write_bytes(source.read_bytes()+b'\n')
            path.write_text(json.dumps(record))
            self.assertFalse(case.verify_selected(path,changed_source))

    def test_annual_reader_rejects_gaps_missing_and_unexpected_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'annual.csv'
            cases=['year,mean,unc\n2000,370,0.1\n2002,374,0.1\n2003,375,0.1\n',
                   'year,mean,unc\n2000,-999,0.1\n2001,374,0.1\n2002,375,0.1\n',
                   'year,mean\n2000,370\n2001,372\n2002,374\n']
            for raw in cases:
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    case.read_annual(path)


if __name__=='__main__':
    unittest.main()
