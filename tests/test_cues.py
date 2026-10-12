import copy
from dataclasses import replace
import tempfile
from pathlib import Path
import json
import unittest
from echoproof import Mapping, encode, audit
from echoproof.cli import DEMOS, main
from echoproof.cues import plan_from_audit, verify_plan, CueEncoder, domain_corpus
from echoproof.model import Render, Event
from echoproof.tasks import answer, json_answer
from echoproof.audit import audit_explicit


class CueTests(unittest.TestCase):
    def test_domain_threshold_disagreement_is_rejected(self):
        from echoproof.cues import build_plan
        domain = {"levels": [1, 2], "lengths": [1], "include_missing": False, "threshold": "2"}
        with self.assertRaisesRegex(ValueError, "thresholds must agree"):
            build_plan(Mapping(), domain, ["threshold"], "5")

    def test_all_demo_domains_decode_all_requested_answers(self):
        for name, config in DEMOS.items():
            config = dict(config)
            config.pop("title")
            result = audit(**config)
            plan = plan_from_audit(result)
            self.assertTrue(verify_plan(plan), name)
            encoder = CueEncoder(plan)
            rendered_labels = {}
            for values in domain_corpus(plan["domain"]):
                labels = [json_answer(answer(values, t, plan["threshold"])) for t in plan["tasks"]]
                augmented = encoder.encode(values)
                self.assertEqual(encoder.decode(augmented), labels)
                self.assertEqual(rendered_labels.setdefault(augmented, labels), labels)
            self.assertEqual(plan["statistics"]["worst_case_bits"], plan["statistics"]["worst_case_binary_lower_bound"])

    def test_quantization_requires_three_bits_for_joint_tasks(self):
        config = dict(DEMOS["quantization"])
        config.pop("title")
        plan = plan_from_audit(audit(**config))
        self.assertEqual(plan["statistics"]["max_joint_answers_per_class"], 8)
        self.assertEqual(plan["statistics"]["worst_case_bits"], 3)

    def test_unambiguous_domain_has_no_added_events(self):
        plan = plan_from_audit(audit(Mapping(), [0, 10], (2,), tasks=["threshold"]))
        self.assertEqual(plan["statistics"]["worst_case_bits"], 0)
        encoder = CueEncoder(plan)
        self.assertEqual(encoder.encode([0, 10]), encode([0, 10]))
        self.assertTrue(verify_plan(plan))

    def test_input_outside_declared_domain_rejected(self):
        plan = plan_from_audit(audit(Mapping(), [0, 10], (2,), tasks=["threshold"]))
        encoder = CueEncoder(plan)
        for values in ([1, 10], [0], [0, None]):
            with self.assertRaises(ValueError):
                encoder.encode(values)

    def test_zero_duration_base_can_receive_cues(self):
        result = audit_explicit(Mapping(missing="skip"), [[None], [None, None]], tasks=["missing_count"])
        plan = plan_from_audit(result)
        encoder = CueEncoder(plan)
        self.assertNotEqual(encoder.encode([None]), encoder.encode([None, None]))
        self.assertEqual(encoder.decode(encoder.encode([None])), [1])
        self.assertTrue(verify_plan(plan))

    def test_plan_tampering_rejected(self):
        result = audit(Mapping(normalization="per_series"), [1, 2], (1, 2), tasks=["total"])
        plan = plan_from_audit(result)
        for field, value in (("statistics", {}), ("classes", []), ("code", {}), ("threshold", "bad")):
            modified = copy.deepcopy(plan)
            modified[field] = value
            self.assertFalse(verify_plan(modified))

    def test_decoder_rejects_tampered_timing_pitch_and_length(self):
        plan = plan_from_audit(audit(Mapping(normalization="per_series"), [1, 2], (1, 2), tasks=["total"]))
        encoder = CueEncoder(plan)
        good = encoder.encode([1])
        for bad in (Render(good.events, good.duration_ms + 1),
                    Render(good.events[:-1], good.duration_ms),
                    Render(good.events[:-1] + (replace(good.events[-1], pitch_cents=999),), good.duration_ms),
                    Render(good.events[:-1] + (replace(good.events[-1], kind="tone"),), good.duration_ms)):
            with self.assertRaises(ValueError):
                encoder.decode(bad)

    def test_decoder_rejects_unused_codeword(self):
        result = audit_explicit(Mapping(normalization="per_series"), [[1], [2], [3]], tasks=["total"])
        plan = plan_from_audit(result)
        encoder = CueEncoder(plan)
        good = encoder.encode([1])
        tail = list(good.events)
        for i in (-1, -2):
            tail[i] = replace(tail[i], kind="cue_one", pitch_cents=5400)
        with self.assertRaises(ValueError):
            encoder.decode(Render(tuple(tail), good.duration_ms))

    def test_cli_exports_same_base_different_cued_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audit.json"
            source.write_text(json.dumps(audit(Mapping(normalization="per_series"), [1, 2], (2,), tasks=["total"])))
            out = Path(directory) / "cues"
            self.assertEqual(main(["cues", str(source), "--out", str(out)]), 0)
            self.assertEqual(main(["verify", str(out / "plan.json")]), 0)
            examples = json.loads((out / "examples.json").read_text())
            self.assertEqual(examples[0]["base"], examples[1]["base"])
            self.assertNotEqual(examples[0]["cued"], examples[1]["cued"])
            self.assertEqual((out / "example0.base.wav").read_bytes(), (out / "example1.base.wav").read_bytes())
            self.assertNotEqual((out / "example0.cued.wav").read_bytes(), (out / "example1.cued.wav").read_bytes())
            self.assertTrue((out / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
