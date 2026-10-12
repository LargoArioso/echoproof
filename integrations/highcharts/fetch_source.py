"""Fetch pinned official source, extracting sonification and core dependencies only.

No installation, package scripts, browser, or player is executed. Downloaded
commercially licensed third-party code is excluded from the MIT snapshot.
"""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = 'https://registry.npmjs.org/highcharts/-/highcharts-13.1.1.tgz'
INTEGRITY = 'k/smhxCgaqHDsuy9ZCWs8FJNTPrbzc8BmMA4M/8f9JMwv9HgmNZjulyWwZ9q9ly6AzHpskL9mhlW8vgsSqnstg=='
MAX_COMPRESSED = 30*1024*1024
MAX_EXTRACTED = 100*1024*1024


def main():
    root = Path(__file__).resolve().parents[2]/'research/vendor/highcharts-13.1.1'
    with urllib.request.urlopen(URL, timeout=30) as response:
        raw = response.read(MAX_COMPRESSED+1)
    if len(raw)>MAX_COMPRESSED or base64.b64encode(hashlib.sha512(raw).digest()).decode()!=INTEGRITY:
        raise ValueError('Archive limit or integrity check failed')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members)>5000 or sum(m.size for m in members if m.isfile())>MAX_EXTRACTED:
            raise ValueError('Archive exceeds extraction bounds')
        selected=[]
        for member in members:
            parts=Path(member.name).parts
            if not parts or parts[0]!='package' or '..' in parts or Path(member.name).is_absolute() or not(member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            relative=Path(*parts[1:])
            if (str(relative).startswith('es-modules/Extensions/Sonification/') or
                str(relative).startswith('es-modules/Core/') or
                str(relative).startswith('es-modules/Shared/') or
                str(relative) in ('package.json', 'license.txt', 'LICENSE', 'README.md')) and member.isfile():
                selected.append((relative, member))
        for relative, member in selected:
            target=root/relative
            if root.resolve() not in target.resolve().parents:
                raise ValueError('Destination escapes source directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    print(root)
    print('Selected %d original source/license files; package not installed' % len(selected))


if __name__=='__main__':
    main()
