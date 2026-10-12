"""Fetch a pinned official npm archive; verify integrity and reject unsafe entries.

This does not execute package scripts. Optional, separate from the core package.
"""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = "https://registry.npmjs.org/erie-web/-/erie-web-1.0.1.tgz"
INTEGRITY = "hsAefPEp85yULPbS0Eog9wsVBPXuvNMIAqs1zdYTGm+jUBqtvliLRwnedkJ4q+sGc2hQdxU/zGxOglLS0+X9UQ=="
MAX_BYTES = 25 * 1024 * 1024


def main():
    root = Path(__file__).resolve().parents[2] / "research/vendor/erie-web-1.0.1"
    with urllib.request.urlopen(URL, timeout=30) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Archive exceeds size limit")
    if base64.b64encode(hashlib.sha512(raw).digest()).decode() != INTEGRITY:
        raise ValueError("Archive integrity mismatch")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        total = sum(m.size for m in members if m.isfile())
        if total > MAX_BYTES or len(members) > 2000:
            raise ValueError("Extracted archive exceeds resource limits")
        # Validate all paths before writing. Symlinks and other special entries are rejected.
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != "package" or ".." in parts or Path(member.name).is_absolute():
                raise ValueError("Unsafe archive path")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Unsupported archive entry type")
            target = root.joinpath(*parts[1:])
            if root.resolve() not in target.resolve().parents and target.resolve() != root.resolve():
                raise ValueError("Extraction would leave destination directory")
        for member in members:
            if member.isfile():
                target = root.joinpath(*Path(member.name).parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    print(root)


if __name__ == "__main__":
    main()
