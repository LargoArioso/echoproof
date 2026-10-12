"""Fixed-meaning threshold/trend earcons; no per-render conditional codebook.

This adds a globally fixed answer channel. It does not establish human learning
or perception, and it is not claimed to be optimal in time or information bits.
"""
from .serialization import same_json
from .model import Mapping, Render, Event, encode, series, number
from .tasks import answer
from .cues import domain_corpus

SUPPORTED = ("threshold", "endpoint_trend")
PATTERNS = {
    "threshold": {False: (6000, 4800), True: (4800, 6000)},
    "endpoint_trend": {"rising": (4800, 5400, 6000), "falling": (6000, 5400, 4800),
                       "flat": (5400, 5400, 5400), "undefined": (3600, 3600, 3600)},
}
HEADER_PITCH = {"threshold": 3600, "endpoint_trend": 3900}
SLOT_MS, NOTE_MS, GAP_MS = 180, 120, 240


def packet(task, label, start_ms=0):
    try:
        pitches = PATTERNS[task][label]
    except (KeyError, TypeError) as exc:
        raise ValueError("Unsupported semantic cue task/answer") from exc
    events = [Event(start_ms, NOTE_MS, HEADER_PITCH[task], "semantic_" + task + "_header")]
    for index, pitch in enumerate(pitches, start=1):
        kind = "semantic_unknown" if label == "undefined" else "semantic_answer"
        events.append(Event(start_ms + index * SLOT_MS, NOTE_MS, pitch, kind))
    return tuple(events), start_ms + len(events) * SLOT_MS


def legend():
    return [{"task": task, "answer": label, "render": Render(events, duration).to_dict()}
            for task in SUPPORTED for label in PATTERNS[task]
            for events, duration in (packet(task, label),)]


class SemanticCueEncoder:
    def __init__(self, mapping=Mapping(), tasks=SUPPORTED, threshold="5"):
        tasks = tuple(dict.fromkeys(tasks))
        if not tasks or any(t not in SUPPORTED for t in tasks):
            raise ValueError("Fixed semantic cues support threshold and endpoint_trend only")
        self.mapping, self.tasks, self.threshold = mapping, tasks, str(number(threshold))

    def encode(self, values):
        values = series(values)
        base = encode(values, self.mapping)
        events = list(base.events)
        end = base.duration_ms
        for task in self.tasks:
            additions, end = packet(task, answer(values, task, self.threshold), end + GAP_MS)
            events.extend(additions)
        return Render(tuple(events), end)

    def decode(self, rendered):
        headers = {"semantic_" + task + "_header" for task in SUPPORTED}
        first = next((i for i, e in enumerate(rendered.events) if e.kind in headers), None)
        if first is None:
            raise ValueError("No semantic cue header")
        events = rendered.events[first:]
        # The original prefix is deliberately not used as a conditional codebook.
        base_duration = events[0].onset_ms - GAP_MS
        if base_duration < 0 or any(e.kind not in ("tone", "missing") or e.onset_ms < 0 or e.duration_ms <= 0 or e.onset_ms + e.duration_ms > base_duration for e in rendered.events[:first]):
            raise ValueError("Invalid original event prefix")
        offset = 0
        previous_end = base_duration
        labels = {}
        for task in self.tasks:
            header_kind = "semantic_" + task + "_header"
            if offset >= len(events) or events[offset].kind != header_kind:
                raise ValueError("Unexpected semantic task order")
            matched = None
            for label in PATTERNS[task]:
                expected, end = packet(task, label, previous_end + GAP_MS)
                if events[offset:offset + len(expected)] == expected:
                    matched = (label, len(expected), end)
                    break
            if matched is None:
                raise ValueError("Invalid semantic cue timing, pitch, or kind")
            label, length, previous_end = matched
            labels[task] = label
            offset += length
        if offset != len(events) or rendered.duration_ms != previous_end:
            raise ValueError("Unexpected semantic cue tail or duration")
        return labels


def plan(mapping, tasks=SUPPORTED, threshold="5"):
    encoder = SemanticCueEncoder(mapping, tasks, threshold)
    return {"schema_version": 1, "claim_type": "fixed_semantic_cue_definition", "mapping": mapping.to_dict(),
            "tasks": list(encoder.tasks), "threshold": encoder.threshold, "legend": legend(),
            "scope": "Fixed event-level answer vocabulary for arbitrary finite input series under this encoder. No finite-domain codebook; no human learning/perception or optimality claim."}


def validate_domain(definition, domain):
    if "threshold" in domain and number(domain["threshold"]) != number(definition["threshold"]):
        raise ValueError("Domain and semantic definition thresholds must agree")
    fresh = plan(Mapping(**definition["mapping"]), definition["tasks"], definition["threshold"])
    if not same_json(definition, fresh):
        raise ValueError("Invalid semantic cue definition")
    encoder = SemanticCueEncoder(Mapping(**definition["mapping"]), definition["tasks"], definition["threshold"])
    corpus = domain_corpus(domain)
    classes = {}
    examples = []
    example_base = None
    added = set()
    for values in corpus:
        base = encode(values, encoder.mapping)
        augmented = encoder.encode(values)
        expected = {t: answer(values, t, encoder.threshold) for t in encoder.tasks}
        if encoder.decode(augmented) != expected:
            raise AssertionError("Semantic cue roundtrip failed")
        if augmented in classes and classes[augmented] != expected:
            raise AssertionError("Task answers collide after augmentation")
        classes[augmented] = expected
        added.add(augmented.duration_ms - base.duration_ms)
        if not examples:
            examples.append({"values": list(values), "answers": expected, "base": base.to_dict(), "cued": augmented.to_dict()})
            example_base = base
        elif len(examples) == 1 and base == example_base and expected != examples[0]["answers"]:
            examples.append({"values": list(values), "answers": expected, "base": base.to_dict(), "cued": augmented.to_dict()})
    return {"schema_version": 1, "claim_type": "fixed_semantic_cue_validation", "definition": fresh,
            "domain": domain, "statistics": {"checked_series": len(corpus), "augmented_render_classes": len(classes),
                                              "decode_failures": 0, "answer_collision_classes": 0,
                                              "added_duration_ms": sorted(added)},
            "examples": examples,
            "scope": "Exact decoding and task separation exhaustively checked on this declared finite domain. Fixed vocabulary supports other finite inputs by construction, without a separate human perceptual or learning claim."}


def verify_validation(record):
    try:
        return same_json(record, validate_domain(record["definition"], record["domain"]))
    except (KeyError, TypeError, ValueError, AssertionError):
        return False
