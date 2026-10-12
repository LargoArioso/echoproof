import copy
import io
import itertools
import json
import tempfile
import unittest
import wave
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from echoproof import Mapping, encode, audit, verify_witness
from echoproof.audit import minimize, witness, repair_candidates
from echoproof.audio import wav_bytes
from echoproof.cli import DEMOS, main
from echoproof.model import Event, Render, number
from echoproof.report import report_html
from echoproof.tasks import answer, TASKS


class MappingTests(unittest.TestCase):
    def test_endpoints_and_midpoint(self):
        self.assertEqual([e.pitch_cents for e in encode([0, 5, 10]).events], [4800, 6600, 8400])

    def test_half_up_boundary_is_exact(self):
        spec = Mapping(domain_high="72")
        self.assertEqual(encode(["0.999999999999999999999"], spec).events[0].pitch_cents, 4800)
        self.assertEqual(encode(["1"], spec).events[0].pitch_cents, 4900)

    def test_quantization_anchored_to_pitch_low(self):
        spec = Mapping(pitch_low_cents=4850, pitch_high_cents=8450)
        self.assertEqual(encode([0], spec).events[0].pitch_cents, 4850)

    def test_clipping(self):
        self.assertEqual(encode([-100, 100]), encode([0, 10]))

    def test_per_series_affine_invariance(self):
        spec = Mapping(normalization="per_series")
        self.assertEqual(encode([1, 2, 4], spec), encode([12, 14, 18], spec))

    def test_per_series_constant_uses_midpoint(self):
        spec = Mapping(normalization="per_series")
        self.assertEqual(encode([1, 1], spec), encode([999, 999], spec))
        self.assertEqual(encode([1], spec).events[0].pitch_cents, 6600)

    def test_missing_silence_retains_tail_duration(self):
        self.assertEqual(encode([1, None]).duration_ms, 480)
        self.assertNotEqual(encode([1, None]), encode([1]))

    def test_missing_zero_has_exact_alias(self):
        spec = Mapping(missing="zero")
        self.assertEqual(encode([None, 5], spec), encode([0, 5], spec))

    def test_missing_marker_is_a_distinct_event(self):
        self.assertNotEqual(encode([None], Mapping(missing="marker")), encode([0], Mapping(missing="marker")))

    def test_missing_skip_compresses_time(self):
        spec = Mapping(missing="skip")
        self.assertEqual(encode([1, None, 2], spec), encode([1, 2], spec))

    def test_all_missing_has_zero_events(self):
        self.assertEqual(encode([None, None]).events, ())
        self.assertEqual(encode([None, None], Mapping(missing="skip")).duration_ms, 0)

    def test_stride_uses_selected_sample_order(self):
        self.assertEqual(encode([0, 10, 5], Mapping(stride=2)), encode([0, 5]))

    def test_reject_invalid_parameters(self):
        for kwargs in ({"stride": 0}, {"stride": True}, {"stride": 1.5}, {"missing": "invent"},
                       {"domain_high": "0"}, {"domain_high": "nan"}, {"pitch_step_cents": 0},
                       {"note_ms": 0}, {"slot_ms": 1}, {"pitch_high_cents": 20000}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Mapping(**kwargs)

    def test_reject_empty_nonfinite_and_bool_data(self):
        for values in ([], [float("inf")], [float("nan")], [True]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                encode(values)
        with self.assertRaises(ValueError):
            encode(iter(()))

    def test_rational_roundtrip(self):
        spec = Mapping(domain_low="1/3", domain_high="4/3")
        self.assertEqual(spec, Mapping(**spec.to_dict()))
        self.assertEqual(encode([Fraction(1, 3)], spec).events[0].pitch_cents, 4800)


class TaskTests(unittest.TestCase):
    def test_threshold_inclusive(self):
        self.assertTrue(answer([None, 5], "threshold", "5"))
        self.assertFalse(answer([None], "threshold", "5"))

    def test_trend_uses_first_last_observed(self):
        self.assertEqual(answer([None, 3, 9, None, 1], "endpoint_trend"), "falling")
        self.assertEqual(answer([None, 1], "endpoint_trend"), "undefined")

    def test_all_peak_ties_and_original_positions(self):
        self.assertEqual(answer([None, 2, 1, 2], "peak_indices"), (1, 3))
        self.assertEqual(answer([None], "peak_indices"), ())

    def test_missing_total_is_not_imputed(self):
        self.assertEqual(answer([1, None, 2], "total"), "3")
        self.assertEqual(answer([None], "total"), "undefined")


class AuditTests(unittest.TestCase):
    def test_original_corpus_witness_retained_when_minimum_leaves_domain(self):
        from echoproof.audit import audit_explicit
        values = [[1, 2], [10, 20]]
        result = audit_explicit(Mapping(normalization="per_series"), values, tasks=["threshold"], threshold=5)
        task = result["tasks"]["threshold"]
        original = task["original_witness"]
        self.assertTrue(verify_witness(original))
        self.assertIn(original["left"], result["domain"]["series"])
        self.assertIn(original["right"], result["domain"]["series"])
        self.assertNotIn(task["witness"]["left"], result["domain"]["series"])
        self.assertEqual(len(original["left"]), 2)


    def test_counts_against_brute_force_pairs(self):
        for spec in (Mapping(), Mapping(missing="zero"), Mapping(stride=2), Mapping(normalization="per_series")):
            sequences = [x for n in (1, 2, 3) for x in itertools.product(("0", "1", None), repeat=n)]
            result = audit(spec, [0, 1], (1, 2, 3), threshold="1", include_missing=True)
            pairs = [(a, b) for a, b in itertools.combinations(sequences, 2) if encode(a, spec) == encode(b, spec)]
            self.assertEqual(result["search"]["equal_render_pairs"], len(pairs))
            self.assertEqual(result["search"]["series_count"], len(sequences))
            for task in TASKS:
                expected = sum(answer(a, task, "1") != answer(b, task, "1") for a, b in pairs)
                self.assertEqual(result["tasks"][task]["disagreeing_pairs"], expected)
                record = result["tasks"][task]["witness"]
                if record:
                    self.assertTrue(verify_witness(record))

    def test_injective_grid_negative_control(self):
        result = audit(Mapping(missing="marker"), [0, 5, 10], (1, 2, 3), include_missing=True)
        self.assertEqual(result["search"]["collision_classes"], 0)
        self.assertTrue(all(v["status"] == "no_collision_on_grid" for v in result["tasks"].values()))

    def test_no_collision_outcome_is_scoped(self):
        result = audit(Mapping(), [0, 10], (2,))
        self.assertIn("finite grid", result["scope"])
        self.assertNotIn("safe", json.dumps(result))

    def test_duplicate_levels_are_not_counted_twice(self):
        a = audit(Mapping(), [0, "0.0", 10], (2,))
        self.assertEqual(a["search"]["series_count"], 4)

    def test_search_guard_and_invalid_tasks(self):
        for kwargs in ({"levels": []}, {"levels": [0, 1], "lengths": [0]},
                       {"levels": [0, 1], "lengths": [True]}, {"levels": [0, 1], "lengths": [25]},
                       {"levels": [0, 1], "tasks": ["fake"]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                audit(Mapping(), **kwargs)

    def test_witness_tampering_rejected(self):
        valid = witness([1, 1], [2, 2], Mapping(normalization="per_series"), "total", "5")
        self.assertTrue(verify_witness(valid))
        for field, value in (("right_answer", "999"), ("claim", "perceptual_collision"), ("right", [1, 1]), ("render", {}), ("mapping", {})):
            record = copy.deepcopy(valid)
            record[field] = value
            self.assertFalse(verify_witness(record))
        self.assertFalse(verify_witness({}))

    def test_minimization_is_valid_and_one_minimal(self):
        spec = Mapping(missing="zero")
        record = minimize(witness([1, None, 5], [1, 0, 5], spec, "missing_count", "5"))
        self.assertTrue(verify_witness(record))
        self.assertEqual(record["left"], [None])
        self.assertEqual(record["right"], ["0"])

    def test_demos_have_verified_failures_and_combined_grid_repair(self):
        for name, config in DEMOS.items():
            config = dict(config)
            config.pop("title")
            result = audit(**config)
            self.assertTrue(any(v["witness"] for v in result["tasks"].values()), name)
            for details in result["tasks"].values():
                if details["witness"]:
                    self.assertTrue(verify_witness(details["witness"]), name)
            combined = dict(repair_candidates(config["mapping"], config["levels"]))["combined"]
            repaired = audit(**dict(config, mapping=combined))
            self.assertTrue(all(v["disagreeing_pairs"] == 0 for v in repaired["tasks"].values()), name)


class ArtifactTests(unittest.TestCase):
    def test_equal_events_equal_wav_bytes(self):
        spec = Mapping(normalization="per_series")
        self.assertEqual(wav_bytes(encode([1, 2], spec)), wav_bytes(encode([10, 20], spec)))

    def test_audio_header_duration_and_peak(self):
        data = wav_bytes(encode([0, None, 10]))
        with wave.open(io.BytesIO(data)) as stream:
            self.assertEqual(stream.getnchannels(), 1)
            self.assertEqual(stream.getsampwidth(), 2)
            self.assertEqual(stream.getnframes(), 15876)
            import struct
            pcm = struct.unpack("<%dh" % stream.getnframes(), stream.readframes(stream.getnframes()))
            self.assertLessEqual(max(abs(x) for x in pcm), 5900)

    def test_audio_limits(self):
        with self.assertRaises(ValueError):
            wav_bytes(Render((), 60001))
        with self.assertRaises(ValueError):
            wav_bytes(Render((Event(10, 100, 6000),), 50))

    def test_report_escapes_title_and_does_not_autoplay(self):
        report = report_html(audit(Mapping(), [0, 10], (1,)), '<script>alert("bad")</script>')
        self.assertNotIn('<script>', report)
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('autoplay', report)

    def test_cli_outputs_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "mapping.json"
            spec.write_text(json.dumps(Mapping(normalization="per_series").to_dict()))
            output = Path(directory) / "report"
            self.assertEqual(main(["audit", "--spec", str(spec), "--levels", "1,2", "--lengths", "1,2", "--tasks", "total", "--out", str(output)]), 0)
            self.assertTrue((output / "index.html").exists())
            self.assertEqual(main(["verify", str(output / "total.witness.json")]), 0)


if __name__ == "__main__":
    unittest.main()
