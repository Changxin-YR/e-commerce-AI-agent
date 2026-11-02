"""Rerun the two immutable package audits against a local raw workbook.

Only the source-path assignment is adapted in a cached script copy. The raw
workbook is not copied out of data/raw and all calculation logic is unchanged.
Outputs are compared recursively, ignoring only the actual execution timestamp.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from importlib import metadata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_source_data import check_xlsx, file_hash


def compare_values(old, new, path='$') -> list[dict]:
    if isinstance(old, dict) and isinstance(new, dict):
        differences = []
        for key in sorted(old.keys() | new.keys()):
            if path == '$' and key == 'audited_at_utc':
                continue
            if key not in old or key not in new:
                differences.append({'path': path + '.' + key, 'old': old.get(key), 'new': new.get(key)})
            else:
                differences.extend(compare_values(old[key], new[key], path + '.' + key))
        return differences
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return [{'path': path + '.length', 'old': len(old), 'new': len(new)}]
        return [d for i, (a, b) in enumerate(zip(old, new)) for d in compare_values(a, b, f'{path}[{i}]')]
    return [] if old == new else [{'path': path, 'old': old, 'new': new}]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        check_xlsx(args.source)
    except (OSError, ValueError) as exc:
        print(f'INDEPENDENT_AUDIT=FAIL: {exc}', file=sys.stderr)
        return 2
    results = []
    for name, assignment in [('audit_retail', "source = BASE / 'Online_Retail.xlsx'"),
                             ('audit_normalization_and_reference', "SOURCE = BASE / 'Online_Retail.xlsx'")]:
        source_script = ROOT / 'docs/plan/evidence' / (name + '.py')
        content = source_script.read_text('utf-8')
        if content.count(assignment) != 1:
            raise ValueError('Unexpected immutable script source assignment')
        replacement = assignment.split(' = ')[0] + ' = Path(' + repr(str(args.source.resolve())) + ')'
        adapted = args.output / (name + '.py')
        adapted.write_text(content.replace(assignment, replacement), encoding='utf-8')
        command = [sys.executable, str(ROOT / 'scripts/record_command.py'), '--output', str(args.output / 'commands'),
                   '--label', name, '--', sys.executable, str(adapted)]
        code = subprocess.run(command, cwd=ROOT).returncode
        result = {'name': name, 'exit_code': code, 'original_script_sha256': file_hash(source_script),
                  'adapted_script_sha256': file_hash(adapted),
                  'only_adaptation': {'old': assignment, 'new': replacement}}
        if code == 0:
            reference = ROOT / 'docs/plan/evidence' / (name + '.json')
            actual = args.output / (name + '.json')
            result.update({'reference_sha256': file_hash(reference), 'result_sha256': file_hash(actual),
                           'differences': compare_values(json.loads(reference.read_text('utf-8')),
                                                         json.loads(actual.read_text('utf-8')))})
        results.append(result)
    passed = all(x['exit_code'] == 0 and not x.get('differences') for x in results)
    summary = {'status': 'PASS' if passed else 'FAIL_OR_REVIEW_REQUIRED',
               'audited_at_utc': datetime.now(timezone.utc).isoformat(),
               'source_xlsx_sha256': file_hash(args.source), 'excluded_comparison_fields': ['audited_at_utc'],
               'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                               **{p: metadata.version(p) for p in ['pandas', 'numpy', 'openpyxl', 'python-dateutil']}},
               'results': results}
    (args.output / 'comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == '__main__':
    raise SystemExit(main())
