"""Reproducible, bounded neighborhoods of a real CSV measurement series."""
import csv
import hashlib
from fractions import Fraction
from pathlib import Path
from .audit import audit_explicit, canonical
from .model import number, series
from .tasks import TASKS

MISSING_TOKENS = {"", "na", "n/a", "null", "none", "nan"}
MAX_CSV_ROWS = 64
MAX_CSV_BYTES = 1024 * 1024


def read_csv(path, column):
    path = Path(path)
    if path.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds 1 MiB; provide a focused slice")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames or column not in reader.fieldnames:
        raise ValueError("CSV column not found: " + column)
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Duplicate CSV headers are ambiguous")
    values = []
    for row_index, row in enumerate(reader, start=2):
        if len(values) >= MAX_CSV_ROWS:
            raise ValueError("CSV exceeds 64 data rows; provide a focused slice")
        token = row.get(column)
        if token is None:
            raise ValueError("Missing CSV field at row %d" % row_index)
        token = token.strip()
        try:
            values.append(None if token.lower() in MISSING_TOKENS else number(token))
        except ValueError as exc:
            raise ValueError("Invalid measurement at row %d: %s" % (row_index, exc)) from exc
    return series(values), {"kind": "csv", "filename": path.name, "column": column,
                            "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(values)}


def neighborhood(values, mapping, threshold):
    """Return input plus a declared deterministic mutation set; never estimate coverage."""
    values, threshold = series(values), number(threshold)
    low, high = number(mapping.domain_low), number(mapping.domain_high)
    delta = (high - low) / 1000
    candidates = [values]
    observed = [x for x in values if x is not None]
    for factor, offset in ((2, 0), (1, 1), (2, 1), (Fraction(1, 2), 0)):
        candidates.append(tuple(None if x is None else factor * x + offset for x in values))
    candidates.append(tuple(Fraction(0) if x is None else x for x in values))
    for index, value in enumerate(values):
        targets = [None, Fraction(0), threshold, threshold - delta, threshold + delta, low - delta, high + delta]
        if value is not None:
            targets += [value - delta, value + delta, value + high - low]
        for target in targets:
            candidate = list(values)
            candidate[index] = target
            candidates.append(tuple(candidate))
    return tuple(dict.fromkeys(candidates))


def probe_csv(path, column, mapping, threshold="5", tasks=TASKS):
    values, source = read_csv(path, column)
    candidates = neighborhood(values, mapping, threshold)
    provenance = {"source": source, "baseline": canonical(values),
                  "method": "deterministic single-position mutations plus four positive affine transforms",
                  "coverage": "Only the listed candidates; not exhaustive over all real values or edits.",
                  "delta": str((number(mapping.domain_high) - number(mapping.domain_low)) / 1000)}
    result = audit_explicit(mapping, candidates, tasks, threshold, provenance)
    return result
