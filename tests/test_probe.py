import itertools
import json
from pathlib import Path
import tempfile
import unittest
from echoproof import Mapping, verify_witness
from echoproof.audit import audit_explicit, audit
from echoproof.probe import read_csv, probe_csv, neighborhood
from echoproof.cli import main


class ExplicitTests(unittest.TestCase):
    def test_explicit_corpus_matches_grid_enumeration(self):
        mapping = Mapping(missing="zero")
        corpus = [x for n in (1, 2) for x in itertools.product((0, 1, None), repeat=n)]
        explicit = audit_explicit(mapping, corpus, threshold="1")
        grid = audit(mapping, [0, 1], (1, 2), threshold="1", include_missing=True)
        self.assertEqual(explicit["search"]["equal_render_pairs"], grid["search"]["equal_render_pairs"])
        for task in explicit["tasks"]:
            self.assertEqual(explicit["tasks"][task]["disagreeing_pairs"], grid["tasks"][task]["disagreeing_pairs"])

    def test_dedup_corpus_and_validation(self):
        result = audit_explicit(Mapping(), [[0], ["0.0"], [1]])
        self.assertEqual(result["search"]["series_count"], 2)
        for corpus in ([], [[]], [[0] * 129]):
            with self.assertRaises(ValueError):
                audit_explicit(Mapping(), corpus)

    def test_huge_length_rejected_before_exponentiation(self):
        with self.assertRaises(ValueError):
            audit(Mapping(), [0, 1], lengths=(100000000000000000000,))

    def test_mutations_deterministic(self):
        baseline = [1, None, 3]
        candidates = neighborhood(baseline, Mapping(), "5")
        self.assertEqual(candidates, neighborhood(baseline, Mapping(), "5"))
        self.assertEqual(len(candidates), len(set(candidates)))
        self.assertEqual(candidates[0][0], 1)


class CsvTests(unittest.TestCase):
    def make_file(self, directory, text):
        path = Path(directory) / "data.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_read_missing_fraction_bom(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.make_file(d, '\ufefftime,value\n0,1/3\n1,NA\n2,"2.5"\n')
            values, source = read_csv(path, "value")
            self.assertEqual(str(values[0]), "1/3")
            self.assertIsNone(values[1])
            self.assertEqual(str(values[2]), "5/2")
            self.assertEqual(source["rows"], 3)
            self.assertEqual(len(source["sha256"]), 64)

    def test_invalid_fields_headers_and_rows_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for text in ('other\n1\n', 'value,value\n1,2\n', 'value\nInfinity\n', 'time,value\n0\n', 'value\n' + '1\n' * 65, 'value\n'):
                with self.subTest(text=text[:30]), self.assertRaises(ValueError):
                    read_csv(self.make_file(d, text), "value")

    def test_probe_provenance_and_witnesses(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.make_file(d, "value\n1\n2\n3\n")
            result = probe_csv(path, "value", Mapping(normalization="per_series"), threshold="3")
            self.assertEqual(result["search"]["mode"], "explicit_finite_corpus")
            self.assertEqual(result["domain"]["provenance"]["source"]["filename"], "data.csv")
            self.assertTrue(result["tasks"]["total"]["witness"])
            for task in result["tasks"].values():
                if task["witness"]:
                    self.assertTrue(verify_witness(task["witness"]))

    def test_csv_cli_and_json_list_verification(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.make_file(d, "value\n1\n2\n3\n")
            out = Path(d) / "output"
            self.assertEqual(main(["probe", str(path), "--column", "value", "--out", str(out)]), 0)
            self.assertTrue((out / "audit.json").exists())
            bogus = Path(d) / "bogus.json"
            bogus.write_text("[]")
            self.assertEqual(main(["verify", str(bogus)]), 1)


if __name__ == "__main__":
    unittest.main()
