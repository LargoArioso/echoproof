"""Threshold preservation over an entire closed real-valued input interval.

Scope: fixed scale, stride one, no missing data, positive-length series.
All endpoints, transitions, and constructed witnesses use rational arithmetic.
"""
from fractions import Fraction
from .audit import witness, verify_witness
from .serialization import same_json
from .model import Mapping, number


def transitions(mapping):
    if mapping.normalization != "fixed":
        raise ValueError("Analytic transitions require fixed normalization")
    low, high = number(mapping.domain_low), number(mapping.domain_high)
    span = mapping.pitch_high_cents - mapping.pitch_low_cents
    step = mapping.pitch_step_cents
    rounded_max = Fraction(span, step) + Fraction(1, 2)
    count = rounded_max.numerator // rounded_max.denominator
    # At most 12700 transitions under Mapping's pitch limits.
    return tuple(low + Fraction((2 * k + 1) * step, 2 * span) * (high - low) for k in range(count))


def threshold_certificate(mapping, threshold, input_low, input_high):
    threshold, input_low, input_high = map(number, (threshold, input_low, input_high))
    if input_high < input_low:
        raise ValueError("input_high must be >= input_low")
    base = {"schema_version": 1, "claim_type": "continuous_interval_threshold", "mapping": mapping.to_dict(),
            "threshold": str(threshold), "input_low": str(input_low), "input_high": str(input_high),
            "assumptions": ["no missing samples", "positive-length series", "fixed scale", "stride = 1"],
            "scope": "All real sample values in the declared closed interval, under EchoProof's exact mapping; event-level result, not a listening study."}
    if mapping.normalization != "fixed" or mapping.stride != 1:
        return dict(base, status="unsupported", reason="This analytic proof requires a fixed scale and stride = 1.")
    if threshold <= input_low or threshold > input_high:
        return dict(base, status="preserved", reason="The threshold answer is constant on this entire interval.", witness=None)
    bounds = transitions(mapping)
    if threshold in bounds:
        return dict(base, status="preserved", reason="The threshold is exactly a pitch transition; lower samples map below its pitch and higher samples at or above it.", witness=None,
                    transition=str(threshold))
    lower_bounds = [b for b in bounds if b < threshold]
    cell_low = max(input_low, lower_bounds[-1]) if lower_bounds else input_low
    left = (cell_low + threshold) / 2
    record = witness([left], [threshold], mapping, "threshold", threshold)
    if not verify_witness(record):
        raise AssertionError("Constructed analytic witness failed exact verification")
    return dict(base, status="collision_found", reason="A single pitch cell contains values on both sides of the threshold.", witness=record)


def verify_threshold_certificate(record):
    try:
        fresh = threshold_certificate(Mapping(**record["mapping"]), record["threshold"], record["input_low"], record["input_high"])
        return same_json(record, fresh)
    except (KeyError, TypeError, ValueError):
        return False
