"""Extract one local EchoProof snapshot and test that exact source copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def check_entries(archive):
    entries=archive.infolist()
    if len(entries)>5000 or sum(e.file_size for e in entries)>200*1024*1024:
        raise ValueError('Snapshot exceeds the local extraction bounds')
    names=set()
    for entry in entries:
        path=PurePosixPath(entry.filename)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='echoproof' or '\\' in entry.filename:
            raise ValueError('Unexpected archive path')
        if entry.filename in names: raise ValueError('Duplicate archive path')
        names.add(entry.filename)
        if (entry.external_attr>>16)&0o170000==0o120000:
            raise ValueError('Snapshot symlinks are unsupported')
    if archive.testzip() is not None: raise ValueError('Archive CRC check failed')


def smoke(archive_path,output,recordings=False):
    archive_path=Path(archive_path).resolve();output=Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Destination must be new or empty')
    archive_sha=hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive_path) as archive:
        check_entries(archive)
        output.mkdir(parents=True,exist_ok=True)
        archive.extractall(output)
    copy=output/'echoproof'
    manifest=json.loads((copy/'MANIFEST.json').read_text())
    for entry in manifest['files']:
        path=PurePosixPath(entry['path'])
        if path.is_absolute() or '..' in path.parts or '\\' in entry['path']:
            raise ValueError('Unexpected manifest path')
        raw=(copy/Path(*path.parts)).read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Manifest content mismatch: '+entry['path'])
    environment=dict(os.environ,PYTHONPATH=str(copy))
    imported=subprocess.run([sys.executable,'-c','import echoproof; print(echoproof.__file__)'],cwd=copy,env=environment,capture_output=True,text=True,check=True).stdout.strip()
    if imported!=str(copy/'echoproof/__init__.py'):
        raise ValueError('Python did not import the extracted source')
    command=[sys.executable,'tools/reproduce.py','--out',str(output/'reproduced'),'--tests']
    if recordings: command.append('--recordings')
    artifact_validation=subprocess.run([sys.executable,'tools/validate_artifacts.py'],cwd=copy,env=environment,capture_output=True,text=True)
    result=artifact_validation if artifact_validation.returncode else subprocess.run(command,cwd=copy,env=environment,capture_output=True,text=True)
    report_path=output/'reproduced/reproduction.json'
    report=json.loads(report_path.read_text()) if result.returncode==0 else {}
    record={'schema_version':1,'archive_sha256':archive_sha,'manifest_files_verified':len(manifest['files']),
            'imported_module_path':imported,'command':command,'reproduction_started':artifact_validation.returncode==0,'artifact_validation':{'exit_code':artifact_validation.returncode,'stdout':artifact_validation.stdout,'stderr':artifact_validation.stderr},'exit_code':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'stages_passed':report.get('stage_count'),
            'source_sha256':report.get('source_sha256'),'automated_test_output':report.get('stages',[{}])[-1].get('stderr'),
            'scope':'This exact local archive was extracted, checked against its included manifest, its packaged artifact certificates replayed, and its source tested independently of the original source path. The manifest checks consistency, not author authenticity. Saved recordings are rechecked only when requested; no external backend, network, browser visual or human hearing validation. This log is outside the tested archive.'}
    (output/'smoke.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'archive_sha256':archive_sha,'exit_code':result.returncode,'stages_passed':record['stages_passed'],'manifest_files_verified':len(manifest['files']),'log':str(output/'smoke.json')},indent=2))
    if result.returncode: raise RuntimeError('Snapshot reproduction failed; inspect the saved log')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',default=str(ROOT/'artifacts/echoproof-snapshot.zip'))
    parser.add_argument('--out',required=True)
    parser.add_argument('--recordings',action='store_true')
    args=parser.parse_args()
    try: smoke(args.archive,args.out,args.recordings)
    except (ValueError,OSError,zipfile.BadZipFile) as exc: parser.exit(2,'error: '+str(exc)+'\n')


if __name__=='__main__': main()
