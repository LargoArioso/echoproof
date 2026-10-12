"""Exhaustive finite enumeration and portable collision witnesses."""
from collections import Counter
from dataclasses import replace
from itertools import product
import hashlib
import json
from .serialization import same_json
from .model import Mapping, encode, number, series
from .tasks import TASKS, answer, json_answer

MAX_SERIES = 200000
MAX_LENGTH = 128


def canonical(values):
    return [None if x is None else str(number(x)) for x in values]


def witness(left, right, mapping, task, threshold):
    rendered = encode(left, mapping)
    return {"left": canonical(left), "right": canonical(right), "task": task,
            "threshold": str(number(threshold)), "left_answer": json_answer(answer(left, task, threshold)),
            "right_answer": json_answer(answer(right, task, threshold)),
            "mapping": mapping.to_dict(), "render": rendered.to_dict(),
            "claim": "exact_render_collision"}


def verify_witness(record):
    """Recompute both sides, answers and the claimed event sequence; fail closed."""
    try:
        if record["claim"] != "exact_render_collision":
            return False
        mapping = Mapping(**record["mapping"])
        left, right = record["left"], record["right"]
        task, threshold = record["task"], record["threshold"]
        a, b = answer(left, task, threshold), answer(right, task, threshold)
        ra, rb = encode(left, mapping), encode(right, mapping)
        return (a != b and ra == rb and same_json(ra.to_dict(), record["render"])
                and same_json(json_answer(a), record["left_answer"]) and same_json(json_answer(b), record["right_answer"]))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def minimize(record, with_trace=False):
    """Paired deletion to a 1-minimal witness; not a globally shortest proof."""
    if not verify_witness(record):
        raise ValueError("Cannot minimize an invalid collision witness")
    left, right = list(record["left"]), list(record["right"])
    retained_left, retained_right = list(range(len(left))), list(range(len(right)))
    removed = []
    mapping, task, threshold = Mapping(**record["mapping"]), record["task"], record["threshold"]
    changed = True
    while changed and len(left) == len(right) and len(left) > 1:
        changed = False
        for index in range(len(left)):
            a, b = left[:index] + left[index + 1:], right[:index] + right[index + 1:]
            if encode(a, mapping) == encode(b, mapping) and answer(a, task, threshold) != answer(b, task, threshold):
                removed.append(retained_left[index])
                retained_left.pop(index)
                retained_right.pop(index)
                left, right, changed = a, b, True
                break
    result = witness(left, right, mapping, task, threshold)
    result["minimization"] = "paired-deletion 1-minimal" if len(left) == len(right) else "not applicable to unequal lengths"
    if not with_trace:
        return result
    trace = {"schema_version": 1, "claim_type": "paired_deletion_trace",
             "original": witness(record["left"], record["right"], mapping, task, threshold),
             "final": result, "removed_original_indices": removed,
             "retained_left_indices": retained_left, "retained_right_indices": retained_right,
             "status": "one_minimal" if len(left) == len(right) else "not_applicable",
             "audit_identity_sha256": None,
             "scope": "Replayed paired deletions preserve exact event collision and task disagreement at every step. When paired deletion applies, the final witness is one-minimal, not globally shortest. Original domain membership requires a separately verified parent audit; source-file authenticity requires its own check."}
    return result, trace


def audit(mapping, levels, lengths=(2, 3, 4), tasks=TASKS, threshold="5", include_missing=False):
    levels = tuple(dict.fromkeys(str(number(x)) for x in levels))
    lengths = tuple(sorted(set(lengths)))
    tasks = tuple(dict.fromkeys(tasks))
    number(threshold)
    if not levels or not lengths or any(type(n) is not int or not 1 <= n <= MAX_LENGTH for n in lengths):
        raise ValueError("Nonempty levels and integer lengths in 1..%d required" % MAX_LENGTH)
    if not tasks or any(task not in TASKS for task in tasks):
        raise ValueError("At least one supported task required")
    alphabet = tuple(number(x) for x in levels) + ((None,) if include_missing else ())
    count = sum(len(alphabet) ** n for n in lengths)
    if count > MAX_SERIES:
        raise ValueError("Search exceeds %d series; narrow the alphabet/lengths" % MAX_SERIES)
    domain = {"levels": list(levels), "lengths": list(lengths), "include_missing": include_missing,
              "threshold": str(number(threshold))}
    sequences = (values for length in lengths for values in product(alphabet, repeat=length))
    return _audit_collection(mapping, sequences, tasks, threshold, domain, "exhaustive_finite_grid", count)


def audit_explicit(mapping, sequences, tasks=TASKS, threshold="5", provenance=None):
    """Exact analysis of an explicit input corpus, without a coverage claim beyond it."""
    tasks = tuple(dict.fromkeys(tasks))
    if not tasks or any(task not in TASKS for task in tasks):
        raise ValueError("At least one supported task required")
    number(threshold)
    unique = {}
    for values in sequences:
        normalized = tuple(canonical(series(values)))
        if len(normalized) > MAX_LENGTH:
            raise ValueError("Explicit series exceeds %d samples" % MAX_LENGTH)
        unique.setdefault(normalized, None)
        if len(unique) > MAX_SERIES:
            raise ValueError("Too many explicit series")
    if not unique:
        raise ValueError("At least one explicit series required")
    corpus = list(unique)
    domain = {"series": [list(values) for values in corpus], "threshold": str(number(threshold)),
              "provenance": provenance or "explicit input corpus"}
    return _audit_collection(mapping, corpus, tasks, threshold, domain, "explicit_finite_corpus", len(corpus))


