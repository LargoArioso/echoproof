import copy
from fractions import Fraction
import unittest
from echoproof import Mapping
from echoproof.multi_alignment import align_thresholds, verify_multi_alignment
from echoproof.model import number
from echoproof.intervals import transitions, verify_threshold_certificate


class MultiAlignmentTests(unittest.TestCase):
    def test_fifty_and_fifty_one_impossible_with_coarse_steps(self):
        record = align_thresholds(Mapping(domain_high="100", pitch_step_cents=1200), [50, 51], 0, 100)
        self.assertEqual(record["status"], "impossible")
        self.assertEqual(record["constraints"]["minimum_transition_spacing"], "100/3")
        self.assertTrue(verify_multi_alignment(record))

    def test_two_already_aligned_thresholds_keep_original_best(self):
        mapping = Mapping(domain_high="100", pitch_step_cents=1200)
        result = align_thresholds(mapping, ["50/3", 50], 0, 100)
        self.assertEqual(result["candidates"][0]["mapping"], mapping.to_dict())
        self.assertEqual(result["candidates"][0]["normalized_endpoint_change"], "0")

    def test_move_both_endpoints_can_find_exact_solution(self):
        result = align_thresholds(Mapping(domain_high="100", pitch_step_cents=1200), [15, 51, 87], 0, 100)
        best = result["candidates"][0]
        self.assertEqual(best["mapping"]["domain_low"], "-3")
        self.assertEqual(best["mapping"]["domain_high"], "105")
        self.assertEqual(best["transition_indices"], [0, 1, 2])
        self.assertTrue(all(verify_threshold_certificate(c) for c in best["certificates"]))

    def test_spacing_bound_sufficient_to_reject_but_not_accept(self):
        result = align_thresholds(Mapping(domain_high="100", pitch_step_cents=1200), [20, 60, 101], 0, 110)
        self.assertEqual(result["status"], "impossible")
        self.assertGreater(result["search"]["index_pair_upper_bound"], 0)

    def test_matches_independent_boundary_pair_enumeration(self):
        # Candidate ranges computed directly from boundary equations for every i<j.
        for thresholds in ([2, 6], [3, 7], [1, 9], [2, 6, 10], ["3/2", "9/2"]):
            mapping = Mapping(pitch_step_cents=1200)
            actual = align_thresholds(mapping, thresholds, 0, 10, limit=16)
            expected = set()
            values = sorted(map(number, thresholds))
            for i in range(3):
                for j in range(i+1, 3):
                    delta = (values[1]-values[0]) / (j-i)
                    lo = values[0] - Fraction(2*i+1, 2)*delta
                    hi = lo + 3*delta
                    candidate = Mapping(domain_low=str(lo), domain_high=str(hi), pitch_step_cents=1200)
                    if lo <= 0 and hi >= 10 and all(t in transitions(candidate) for t in values):
                        expected.add((str(lo), str(hi)))
            found = {(c["mapping"]["domain_low"], c["mapping"]["domain_high"]) for c in actual["candidates"]}
            self.assertEqual(found, expected)

    def test_tampering_and_invalid_or_constant_thresholds(self):
        record = align_thresholds(Mapping(), [2, 6], 0, 10)
        broken = copy.deepcopy(record)
        broken["status"] = "invented"
        self.assertFalse(verify_multi_alignment(broken))
        for thresholds in ([1], [1, 1], [0, 5], [5, 11]):
            with self.assertRaises(ValueError):
                align_thresholds(Mapping(), thresholds, 0, 10)
        with self.assertRaises(ValueError):
            align_thresholds(Mapping(stride=2), [2, 6], 0, 10)

    def test_large_search_explicitly_rejected_not_called_impossible(self):
        with self.assertRaisesRegex(ValueError, "search limit"):
            align_thresholds(Mapping(pitch_low_cents=0, pitch_high_cents=12700, pitch_step_cents=1), [4, 6], 0, 10)


if __name__ == "__main__":
    unittest.main()
