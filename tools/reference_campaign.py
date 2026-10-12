"""Fixed-seed differential checks against an independent integer-ratio oracle.

The oracle does not import Fraction, encode, tasks.answer, or dataclass Render.
It evaluates the declared mapping contract using integer cross multiplication.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from echoproof import Mapping, encode
from echoproof.tasks import answer, json_answer, TASKS


@dataclass(frozen=True)
class Ratio:
    n: int
    d: int = 1

    def __post_init__(self):
        if self.d == 0:
            raise ValueError('Zero denominator')
        divisor = math.gcd(self.n, self.d)
        sign = -1 if self.d < 0 else 1
        object.__setattr__(self, 'n', sign * self.n // divisor)
        object.__setattr__(self, 'd', sign * self.d // divisor)

    def __lt__(self, other):
        return self.n * other.d < other.n * self.d

    def __add__(self, other):
        return Ratio(self.n * other.d + other.n * self.d, self.d * other.d)

    def __sub__(self, other):
        return Ratio(self.n * other.d - other.n * self.d, self.d * other.d)

    def __mul__(self, other):
        return Ratio(self.n * other.n, self.d * other.d)

    def __truediv__(self, other):
        return Ratio(self.n * other.d, self.d * other.n)

    def __str__(self):
        return str(self.n) if self.d == 1 else '%d/%d' % (self.n, self.d)


def parse(value):
    text = str(value)
    if '/' in text:
        numerator, denominator = text.split('/')
        return Ratio(int(numerator), int(denominator))
    decimal = Decimal(text)
    parts = decimal.as_tuple()
    coefficient = int(''.join(str(x) for x in parts.digits))
    if parts.sign:
        coefficient = -coefficient
    return Ratio(coefficient * 10 ** max(0, parts.exponent), 10 ** max(0, -parts.exponent))


def reference_render(values, spec):
    values = [None if x is None else parse(x) for x in values]
    low, high = parse(spec.domain_low), parse(spec.domain_high)
    observed = [x for x in values if x is not None]
    if spec.normalization == 'per_series' and observed:
        low, high = min(observed), max(observed)
    events = []
    slots = 0
    for value in values[::spec.stride]:
        if value is None and spec.missing == 'skip':
            continue
        onset = slots * spec.slot_ms
        slots += 1
        if value is None:
            if spec.missing == 'silence':
                continue
            if spec.missing == 'marker':
                events.append({'onset_ms': onset, 'duration_ms': spec.note_ms, 'pitch_cents': 3600, 'kind': 'missing'})
                continue
            value = Ratio(0)
        if low == high:
            position = Ratio(1, 2)
        else:
            position = (value - low) / (high - low)
        if position < Ratio(0):
            position = Ratio(0)
        if Ratio(1) < position:
            position = Ratio(1)
        # Direct integer nearest-neighbor index, tie to the greater pitch.
        step_index = position * Ratio(spec.pitch_high_cents - spec.pitch_low_cents, spec.pitch_step_cents)
        nearest = (2 * step_index.n + step_index.d) // (2 * step_index.d)
        pitch = min(spec.pitch_high_cents, spec.pitch_low_cents + nearest * spec.pitch_step_cents)
        events.append({'onset_ms': onset, 'duration_ms': spec.note_ms, 'pitch_cents': pitch, 'kind': 'tone'})
    return {'events': events, 'duration_ms': slots * spec.slot_ms}


def reference_answers(values, threshold):
    values = [None if x is None else parse(x) for x in values]
    observed = [x for x in values if x is not None]
    total = Ratio(0)
    for value in observed:
        total += value
    trend = 'undefined'
    if len(observed) > 1:
        trend = 'rising' if observed[0] < observed[-1] else 'falling' if observed[-1] < observed[0] else 'flat'
    return {'threshold': any(not (x < parse(threshold)) for x in observed),
            'endpoint_trend': trend,
            'peak_indices': [i for i, x in enumerate(values) if x is not None and x == max(observed)] if observed else [],
            'missing_count': len(values) - len(observed),
            'total': str(total) if observed else 'undefined'}


def main():
    seed = 20261011
    rng = random.Random(seed)
    cases = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    if not 1 <= cases <= 100000:
        raise ValueError('Choose 1..100000 cases')
    started = time.perf_counter()
    digest = hashlib.sha256()
    counts = {'render_checks': 0, 'task_answer_checks': 0}
    for case in range(cases):
        low, high = rng.randint(-20, 0), rng.randint(1, 30)
        spec = Mapping(domain_low=str(low), domain_high=str(high),
                       normalization=rng.choice(('fixed', 'per_series')),
                       pitch_low_cents=rng.choice((0, 3600, 4800, 4850)),
                       pitch_high_cents=rng.choice((6400, 8400, 12700)),
                       pitch_step_cents=rng.choice((1, 7, 50, 100, 333, 1200, 10000)),
                       missing=rng.choice(('silence', 'zero', 'skip', 'marker')),
                       stride=rng.choice((1, 2, 3)))
        values = [None if rng.random() < 0.2 else '%d/%d' % (rng.randint(-60, 90), rng.choice((1, 2, 3, 7, 10))) for _ in range(rng.randint(1, 8))]
        if case % 17 == 0:
            values = [None] * len(values)
        elif case % 19 == 0:
            values = [str(rng.randint(-20, 50))] * len(values)
        threshold = '%d/%d' % (rng.randint(-20, 40), rng.choice((1, 2, 3, 7)))
        real = encode(values, spec).to_dict()
        expected = reference_render(values, spec)
        if real != expected:
            raise AssertionError({'case': case, 'spec': spec.to_dict(), 'values': values, 'real': real, 'reference': expected})
        counts['render_checks'] += 1
        reference = reference_answers(values, threshold)
        for task in TASKS:
            actual = json_answer(answer(values, task, threshold))
            if actual != reference[task]:
                raise AssertionError({'case': case, 'task': task, 'actual': actual, 'reference': reference[task]})
            counts['task_answer_checks'] += 1
        digest.update(json.dumps({'spec': spec.to_dict(), 'values': values, 'threshold': threshold}, sort_keys=True).encode())
    output = {'seed': seed, 'cases': cases, **counts, 'failures': 0,
              'campaign_input_sha256': digest.hexdigest(), 'elapsed_seconds': round(time.perf_counter() - started, 6),
              'oracle': 'independent normalized integer ratios; no Fraction, encode or answer calls inside reference functions',
              'scope': 'Finite differential falsification, not formal verification or a perceptual test.'}
    destination = Path(__file__).resolve().parents[1] / 'artifacts/reference-campaign.json'
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
