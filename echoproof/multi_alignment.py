"""Exact simultaneous threshold alignment for a linear quantized scale.

Two distinct nonconstant thresholds determine a candidate range from their
transition indices. Exhausting those finite indices is complete in this model.
"""
from dataclasses import replace
from fractions import Fraction
from .serialization import same_json
from .model import Mapping, number
from .intervals import threshold_certificate

MAX_INDEX_PAIRS = 200000


def align_thresholds(mapping, thresholds, input_low, input_high, limit=4):
    low, high = map(number, (input_low, input_high))
    values = sorted(set(number(t) for t in thresholds))
    if not 2 <= len(values) <= 16:
        raise ValueError("Require 2..16 distinct thresholds")
    if not low < high or any(not low < t <= high for t in values):
        raise ValueError("Require a positive interval and nonconstant thresholds: input_low < t <= input_high")
    if mapping.stride != 1:
        raise ValueError("Simultaneous alignment requires stride = 1")
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Candidate limit must be in 1..16")
    original_low, original_high = map(number, (mapping.domain_low, mapping.domain_high))
    mapping = replace(mapping, domain_low=str(original_low), domain_high=str(original_high))
    covered_low, covered_high = min(low, original_low), max(high, original_high)
    span, step = mapping.pitch_high_cents - mapping.pitch_low_cents, mapping.pitch_step_cents
    ratio = Fraction(span, step)
    rounded = ratio + Fraction(1, 2)
    count = rounded.numerator // rounded.denominator
    minimum_spacing = (covered_high - covered_low) / ratio
    smallest_gap = min(b-a for a, b in zip(values, values[1:]))
    base = {"schema_version": 1, "claim_type": "simultaneous_threshold_alignment",
            "original_mapping": mapping.to_dict(), "thresholds": list(map(str, values)),
            "input_low": str(low), "input_high": str(high), "limit": limit,
            "constraints": {"covered_low": str(covered_low), "covered_high": str(covered_high),
                            "minimum_transition_spacing": str(minimum_spacing), "smallest_threshold_gap": str(smallest_gap)},
            "scope": "Complete finite search of linear fixed ranges retaining the pitch span and step and covering the original range plus declared closed interval. Positive-length series, no missing samples, stride = 1. Event-level claim, no human listening claim."}
    if count < len(values) or smallest_gap < minimum_spacing:
        reason = "Too few pitch transitions" if count < len(values) else "Distinct thresholds are closer than the minimum possible transition spacing"
        return dict(base, status="impossible", reason=reason, candidates=[], search={"transition_count": count, "index_pairs_checked": 0, "feasible_ranges": 0})
    difference = values[1] - values[0]
    max_gap = difference / minimum_spacing
    max_gap = min(count - 1, max_gap.numerator // max_gap.denominator)
    pair_bound = sum(count-gap for gap in range(1, max_gap+1))
    if pair_bound > MAX_INDEX_PAIRS:
        raise ValueError("Simultaneous alignment exceeds the 200000 transition-index pair search limit")
    candidates, checked = [], 0
    for gap in range(1, max_gap + 1):
        spacing = difference / gap
        offsets = [(t-values[0])/spacing for t in values]
        if any(offset.denominator != 1 for offset in offsets):
            continue
        offsets = [int(offset) for offset in offsets]
        for first in range(count-gap):
            checked += 1
            if first + offsets[-1] >= count:
                continue
            new_low = values[0] - (Fraction(first) + Fraction(1, 2))*spacing
            new_high = new_low + ratio*spacing
            if new_low > covered_low or new_high < covered_high:
                continue
            revised = replace(mapping, normalization="fixed", domain_low=str(new_low), domain_high=str(new_high))
            distance = (abs(new_low-original_low)+abs(new_high-original_high))/(original_high-original_low)
            candidates.append({"mapping": revised.to_dict(), "normalized_endpoint_change": str(distance),
                               "transition_indices": [first+offset for offset in offsets]})
    candidates.sort(key=lambda c: (number(c["normalized_endpoint_change"]), number(c["mapping"]["domain_low"]), number(c["mapping"]["domain_high"])))
    selected = candidates[:limit]
    for candidate in selected:
        revised = Mapping(**candidate["mapping"])
        candidate["certificates"] = [threshold_certificate(revised, t, low, high) for t in values]
        if any(c["status"] != "preserved" for c in candidate["certificates"]):
            raise AssertionError("Simultaneous construction failed exact certificate verification")
    return dict(base, status="preserved" if selected else "impossible", candidates=selected,
                reason="All requested thresholds align" if selected else "No transition-index pair yields a range satisfying all constraints",
                search={"transition_count": count, "index_pairs_checked": checked, "index_pair_upper_bound": pair_bound, "feasible_ranges": len(candidates)})


def verify_multi_alignment(record):
    try:
        return same_json(record, align_thresholds(Mapping(**record["original_mapping"]), record["thresholds"], record["input_low"], record["input_high"], record["limit"]))
    except (KeyError, TypeError, ValueError):
        return False
