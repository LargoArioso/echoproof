from dataclasses import replace
import itertools
import unittest
from echoproof import Mapping, encode
from echoproof.semantic_cues import SemanticCueEncoder, packet, legend, plan, validate_domain, verify_validation
from echoproof.model import Render, Event
from echoproof.tasks import answer
from echoproof.audio import wav_bytes


class SemanticCueTests(unittest.TestCase):
    def test_all_answers_use_globally_fixed_patterns(self):
        cases = [("threshold", False), ("threshold", True), ("endpoint_trend", "rising"),
                 ("endpoint_trend", "falling"), ("endpoint_trend", "flat"), ("endpoint_trend", "undefined")]
        patterns = [packet(task, value) for task, value in cases]
        self.assertEqual(len(set(patterns)), 6)
        self.assertEqual(len(legend()), 6)

    def test_unseen_and_outside_original_grid_inputs_decode(self):
        encoder = SemanticCueEncoder(Mapping(normalization="per_series"), threshold="5")
        for values in (["1/3", 999, -100], [None], [None, 5], [4, 2], [8, 8]):
            expected = {t: answer(values, t, "5") for t in encoder.tasks}
            self.assertEqual(encoder.decode(encoder.encode(values)), expected)

    def test_exhaustive_small_domain_and_all_missing_policies(self):
        for missing in ("zero", "skip", "silence", "marker"):
            encoder = SemanticCueEncoder(Mapping(missing=missing, stride=2), threshold="2")
            for length in (1, 2, 3):
                for values in itertools.product((None, 0, 2, 4), repeat=length):
                    self.assertEqual(encoder.decode(encoder.encode(values)), {t: answer(values, t, "2") for t in encoder.tasks})

    def test_original_events_retained(self):
        encoder = SemanticCueEncoder()
        base = encode([1, 3, 2])
        augmented = encoder.encode([1, 3, 2])
        self.assertEqual(augmented.events[:len(base.events)], base.events)

    def test_base_alias_separated_without_conditional_codebook(self):
        encoder = SemanticCueEncoder(Mapping(normalization="per_series"), tasks=("threshold",), threshold="5")
        self.assertEqual(encode([1, 2], encoder.mapping), encode([10, 20], encoder.mapping))
        a, b = encoder.encode([1, 2]), encoder.encode([10, 20])
        self.assertNotEqual(a, b)
        self.assertNotEqual(wav_bytes(a), wav_bytes(b))
        self.assertEqual(encoder.decode(a), {"threshold": False})
        self.assertEqual(encoder.decode(b), {"threshold": True})

    def test_only_supported_tasks_allowed(self):
        for tasks in ((), ("total",), ("threshold", "peak_indices")):
            with self.assertRaises(ValueError):
                SemanticCueEncoder(tasks=tasks)

    def test_tampered_packet_rejected(self):
        encoder = SemanticCueEncoder()
        good = encoder.encode([1, 10])
        for bad in (Render(good.events, good.duration_ms + 1), Render(good.events[:-1], good.duration_ms),
                    Render(good.events[:-1] + (replace(good.events[-1], pitch_cents=7000),), good.duration_ms),
                    Render(good.events[:-1] + (replace(good.events[-1], onset_ms=1),), good.duration_ms)):
            with self.assertRaises(ValueError):
                encoder.decode(bad)

    def test_task_subset_and_reversed_order_decode(self):
        for tasks in (("threshold",), ("endpoint_trend",), ("endpoint_trend", "threshold")):
            encoder = SemanticCueEncoder(tasks=tasks)
            self.assertEqual(encoder.decode(encoder.encode([6, 2])), {t: answer([6, 2], t) for t in tasks})

    def test_plan_does_not_claim_human_validation(self):
        record = plan(Mapping())
        self.assertIn("No finite-domain codebook", record["scope"])
        self.assertIn("no human", record["scope"])

    def test_mismatched_threshold_in_domain_is_rejected(self):
        domain = {"levels": [1, 2], "lengths": [1], "include_missing": False, "threshold": "2"}
        with self.assertRaisesRegex(ValueError, "thresholds must agree"):
            validate_domain(plan(Mapping(), threshold="5"), domain)

    def test_declared_domain_verification_and_tampering(self):
        domain = {"levels": ["1", "2", "10"], "lengths": [1, 2], "include_missing": True, "threshold": "5"}
        result = validate_domain(plan(Mapping(normalization="per_series")), domain)
        self.assertTrue(verify_validation(result))
        self.assertEqual(result["statistics"]["checked_series"], 20)
        result["statistics"]["decode_failures"] = 1
        self.assertFalse(verify_validation(result))


if __name__ == "__main__":
    unittest.main()
