import copy
from dataclasses import replace
from fractions import Fraction
import unittest
from echoproof import Mapping, encode, verify_witness
from echoproof.intervals import threshold_certificate, transitions, verify_threshold_certificate


class IntervalTests(unittest.TestCase):
    def test_default_transitions(self):
        points = transitions(Mapping())
        self.assertEqual(len(points), 36)
        self.assertEqual(points[0], Fraction(5, 36))
        self.assertEqual(points[-1], Fraction(355, 36))

    def test_threshold_fifty_safe_fifty_one_not(self):
        spec = Mapping(domain_high="100", pitch_step_cents=1200)
        self.assertEqual(threshold_certificate(spec, 50, 0, 100)["status"], "preserved")
        result = threshold_certificate(spec, 51, 0, 100)
        self.assertEqual(result["status"], "collision_found")
        self.assertTrue(verify_witness(result["witness"]))

    def test_transition_exactly_at_domain_max(self):
        spec = Mapping(pitch_high_cents=4950, pitch_step_cents=100)
        self.assertEqual(transitions(spec), (Fraction(10, 3), Fraction(10)))
        self.assertEqual(threshold_certificate(spec, 10, 0, 11)["status"], "preserved")

    def test_all_true_false_and_singleton_intervals(self):
        for threshold, low, high in ((0, 0, 10), (11, 0, 10), (5, 5, 5), (6, 5, 5)):
            self.assertEqual(threshold_certificate(Mapping(), threshold, low, high)["status"], "preserved")

    def test_clipped_tails_have_collisions(self):
        for threshold in (-1, 11, 10, 0):
            result = threshold_certificate(Mapping(), threshold, -2, 12)
            self.assertEqual(result["status"], "collision_found")
            self.assertTrue(verify_witness(result["witness"]))

    def test_step_wider_than_range_is_constant(self):
        spec = Mapping(pitch_step_cents=10000)
        self.assertEqual(transitions(spec), ())
        self.assertEqual(threshold_certificate(spec, 5, 0, 10)["status"], "collision_found")

    def test_unsupported_assumptions_are_explicit(self):
        for spec in (Mapping(stride=2), Mapping(normalization="per_series")):
            self.assertEqual(threshold_certificate(spec, 5, 0, 10)["status"], "unsupported")

    def test_tampered_certificate_is_invalid(self):
        result = threshold_certificate(Mapping(), "5/36", 0, 10)
        self.assertTrue(verify_threshold_certificate(result))
        modified = copy.deepcopy(result)
        modified["reason"] = "invented"
        self.assertFalse(verify_threshold_certificate(modified))

    def test_analytic_claims_against_dense_rational_grid(self):
        # Independent finite falsification, across irregular quantizer widths.
        for step in (7, 100, 333, 1200, 2400, 7200, 10000):
            spec = Mapping(pitch_step_cents=step)
            values = [Fraction(i, 10) for i in range(-20, 121)]
            for threshold in (Fraction(-1), Fraction(0), Fraction(5), Fraction(10), Fraction(11), *transitions(spec)[:3]):
                certificate = threshold_certificate(spec, threshold, -2, 12)
                if certificate["status"] == "collision_found":
                    self.assertTrue(verify_witness(certificate["witness"]))
                else:
                    labels = {}
                    for value in values + [threshold]:
                        pitch = encode([value], spec).events[0].pitch_cents
                        label = value >= threshold
                        self.assertEqual(labels.setdefault(pitch, label), label)


if __name__ == "__main__":
    unittest.main()
