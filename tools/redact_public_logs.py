"""Redact machine paths in JSON logs without changing verification results."""
import argparse
import json
from pathlib import Path
import re


def redact(value, project_root):
    if isinstance(value, str):
        value = value.replace(str(project_root), '<PROJECT_ROOT>')
        value = re.sub(r'/private/tmp/echoproof-[A-Za-z0-9_-]+', '<ISOLATED_RUN>', value)
        value = re.sub(r'/private/var/folders/[^\s"\\]+', '<TEMP_OUTPUT>', value)
        return value.replace('/Library/Developer/CommandLineTools/usr/bin/python3', 'python3')
    if isinstance(value, list):
        return [redact(item, project_root) for item in value]
    if isinstance(value, dict):
        return {key: redact(item, project_root) for key, item in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    record = redact(json.loads(args.log.read_text(encoding='utf-8')), args.project_root.resolve())
    record['publication_redaction'] = {
        'applied': True,
        'scope': 'Machine-specific absolute paths only; commands/output are not verbatim raw logs. Status, counts and SHA-256 values retained.',
        'placeholders': ['<PROJECT_ROOT>', '<ISOLATED_RUN>', '<TEMP_OUTPUT>'],
    }
    args.log.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
