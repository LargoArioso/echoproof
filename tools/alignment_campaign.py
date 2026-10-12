"""Fixed-seed independent boundary-pair oracle for simultaneous repair."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from echoproof import Mapping
from echoproof.multi_alignment import align_thresholds


def oracle(mapping, thresholds, input_low, input_high):
    # Solve two affine equations directly; do not call the repair, boundary,
    # interval-certificate, or sound-encoding functions from inside this oracle.
    span = mapping.pitch_high_cents-mapping.pitch_low_cents
    step = mapping.pitch_step_cents
    count = (2*span+step)//(2*step)
    covered_low = min(Fraction(mapping.domain_low), input_low)
    covered_high = max(Fraction(mapping.domain_high), input_high)
    out = set()
    for left_index in range(count):
        first_coefficient = Fraction((2*left_index+1)*step, 2*span)
        for right_index in range(left_index+1, count):
            second_coefficient = Fraction((2*right_index+1)*step, 2*span)
            width = (thresholds[1]-thresholds[0])/(second_coefficient-first_coefficient)
            low = thresholds[0]-first_coefficient*width
            high = low+width
            boundaries = {low+Fraction((2*k+1)*step, 2*span)*width for k in range(count)}
            if low <= covered_low and high >= covered_high and set(thresholds) <= boundaries:
                out.add((low, high))
    return out


def main():
    cases = int(sys.argv[1]) if len(sys.argv)>1 else 3000
    if not 1 <= cases <= 10000:
        raise ValueError("Choose 1..10000 cases")
    rng = random.Random(20261012)
    counts, fingerprint = Counter(), hashlib.sha256()
    started = time.perf_counter()
    for index in range(cases):
        step = rng.choice((100, 200, 300, 400))
        span = rng.randint(1, 7)*step + rng.choice((-step//2, 0, step//2-1))
        pitch_low = rng.randint(0, 20)*100
        original_low, original_high = rng.randint(-4, 0), rng.randint(10, 16)
        mapping = Mapping(domain_low=str(original_low), domain_high=str(original_high),
                          pitch_low_cents=pitch_low, pitch_high_cents=pitch_low+span,
                          pitch_step_cents=step, normalization=rng.choice(("fixed", "per_series")))
        input_low, input_high = Fraction(-6), Fraction(18)
        count = (2*span+step)//(2*step)
        if index % 2 == 0 and count >= 2:
            # Deliberately generate positive controls from an expanded range;
            # select only transitions lying in the declared input interval.
            lo, hi = Fraction(rng.randint(-12, -6)), Fraction(rng.randint(18, 24))
            inside = sorted({lo+Fraction((2*k+1)*step, 2*span)*(hi-lo) for k in range(count)
                             if input_low < lo+Fraction((2*k+1)*step, 2*span)*(hi-lo) <= input_high})
            thresholds = sorted(rng.sample(inside, min(len(inside), rng.randint(2, 4)))) if len(inside)>=2 else [Fraction(4), Fraction(5)]
        else:
            thresholds = sorted(set(Fraction(rng.randint(-11, 36), 2) for _ in range(4)))
            if len(thresholds) < 2:
                thresholds = [Fraction(4), Fraction(5)]
        payload = {"mapping": mapping.to_dict(), "thresholds": list(map(str, thresholds))}
        fingerprint.update((json.dumps(payload, sort_keys=True)+"\n").encode())
        expected = oracle(mapping, thresholds, input_low, input_high)
        # Up to 8 transitions => at most 28 pair candidates. Compare all feasible
        # ranges via feasible count plus the first 16 ranked ranges.
        result = align_thresholds(mapping, thresholds, input_low, input_high, limit=16)
        ranked = sorted(expected, key=lambda pair: ((abs(pair[0]-original_low)+abs(pair[1]-original_high))/(original_high-original_low), pair[0], pair[1]))
        actual = [(Fraction(c["mapping"]["domain_low"]), Fraction(c["mapping"]["domain_high"])) for c in result["candidates"]]
        if actual != ranked[:16] or result["search"]["feasible_ranges"] != len(expected):
            raise AssertionError({"case": index, "input": payload, "expected": list(map(str, ranked)), "actual": list(map(str, actual))})
        counts[result["status"]] += 1
    record = {"seed": 20261012, "cases": cases, "outcomes": dict(counts), "differences": 0,
              "input_sha256": fingerprint.hexdigest(), "elapsed_seconds": round(time.perf_counter()-started, 4),
              "python": platform.python_version(), "platform": platform.platform(),
              "source_sha256": {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'echoproof/multi_alignment.py', Path(__file__).resolve()]},
              "scope": "Finite fixed-seed counterchecks, maximum eight pitch transitions. Independent direct solution of affine boundary-pair equations; no human experiment or proof of program correctness."}
    path = ROOT/'artifacts/alignment-campaign.json'
    path.write_text(json.dumps(record, indent=2)+"\n", encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