def _audit_collection(mapping, sequences, tasks, threshold, domain, mode, count):
    buckets = {}
    first = {}
    originals = {}
    traces = {}
    for values in sequences:
        values = series(values)
        rendered = encode(values, mapping)
        answers = {task: answer(values, task, threshold) for task in tasks}
        if rendered not in buckets:
            buckets[rendered] = {"size": 1, "labels": None,
                                 "representative": values, "answers": answers}
            continue
        bucket = buckets[rendered]
        bucket["size"] += 1
        if bucket["labels"] is None:
            bucket["labels"] = {task: Counter({label: 1}) for task, label in bucket["answers"].items()}
        for task in tasks:
            label = answers[task]
            if label != bucket["answers"][task] and task not in first:
                originals[task] = witness(bucket["representative"], values, mapping, task, threshold)
                first[task], traces[task] = minimize(originals[task], with_trace=True)
            bucket["labels"][task][label] += 1
    task_results = {}
    for task in tasks:
        ambiguous = 0
        disagreeing_pairs = 0
        affected_series = 0
        for bucket in buckets.values():
            if bucket["labels"] is None:
                continue
            counts = bucket["labels"][task]
            if len(counts) > 1:
                ambiguous += 1
                affected_series += bucket["size"]
                disagreeing_pairs += (bucket["size"] ** 2 - sum(n * n for n in counts.values())) // 2
        task_results[task] = {"ambiguous_render_classes": ambiguous, "affected_series": affected_series,
                              "disagreeing_pairs": disagreeing_pairs, "witness": first.get(task), "original_witness": originals.get(task), "minimization_trace": traces.get(task),
                              "status": "collision_found" if ambiguous else "no_collision_on_grid" if mode == "exhaustive_finite_grid" else "no_collision_in_explicit_corpus"}
    identity = json.dumps({"domain": domain, "mapping": mapping.to_dict(), "tasks": list(tasks)}, sort_keys=True).encode()
    identity_hash = hashlib.sha256(identity).hexdigest()
    for trace in traces.values():
        trace["audit_identity_sha256"] = identity_hash
    return {"schema_version": 1, "claim_type": "finite_task_audit", "engine_version": "0.1.0", "mapping": mapping.to_dict(), "domain": domain, "task_order": list(tasks),
            "search": {"mode": mode, "series_count": count,
                       "render_classes": len(buckets), "collision_classes": sum(b["size"] > 1 for b in buckets.values()),
                       "equal_render_pairs": sum(b["size"] * (b["size"] - 1) // 2 for b in buckets.values()),
                       "identity_sha256": identity_hash},
            "tasks": task_results,
            "scope": "Exact event equality in EchoProof's discrete renderer. No human perceptual claim; no guarantee outside this finite grid or explicitly listed corpus."}


def repair_candidates(mapping, levels=None):
    """Transparent alternatives, never labelled universally safe."""
    low, high = number(mapping.domain_low), number(mapping.domain_high)
    if levels:
        low = min(low, *(number(x) for x in levels))
        high = max(high, *(number(x) for x in levels))
    variants = [("retain_missing", replace(mapping, missing="marker")),
                ("retain_every_sample", replace(mapping, stride=1)),
                ("shared_scale", replace(mapping, normalization="fixed")),
                ("cover_grid_domain", replace(mapping, normalization="fixed", domain_low=str(low), domain_high=str(high))),
                ("finer_pitch", replace(mapping, pitch_step_cents=10)),
                ("combined", replace(mapping, normalization="fixed", domain_low=str(low), domain_high=str(high), missing="marker", stride=1, pitch_step_cents=10))]
    seen = {mapping}
    for label, candidate in variants:
        if candidate not in seen:
            seen.add(candidate)
            yield label, candidate


def verify_audit(record):
    """Replay the full finite declaration, not merely a supplied witness.

    Source provenance is retained as supplied; source-file association must be
    validated separately. No continuous or human-perceptual claim is added.
    """
    try:
        if record["claim_type"] != "finite_task_audit":
            return False
        mapping = Mapping(**record["mapping"])
        domain, tasks = record["domain"], record["task_order"]
        if record["search"]["mode"] == "exhaustive_finite_grid":
            fresh = audit(mapping, domain["levels"], domain["lengths"], tasks, domain["threshold"], domain["include_missing"])
        elif record["search"]["mode"] == "explicit_finite_corpus":
            fresh = audit_explicit(mapping, domain["series"], tasks, domain["threshold"], domain["provenance"])
        else:
            return False
        return same_json(record, fresh)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return False
