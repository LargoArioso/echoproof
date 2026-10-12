"""Small reproducible end-to-end core benchmark, with fresh-process peak RSS."""
import json
import hashlib
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from echoproof import Mapping, audit

CASES = [
    {'name': 'injective_small', 'levels': list(range(5)), 'length': 4, 'mapping': {}},
    {'name': 'injective_large', 'levels': list(range(5)), 'length': 7, 'mapping': {}},
    {'name': 'normalized_large', 'levels': list(range(5)), 'length': 7, 'mapping': {'normalization': 'per_series'}},
    {'name': 'sampled_large', 'levels': list(range(5)), 'length': 7, 'mapping': {'stride': 2}},
]


def worker(index):
    config = CASES[index]
    started = time.perf_counter()
    result = audit(Mapping(**config['mapping']), config['levels'], lengths=(config['length'],))
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if sys.platform == 'darwin' else peak * 1024
    return {'case': config, 'elapsed_seconds': round(elapsed, 6), 'peak_rss_bytes': peak_bytes,
            'series_per_second': round(result['search']['series_count'] / elapsed, 2),
            'search': result['search'],
            'task_disagreeing_pairs': {t: r['disagreeing_pairs'] for t, r in result['tasks'].items()}}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        print(json.dumps(worker(int(sys.argv[2]))))
        return
    results = []
    for index in range(len(CASES)):
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(index)],
                                 check=True, capture_output=True, text=True, timeout=60)
        result = json.loads(process.stdout)
        results.append(result)
        print('%s: %.3fs, %.1f MiB peak RSS' % (result['case']['name'], result['elapsed_seconds'], result['peak_rss_bytes'] / 1024 ** 2), flush=True)
    output = {'method': 'one cold Python process per case; enumeration plus semantic grouping, excluding report/WAV generation',
              'python_version': platform.python_version(), 'platform': platform.platform(),
              'machine': platform.machine(), 'results': results,
              'scope': 'Single-run local timings, not statistical performance guarantees or cross-machine comparisons.'}
    project = Path(__file__).resolve().parents[1]
    output['source_sha256'] = {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in sorted((project / 'echoproof').glob('*.py'))}
    destination = Path(__file__).resolve().parents[1] / 'artifacts/benchmark.json'
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print(destination)


if __name__ == '__main__':
    main()
