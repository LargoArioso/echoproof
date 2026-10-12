"""Task-aware checks of recorded backend outputs, with explicit scope.

Verification here checks the recorded equality and task answers. It does NOT
re-execute or authenticate the external compiler. Re-run the capture script for that.
"""
from collections import Counter
import copy
import hashlib
import json
from .tasks import TASKS, answer, json_answer
from .serialization import same_json
from .model import number, series

SCOPES = ("erie_full_queue", "erie_tone_stream", "highcharts_mapped_instrument")


def strip_datum(value):
    if isinstance(value, list):
        return [strip_datum(x) for x in value]
    if isinstance(value, dict):
        return {key: strip_datum(item) for key, item in value.items() if key != "__datum"}
    return value


def signature(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def project(record, scope):
    if scope == "erie_full_queue":
        raw = record["queue"]
        if not isinstance(raw, dict) or not isinstance(raw.get("queue"), list):
            raise ValueError("Expected an Erie prerendered queue")
        if any(x.get("type") not in ("text", "tone", "tone-series") for x in raw["queue"]):
            raise ValueError("Unsupported queue item type; refusing to silently omit it")
        result = strip_datum(raw)
    elif scope == "erie_tone_stream":
        raw = record["tone"]
        if not isinstance(raw, dict) or not isinstance(raw.get("sounds"), list):
            raise ValueError("Expected an Erie tone stream")
        if raw.get("continued") or raw.get("relative"):
            raise ValueError("Tone projection currently requires discrete, absolute-time events")
        result = strip_datum(raw)
        result["sounds"].sort(key=lambda x: x["start"])
    elif scope == "highcharts_mapped_instrument":
        raw = record["events"]
        if not isinstance(raw, list):
            raise ValueError("Expected a mapped instrument event list")
        for event in raw:
            if not isinstance(event, dict) or set(event) != {"time", "instrumentEventOptions"}:
                raise ValueError("Unknown mapped event fields; refusing to silently omit them")
            if isinstance(event["time"], bool) or not isinstance(event["time"], (int, float)) or event["time"] < 0:
                raise ValueError("Expected nonnegative mapped event time")
            if not isinstance(event["instrumentEventOptions"], dict):
                raise ValueError("Expected complete recorded instrument parameters")
        result = copy.deepcopy(raw)
    else:
        raise ValueError("Unknown compiled audit scope")
    signature(result)  # Reject NaN and Infinity rather than creating an ambiguous recording.
    return result


def recording_witness(left, right, backend, scope, task, threshold):
    a, b = json_answer(answer(left["input"], task, threshold)), json_answer(answer(right["input"], task, threshold))
    projected = project(left, scope)
    return {"schema_version": 1, "claim_type": "compiled_recording_collision", "backend": copy.deepcopy(backend),
            "audit_scope": scope, "task": task, "task_basis": "original_input_series_before_transforms",
            "threshold": str(number(threshold)), "left": copy.deepcopy(left), "right": copy.deepcopy(right),
            "left_answer": a, "right_answer": b, "projection": projected,
            "projection_sha256": hashlib.sha256(signature(projected).encode()).hexdigest(),
            "scope": "Recorded compiler-output equality and task mismatch only. The verifier does not rerun the backend or certify the input-to-output association. Tone and mapped-instrument scopes are partial; Erie full queue scope includes recorded speech."}


def verify_recording_witness(record):
    try:
        if record["claim_type"] != "compiled_recording_collision" or record["task_basis"] != "original_input_series_before_transforms":
            return False
        left, right = record["left"], record["right"]
        scope, task, threshold = record["audit_scope"], record["task"], record["threshold"]
        a, b = json_answer(answer(left["input"], task, threshold)), json_answer(answer(right["input"], task, threshold))
        projected = project(left, scope)
        return (a != b and same_json(a, record["left_answer"]) and same_json(b, record["right_answer"])
                and same_json(projected, project(right, scope)) and same_json(projected, record["projection"])
                and hashlib.sha256(signature(projected).encode()).hexdigest() == record["projection_sha256"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def audit_compiled(corpus, scope="erie_full_queue", tasks=TASKS, threshold="5"):
    records = corpus["records"]
    backend = corpus["backend"]
    tasks = tuple(dict.fromkeys(tasks))
    if not records or len(records) > 10000:
        raise ValueError("Compiled corpus must contain 1..10000 recordings")
    if not tasks or any(t not in TASKS for t in tasks):
        raise ValueError("Unknown or empty compiled audit tasks")
    threshold = str(number(threshold))
    buckets = {}
    witnesses = {}
    seen = set()
    for record in records:
        normalized = tuple(None if x is None else str(x) for x in series(record["input"]))
        if normalized in seen:
            raise ValueError("Duplicate input recordings; audit repeated determinism separately")
        seen.add(normalized)
        projected = project(record, scope)
        key = signature(projected)
        labels = {task: answer(record["input"], task, threshold) for task in tasks}
        if key not in buckets:
            buckets[key] = {"representative": record, "answers": labels, "size": 0,
                            "counts": {t: Counter() for t in tasks}}
        bucket = buckets[key]
        bucket["size"] += 1
        for task in tasks:
            if labels[task] != bucket["answers"][task] and task not in witnesses:
                witnesses[task] = recording_witness(bucket["representative"], record, backend, scope, task, threshold)
            bucket["counts"][task][labels[task]] += 1
    result_tasks = {}
    for task in tasks:
        pairs = sum((b["size"] ** 2 - sum(n * n for n in b["counts"][task].values())) // 2 for b in buckets.values())
        result_tasks[task] = {"status": "recorded_collision_found" if pairs else "no_collision_in_recorded_corpus",
                              "disagreeing_pairs": pairs, "witness": witnesses.get(task)}
    return {"schema_version": 1, "claim_type": "compiled_corpus_audit", "backend": backend, "audit_scope": scope,
            "task_basis": "original_input_series_before_transforms", "threshold": threshold,
            "recording_count": len(records), "projection_classes": len(buckets), "tasks": result_tasks,
            "source_corpus_sha256": hashlib.sha256(signature(corpus).encode()).hexdigest(),
            "scope": "Finite recorded corpus only; backend association requires rerunning the producer. Aggregation can intentionally remove detail: a task mismatch is not automatically a library bug."}
