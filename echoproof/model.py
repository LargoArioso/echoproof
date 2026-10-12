"""Exact rational mapping into a deliberately small discrete sound language.

An equality certificate concerns this language and its deterministic renderer,
not an arbitrary external player or a model of human hearing.
"""
from dataclasses import dataclass, asdict
from fractions import Fraction
from functools import lru_cache
from typing import Optional, Tuple


def number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean values are not data measurements")
    if isinstance(value, Fraction):
        return value
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Expected a finite numeric value, got %r" % value) from exc


def series(values):
    normalized = tuple(None if x is None else number(x) for x in values)
    if not normalized:
        raise ValueError("A series must contain at least one sample")
    return normalized


@dataclass(frozen=True)
class Mapping:
    domain_low: str = "0"
    domain_high: str = "10"
    normalization: str = "fixed"
    pitch_low_cents: int = 4800
    pitch_high_cents: int = 8400
    pitch_step_cents: int = 100
    missing: str = "silence"
    stride: int = 1
    note_ms: int = 180
    slot_ms: int = 240

    def __post_init__(self):
        low, high = number(self.domain_low), number(self.domain_high)
        if high <= low:
            raise ValueError("domain_high must exceed domain_low")
        if self.normalization not in ("fixed", "per_series"):
            raise ValueError("normalization must be fixed or per_series")
        if self.missing not in ("silence", "zero", "skip", "marker"):
            raise ValueError("Unsupported missing policy")
        for name in ("pitch_low_cents", "pitch_high_cents", "pitch_step_cents", "stride", "note_ms", "slot_ms"):
            value = getattr(self, name)
            if type(value) is not int:
                raise ValueError(name + " must be an integer")
        if not 0 <= self.pitch_low_cents < self.pitch_high_cents <= 12700:
            raise ValueError("Pitch bounds must ascend inside 0..12700 MIDI cents")
        if self.pitch_step_cents <= 0 or self.stride <= 0:
            raise ValueError("Pitch step and stride must be positive")
        if not 0 < self.note_ms <= self.slot_ms:
            raise ValueError("Require 0 < note_ms <= slot_ms")

    def to_dict(self):
        result = asdict(self)
        result["domain_low"] = str(number(self.domain_low))
        result["domain_high"] = str(number(self.domain_high))
        return result


@dataclass(frozen=True)
class Event:
    onset_ms: int
    duration_ms: int
    pitch_cents: int
    kind: str = "tone"


@dataclass(frozen=True)
class Render:
    events: Tuple[Event, ...]
    duration_ms: int

    def to_dict(self):
        return {"events": [asdict(e) for e in self.events], "duration_ms": self.duration_ms}


@lru_cache(maxsize=8192)
def _event(onset_ms, duration_ms, pitch_cents, kind="tone"):
    # Immutable events can be shared by many complete renders. The bounded cache
    # avoids retaining arbitrary caller-generated pitches/timings indefinitely.
    return Event(onset_ms, duration_ms, pitch_cents, kind)


def encode(values, mapping=Mapping()):
    values = series(values)
    observed = [x for x in values if x is not None]
    low, high = number(mapping.domain_low), number(mapping.domain_high)
    if mapping.normalization == "per_series" and observed:
        low, high = min(observed), max(observed)
    events = []
    slots = 0
    for index in range(0, len(values), mapping.stride):
        value = values[index]
        if value is None and mapping.missing == "skip":
            continue
        onset = slots * mapping.slot_ms
        slots += 1
        if value is None:
            if mapping.missing == "silence":
                continue
            if mapping.missing == "marker":
                events.append(_event(onset, mapping.note_ms, 3600, "missing"))
                continue
            value = Fraction(0)
        position = Fraction(1, 2) if high == low else (value - low) / (high - low)
        position = max(Fraction(0), min(Fraction(1), position))
        raw = mapping.pitch_low_cents + position * (mapping.pitch_high_cents - mapping.pitch_low_cents)
        # Quantize relative to pitch_low, round ties upward, then clamp.
        steps = (raw - mapping.pitch_low_cents) / mapping.pitch_step_cents
        rounded = (steps + Fraction(1, 2)).numerator // (steps + Fraction(1, 2)).denominator
        pitch = min(mapping.pitch_high_cents, mapping.pitch_low_cents + rounded * mapping.pitch_step_cents)
        events.append(_event(onset, mapping.note_ms, pitch))
    return Render(tuple(events), slots * mapping.slot_ms)
