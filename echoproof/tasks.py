"""Questions a listener may need to answer about the original samples."""
from .model import number, series

TASKS = ("threshold", "endpoint_trend", "peak_indices", "missing_count", "total")


def answer(values, task, threshold="5"):
    values = series(values)
    observed = [x for x in values if x is not None]
    if task == "threshold":
        return any(x >= number(threshold) for x in observed)
    if task == "missing_count":
        return sum(x is None for x in values)
    if task == "endpoint_trend":
        if len(observed) < 2:
            return "undefined"
        delta = observed[-1] - observed[0]
        return "rising" if delta > 0 else "falling" if delta < 0 else "flat"
    if task == "peak_indices":
        if not observed:
            return ()
        maximum = max(observed)
        return tuple(i for i, x in enumerate(values) if x is not None and x == maximum)
    if task == "total":
        # Missing values are absent, not estimated. Empty observed sum is undefined.
        return str(sum(observed)) if observed else "undefined"
    raise ValueError("Unknown task: " + str(task))


def json_answer(value):
    return list(value) if isinstance(value, tuple) else value
