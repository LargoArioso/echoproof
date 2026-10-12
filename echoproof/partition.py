"""Task-aligned nonuniform pitch bins, with a scoped alphabet lower bound.

This changes the geometry of the mapping. It does not contradict infeasibility
results for uniform linear quantization, or claim a perceptual optimum.
"""
from bisect import bisect_right
from fractions import Fraction
from .model import Mapping, Event, Render, number, series
from .serialization import same_json


def partition_thresholds(mapping, thresholds, input_low, input_high):
    low, high = number(input_low), number(input_high)
    queries = sorted(set(number(t) for t in thresholds))
    if not 1 <= len(queries) <= 64:
        raise ValueError("Require 1..64 distinct thresholds")
    if not low < high:
        raise ValueError("Require a positive closed input interval")
    if low > number(mapping.domain_low) or high < number(mapping.domain_high):
        raise ValueError("Input interval must cover the original mapping range")
    if mapping.normalization != "fixed" or mapping.stride != 1:
        raise ValueError("Partition construction requires a fixed mapping and stride = 1")
    span = mapping.pitch_high_cents - mapping.pitch_low_cents
    rounded = Fraction(span, mapping.pitch_step_cents) + Fraction(1, 2)
    transitions = rounded.numerator // rounded.denominator
    palette = [min(mapping.pitch_high_cents, mapping.pitch_low_cents + k*mapping.pitch_step_cents)
               for k in range(transitions + 1)]
    cuts = [t for t in queries if low < t <= high]
    required = len(cuts) + 1
    # Every cut introduces a distinct single-sample answer vector. With fixed
    # timing and exactly one pitch per sample, its alphabet must separate them.
    representatives = [low] + cuts
    vectors = [[x >= t for t in queries] for x in representatives]
    record = {"schema_version": 1, "claim_type": "nonuniform_threshold_partition",
              "original_mapping": mapping.to_dict(), "input_low": str(low), "input_high": str(high),
              "thresholds": list(map(str, queries)), "cutpoints": list(map(str, cuts)),
              "available_pitches_cents": palette,
              "lower_bound": {"required_pitch_symbols": required,
                              "singleton_representatives": list(map(str, representatives)),
                              "distinct_answer_vectors": vectors,
                              "scope": "Exactly one pitch event per sample, fixed onset and duration, no other data-bearing channel. Bound follows from distinct singleton answer vectors."},
              "scope": "All positive-length series of real values in the declared closed interval, no missing samples. Monotone nonuniform bins, inclusive threshold boundaries, original pitch vocabulary and fixed timing retained. Each event preserves every requested threshold predicate, hence occurrence indices and counts as well as any/all decisions. Event-level sufficiency only; no human listening claim or numerical-value recovery."}
    if required > len(palette):
        return dict(record, status="impossible", selected_pitches_cents=[],
                    reason="Required singleton answer classes exceed the original pitch alphabet")
    if required == 1:
        indices = [0]
    else:
        indices = []
        for i in range(required):
            position = Fraction(i*transitions, required-1) + Fraction(1, 2)
            indices.append(position.numerator // position.denominator)
    selected = [palette[i] for i in indices]
    assert len(set(selected)) == required
    return dict(record, status="preserved", selected_pitches_cents=selected,
                reason="Every requested nonconstant threshold is a bin boundary; the construction attains the scoped alphabet lower bound")


def verify_partition(record):
    try:
        return same_json(record, partition_thresholds(Mapping(**record["original_mapping"]), record["thresholds"], record["input_low"], record["input_high"]))
    except (KeyError, TypeError, ValueError):
        return False


class PartitionEncoder:
    def __init__(self, record):
        if not verify_partition(record) or record["status"] != "preserved":
            raise ValueError("Require a verified preserved partition")
        self.mapping = Mapping(**record["original_mapping"])
        self.low, self.high = number(record["input_low"]), number(record["input_high"])
        self.queries = tuple(map(number, record["thresholds"]))
        self.cuts = tuple(map(number, record["cutpoints"]))
        self.pitches = tuple(record["selected_pitches_cents"])

    def encode(self, values):
        values = series(values)
        if any(x is None or x < self.low or x > self.high for x in values):
            raise ValueError("Partition input must be observed values inside its certified interval")
        events = tuple(Event(i*self.mapping.slot_ms, self.mapping.note_ms,
                             self.pitches[bisect_right(self.cuts, x)]) for i, x in enumerate(values))
        return Render(events, len(values)*self.mapping.slot_ms)

    def _bin_indices(self, render):
        if not isinstance(render, Render) or not render.events:
            raise ValueError("Require a nonempty regular partition render")
        if type(render.duration_ms) is not int or render.duration_ms != len(render.events)*self.mapping.slot_ms:
            raise ValueError("Invalid partition duration")
        bins = []
        for i, event in enumerate(render.events):
            if not isinstance(event, Event) or any(type(getattr(event, field)) is not int for field in ("onset_ms", "duration_ms", "pitch_cents")):
                raise ValueError("Invalid event field types")
            if event.kind != "tone" or event.onset_ms != i*self.mapping.slot_ms or event.duration_ms != self.mapping.note_ms or event.pitch_cents not in self.pitches:
                raise ValueError("Render does not match the partition language")
            bins.append(self.pitches.index(event.pitch_cents))
        return bins

    def decode(self, render):
        highest = max(self._bin_indices(render))
        return {str(t): True if t <= self.low else False if t > self.high
                else highest >= bisect_right(self.cuts, t) for t in self.queries}

    def profiles(self, render):
        bins = self._bin_indices(render)
        result = {}
        for threshold in self.queries:
            indices = [i for i,bin_index in enumerate(bins)
                       if threshold <= self.low or (threshold <= self.high and bin_index >= bisect_right(self.cuts,threshold))]
            result[str(threshold)] = {"sample_count":len(bins), "at_or_above_count":len(indices),
                                      "indices":indices, "any":bool(indices), "all":len(indices)==len(bins),
                                      "first_index":indices[0] if indices else None,
                                      "last_index":indices[-1] if indices else None}
        return result
