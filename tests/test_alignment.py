import copy
import unittest
from echoproof import Mapping, encode
from echoproof.alignment import align_threshold, verify_alignment
from echoproof.intervals import verify_threshold_certificate


class AlignmentTests(unittest.TestCase):
    def test_threshold_fifty_one_adjusts_high_to_102(self):
        original = Mapping(domain_high="100", pitch_step_cents=1200)
        result = align_threshold(original, 51, 0, 100)
        best = result["candidates"][0]
        self.assertEqual(best["mapping"]["domain_low"], "0")
        self.assertEqual(best["mapping"]["domain_high"], "102")
        self.assertEqual(best["mapping"]["pitch_step_cents"], 1200)
        self.assertEqual(best["normalized_endpoint_change"], "1/50")
        self.assertTrue(verify_alignment(result))
        self.assertIn("50", best["previously_preserved_thresholds_lost"])
        fixed = Mapping(**best["mapping"])
        self.assertNotEqual(encode(["50.5"], fixed), encode([51], fixed))

    def test_already_aligned_returns_unchanged_best(self):
        original = Mapping(domain_high="100", pitch_step_cents=1200)
        best = align_threshold(original, 50, 0, 100)["candidates"][0]
        self.assertEqual(best["normalized_endpoint_change"], "0")
        self.assertEqual(best["operation"], "already_preserved")
        self.assertEqual(best["previously_preserved_thresholds_lost"], [])

    def test_constant_task_needs_no_range_fix_even_without_transitions(self):
        original = Mapping(pitch_step_cents=10000)
        result = align_threshold(original, 100, 0, 10)
        self.assertEqual(result["candidates"][0]["operation"], "already_preserved")
        self.assertEqual(result["candidates"][0]["mapping"], original.to_dict())

    def test_all_candidates_cover_original_and_declared_interval(self):
        result = align_threshold(Mapping(domain_high="100", pitch_step_cents=1200), 51, -5, 110)
        for candidate in result["candidates"]:
            from echoproof.model import number
            self.assertLessEqual(number(candidate["mapping"]["domain_low"]), -5)
            self.assertGreaterEqual(number(candidate["mapping"]["domain_high"]), 110)
            self.assertTrue(verify_threshold_certificate(candidate["certificate"]))

    def test_pitch_vocabulary_with_no_transitions_has_no_range_fix(self):
        result = align_threshold(Mapping(pitch_step_cents=10000), 5, 0, 10)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["search"]["pitch_steps_considered"], 0)

    def test_missing_samples_and_stride_are_not_smuggled_into_proof(self):
        with self.assertRaises(ValueError):
            align_threshold(Mapping(stride=2), 5, 0, 10)
        result = align_threshold(Mapping(missing="zero"), 5, 0, 10)
        self.assertIn("no missing samples", result["scope"])

    def test_per_series_mapping_explicitly_changes_to_fixed(self):
        result = align_threshold(Mapping(normalization="per_series"), 5, 0, 10)
        self.assertTrue(all(c["mapping"]["normalization"] == "fixed" for c in result["candidates"]))

    def test_tampered_rank_or_mapping_rejected(self):
        result = align_threshold(Mapping(), 5, 0, 10)
        self.assertTrue(verify_alignment(result))
        modified = copy.deepcopy(result)
        modified["candidates"].reverse()
        self.assertFalse(verify_alignment(modified))


if __name__ == "__main__":
    unittest.main()
