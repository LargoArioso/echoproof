"""Construct exact range adjustments that put a threshold on a pitch transition.

Keep the pitch vocabulary and discrete step intact. Search both one-endpoint
families, retaining only ranges covering the entire declared input interval.
"""
from dataclasses import replace
from fractions import Fraction
from .serialization import same_json
from .model import Mapping, number
from .intervals import threshold_certificate, transitions


def align_threshold(mapping, threshold, input_low, input_high, limit=4):
    threshold, input_low, input_high = map(number, (threshold, input_low, input_high))
    if input_high < input_low:
        raise ValueError("Reversed input interval")
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Alignment candidate limit must be in 1..16")
    if mapping.stride != 1:
        raise ValueError("Range alignment cannot recover skipped samples; require stride = 1")
    low, high = number(mapping.domain_low), number(mapping.domain_high)
    mapping = replace(mapping, domain_low=str(low), domain_high=str(high))
    span = mapping.pitch_high_cents - mapping.pitch_low_cents
    step = mapping.pitch_step_cents
    count = Fraction(span, step) + Fraction(1, 2)
    count = count.numerator // count.denominator
    candidates = {}
    baseline = threshold_certificate(mapping, threshold, input_low, input_high)
    if baseline["status"] == "preserved":
        candidates[mapping] = {"operation": "already_preserved", "mapping": mapping.to_dict(),
                               "normalized_endpoint_change": "0", "transition_index": None, "certificate": baseline}
    # Keep the full original range as well as the declared admissible interval.
    covered_low, covered_high = min(low, input_low), max(high, input_high)
    for index in range(count):
        fraction = Fraction((2 * index + 1) * step, 2 * span)
        solutions = [(low, low + (threshold - low) / fraction, "adjust_high")]
        if fraction != 1:
            solutions.append(((threshold - fraction * high) / (1 - fraction), high, "adjust_low"))
        for new_low, new_high, operation in solutions:
            if not new_low < new_high or new_low > covered_low or new_high < covered_high:
                continue
            candidate = replace(mapping, normalization="fixed", domain_low=str(new_low), domain_high=str(new_high))
            distance = (abs(new_low - low) + abs(new_high - high)) / (high - low)
            candidates.setdefault(candidate, {"operation": operation, "mapping": candidate.to_dict(),
                                      "normalized_endpoint_change": str(distance),
                                      "transition_index": index})
    ordered = sorted(candidates.values(), key=lambda c: (number(c["normalized_endpoint_change"]), c["operation"], c["transition_index"]))[:limit]
    old_boundaries = tuple(t for t in transitions(mapping) if input_low < t <= input_high) if mapping.normalization == "fixed" else ()
    for candidate in ordered:
        revised = Mapping(**candidate["mapping"])
        certificate = threshold_certificate(revised, threshold, input_low, input_high)
        if certificate["status"] != "preserved":
            raise AssertionError("Constructed alignment failed its preservation proof")
        candidate["certificate"] = certificate
        new_boundaries = set(transitions(revised))
        candidate["previously_preserved_thresholds_lost"] = [str(t) for t in old_boundaries if t not in new_boundaries]
    return {"schema_version": 1, "claim_type": "threshold_range_alignment", "original_mapping": mapping.to_dict(),
            "threshold": str(threshold), "input_low": str(input_low), "input_high": str(input_high), "limit": limit,
            "candidates": ordered,
            "search": {"families": ["hold low endpoint and adjust high", "hold high endpoint and adjust low"],
                       "admissible_candidates": len(candidates), "pitch_steps_considered": count},
            "scope": "Exact threshold preservation certificates for the declared closed input interval, no missing samples. Pitch range and step unchanged; fixed normalization. Ranking minimizes endpoint displacement only within these one-endpoint families, not human perception or a global design optimum."}


def verify_alignment(record):
    try:
        return same_json(record, align_threshold(Mapping(**record["original_mapping"]), record["threshold"], record["input_low"], record["input_high"], record["limit"]))
    except (KeyError, TypeError, ValueError):
        return False
