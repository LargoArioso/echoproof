import copy
import json
from pathlib import Path
import tempfile
import unittest
from echoproof.compiled import audit_compiled, recording_witness, verify_recording_witness, project
from echoproof.cli import main


BACKEND = {"name": "test-recording-fixture", "version": "1", "scope": "synthetic test, not real Erie output"}


def fixture(values, speech, pitch=500):
    sound = {"start": 0, "duration": 0.5, "pitch": pitch, "__datum": {"y": values[0]}}
    return {"input": values, "tone": {"instrument_type": "sine", "sounds": [sound], "continued": False, "relative": False, "duration": 0.5},
            "queue": {"queue": [{"type": "text", "speech": speech}, {"type": "tone", **sound}], "state": "finished"}}


class CompiledTests(unittest.TestCase):
    def test_full_scope_keeps_speech_partial_scope_can_alias(self):
        a, b = fixture([1, 2, 3], "minimum 1"), fixture([10, 20, 30], "minimum 10")
        corpus = {"backend": BACKEND, "records": [a, b]}
        full = audit_compiled(corpus, "erie_full_queue", threshold="5")
        tone = audit_compiled(corpus, "erie_tone_stream", threshold="5")
        self.assertEqual(full["tasks"]["threshold"]["disagreeing_pairs"], 0)
        self.assertEqual(tone["tasks"]["threshold"]["disagreeing_pairs"], 1)
        self.assertTrue(verify_recording_witness(tone["tasks"]["threshold"]["witness"]))

    def test_aggregate_style_recording_collision_on_original_threshold(self):
        a, b = fixture([1, 3, 2], "mean 2"), fixture([2, 2, 2], "mean 2")
        # Recorded aggregate metadata is the same, though source inputs differ.
        a["queue"]["queue"][1]["__datum"] = {"y": 2}
        b["queue"]["queue"][1]["__datum"] = {"y": 2}
        result = audit_compiled({"backend": BACKEND, "records": [a, b]}, threshold="3")
        self.assertEqual(result["tasks"]["threshold"]["disagreeing_pairs"], 1)
        self.assertEqual(result["tasks"]["total"]["disagreeing_pairs"], 0)
        self.assertIn("not automatically a library bug", result["scope"])

    def test_only_datum_removed_and_other_fields_retained(self):
        a = fixture([1], "important speech")
        projected = project(a, "erie_full_queue")
        self.assertEqual(projected["queue"][0]["speech"], "important speech")
        self.assertEqual(projected["queue"][1]["pitch"], 500)
        self.assertNotIn("__datum", projected["queue"][1])
        self.assertIn("__datum", a["queue"]["queue"][1])

    def test_unknown_queue_item_rejected(self):
        a = fixture([1], "x")
        a["queue"]["queue"].append({"type": "custom-audio"})
        with self.assertRaises(ValueError):
            project(a, "erie_full_queue")

    def test_continuous_or_relative_tones_rejected(self):
        for field in ("continued", "relative"):
            a = fixture([1], "x")
            a["tone"][field] = True
            with self.assertRaises(ValueError):
                project(a, "erie_tone_stream")

    def test_nonfinite_compiled_parameter_rejected(self):
        with self.assertRaises(ValueError):
            project(fixture([1], "x", float("nan")), "erie_full_queue")

    def test_duplicate_inputs_and_empty_corpus_rejected(self):
        a = fixture([1], "x")
        for records in ([], [a, a]):
            with self.assertRaises(ValueError):
                audit_compiled({"backend": BACKEND, "records": records})

    def test_witness_tampering_and_scope_expansion_rejected(self):
        a, b = fixture([1], "minimum 1"), fixture([10], "minimum 10")
        witness = recording_witness(a, b, BACKEND, "erie_tone_stream", "threshold", "5")
        self.assertTrue(verify_recording_witness(witness))
        for field, value in (("audit_scope", "erie_full_queue"), ("left_answer", True),
                             ("projection_sha256", "wrong"), ("task_basis", "transformed")):
            modified = copy.deepcopy(witness)
            modified[field] = value
            self.assertFalse(verify_recording_witness(modified))

    def test_cli_recording_verification_is_distinguished(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus = {"backend": BACKEND, "records": [fixture([1], "same"), fixture([10], "same")]}
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(corpus))
            output = Path(directory) / "report"
            self.assertEqual(main(["compiled", str(path), "--out", str(output)]), 0)
            self.assertEqual(main(["verify", str(output / "threshold.recording-witness.json")]), 0)
            self.assertTrue((output / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
