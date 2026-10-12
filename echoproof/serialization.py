"""Canonical JSON equality, preserving booleans versus numbers in evidence."""
import json


def canonical_json(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def same_json(left,right):
    try:
        return canonical_json(left)==canonical_json(right)
    except (TypeError,ValueError,RecursionError):
        return False
