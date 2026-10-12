"""Finite-domain, task-sufficient binary cue synthesis.

This is a constructive quotient-code experiment, not a human-audibility result.
The base render is retained; ambiguous classes receive a delimiter and bits.
"""
from collections import defaultdict
from itertools import product
import json
from .serialization import same_json
from .model import Mapping, Render, Event, encode, number, series
from .tasks import TASKS, answer, json_answer
from .audit import canonical, MAX_SERIES, MAX_LENGTH


def key(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def domain_corpus(domain):
    if "series" in domain:
        sequences = domain["series"]
        if not sequences or len(sequences) > MAX_SERIES:
            raise ValueError("Invalid explicit cue domain")
        normalized = tuple(dict.fromkeys(tuple(canonical(series(x))) for x in sequences))
        if any(len(x) > MAX_LENGTH for x in normalized):
            raise ValueError("Explicit cue series is too long")
        return normalized
    levels = tuple(dict.fromkeys(str(number(x)) for x in domain["levels"]))
    lengths = tuple(sorted(set(domain["lengths"])))
    if not levels or not lengths or any(type(n) is not int or not 1 <= n <= MAX_LENGTH for n in lengths):
        raise ValueError("Invalid cue domain levels/lengths")
    alphabet = levels + ((None,) if domain["include_missing"] else ())
    if sum(len(alphabet) ** n for n in lengths) > MAX_SERIES:
        raise ValueError("Cue domain is too large")
    return tuple(values for length in lengths for values in product(alphabet, repeat=length))


def build_plan(mapping, domain, tasks, threshold):
    tasks = tuple(dict.fromkeys(tasks))
    if not tasks or any(t not in TASKS for t in tasks):
        raise ValueError("Unsupported or empty cue tasks")
    threshold = str(number(threshold))
    if "threshold" in domain and number(domain["threshold"]) != number(threshold):
        raise ValueError("Domain and cue plan thresholds must agree")
    corpus = domain_corpus(domain)
    groups = defaultdict(dict)
    renders = {}
    for values in corpus:
        base = encode(values, mapping)
        signature = key(base.to_dict())
        renders[signature] = base.to_dict()
        labels = [json_answer(answer(values, task, threshold)) for task in tasks]
        groups[signature][key(labels)] = labels
    classes = []
    for signature in sorted(groups):
        labels = [groups[signature][label] for label in sorted(groups[signature])]
        bits = (len(labels) - 1).bit_length()
        classes.append({"render": renders[signature], "labels": labels, "bits": bits})
    maximum = max(len(c["labels"]) for c in classes)
    return {"schema_version": 1, "claim_type": "finite_task_sufficient_cues", "mapping": mapping.to_dict(),
            "domain": domain, "tasks": list(tasks), "threshold": threshold,
            "code": {"delimiter_pitch_cents": 3600, "zero_pitch_cents": 4200, "one_pitch_cents": 5400,
                     "gap_ms": 240, "slot_ms": 160, "note_ms": 110},
            "classes": classes,
            "statistics": {"series_count": len(corpus), "base_render_classes": len(classes),
                           "ambiguous_classes": sum(len(c["labels"]) > 1 for c in classes),
                           "max_joint_answers_per_class": maximum, "worst_case_bits": (maximum - 1).bit_length(),
                           "worst_case_binary_lower_bound": (maximum - 1).bit_length()},
            "scope": "Task sufficiency only on the declared finite domain and exact event language. Bit optimality assumes a binary fixed-length code conditional on the base render; excludes delimiter cost. No human hearing claim."}


def plan_from_audit(result):
    return build_plan(Mapping(**result["mapping"]), result["domain"], result.get("task_order", result["tasks"]), result["domain"]["threshold"])


class CueEncoder:
    def __init__(self, plan):
        self.plan = plan
        self.mapping = Mapping(**plan["mapping"])
        self.allowed = set(domain_corpus(plan["domain"]))
        self.index = {key(c["render"]): c for c in plan["classes"]}

    def encode(self, values):
        values = tuple(canonical(series(values)))
        if values not in self.allowed:
            raise ValueError("Input is outside the declared finite cue domain")
        base = encode(values, self.mapping)
        row = self.index[key(base.to_dict())]
        labels = [json_answer(answer(values, task, self.plan["threshold"])) for task in self.plan["tasks"]]
        rank = row["labels"].index(labels)
        if row["bits"] == 0:
            return base
        code = self.plan["code"]
        start = base.duration_ms + code["gap_ms"]
        events = list(base.events)
        events.append(Event(start, code["note_ms"], code["delimiter_pitch_cents"], "cue_start"))
        for i, bit in enumerate(format(rank, "0%db" % row["bits"])):
            events.append(Event(start + (i + 1) * code["slot_ms"], code["note_ms"],
                                code["one_pitch_cents"] if bit == "1" else code["zero_pitch_cents"],
                                "cue_one" if bit == "1" else "cue_zero"))
        return Render(tuple(events), start + (row["bits"] + 1) * code["slot_ms"])

    def decode(self, rendered):
        starts = [i for i, event in enumerate(rendered.events) if event.kind == "cue_start"]
        if not starts:
            row = self.index.get(key(rendered.to_dict()))
            if row is None or row["bits"] != 0:
                raise ValueError("Not a valid unambiguous base render")
            return row["labels"][0]
        if len(starts) != 1:
            raise ValueError("Expected exactly one cue delimiter")
        index = starts[0]
        delimiter = rendered.events[index]
        code = self.plan["code"]
        base_duration = delimiter.onset_ms - code["gap_ms"]
        base = Render(rendered.events[:index], base_duration)
        row = self.index.get(key(base.to_dict()))
        tail = rendered.events[index + 1:]
        if row is None or len(tail) != row["bits"] or row["bits"] == 0:
            raise ValueError("Cue length or base does not match codebook")
        if delimiter != Event(base_duration + code["gap_ms"], code["note_ms"], code["delimiter_pitch_cents"], "cue_start"):
            raise ValueError("Invalid delimiter")
        bits = ""
        for i, event in enumerate(tail):
            bit = "1" if event.kind == "cue_one" else "0" if event.kind == "cue_zero" else None
            if bit is None:
                raise ValueError("Invalid cue event kind")
            expected = Event(delimiter.onset_ms + (i + 1) * code["slot_ms"], code["note_ms"],
                             code["one_pitch_cents"] if bit == "1" else code["zero_pitch_cents"], event.kind)
            if event != expected:
                raise ValueError("Invalid cue timing or pitch")
            bits += bit
        if rendered.duration_ms != delimiter.onset_ms + (len(tail) + 1) * code["slot_ms"]:
            raise ValueError("Invalid render duration")
        rank = int(bits, 2)
        if rank >= len(row["labels"]):
            raise ValueError("Unused binary word")
        return row["labels"][rank]


def verify_plan(plan):
    try:
        if not same_json(plan, build_plan(Mapping(**plan["mapping"]), plan["domain"], plan["tasks"], plan["threshold"])):
            return False
        encoder = CueEncoder(plan)
        for values in domain_corpus(plan["domain"]):
            expected = [json_answer(answer(values, task, plan["threshold"])) for task in plan["tasks"]]
            if encoder.decode(encoder.encode(values)) != expected:
                return False
        return True
    except (KeyError, TypeError, ValueError, IndexError):
        return False
