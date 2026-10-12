"""Create a reviewable local snapshot without caches or downloaded dependencies."""
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / 'artifacts/echoproof-snapshot.zip'
    manifest_path = root / 'artifacts/snapshot-manifest.json'
    excluded_parts = {'node_modules', '__pycache__', '.git', '.cache', '.venv', 'vendor', 'dist', 'build'}
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path in (destination, manifest_path, root / 'artifacts/package-smoke.json') or path.suffix in ('.zip', '.pyc', '.pyo'):
            continue
        files.append((relative, path.read_bytes()))
    manifest = {'files': [{'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for path, data in files],
                'exclusions': sorted(excluded_parts),
                'scope': 'Local source and artifact snapshot. Optional external compiler sources/dependencies must be fetched separately using the documented pinned workflow.'}
    manifest_raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in files + [(Path('MANIFEST.json'), manifest_raw)]:
            entry = zipfile.ZipInfo('echoproof/' + relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    manifest['archive_sha256'] = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest['archive_bytes'] = destination.stat().st_size
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Inspect every archived file against the manifest, rather than assuming writes succeeded.
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for entry in manifest['files']:
            content = archive.read('echoproof/' + entry['path'])
            assert hashlib.sha256(content).hexdigest() == entry['sha256']
    print(json.dumps({'archive': str(destination), 'files': len(files), 'bytes': manifest['archive_bytes'], 'sha256': manifest['archive_sha256']}, indent=2))


if __name__ == '__main__':
    main()
