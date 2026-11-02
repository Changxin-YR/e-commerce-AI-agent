"""Read-only release checks. Report only file names and booleans, never secret contents."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    from backend.app.config import Settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dist', type=Path)
    args = parser.parse_args()
    settings = Settings()
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').rstrip('\0').split('\0')
    files = [ROOT/name for name in names]
    blocked = []
    for name, path in zip(names, files):
        if (path.stat().st_size > 5 * 1024**2 or path.suffix.lower() in
            {'.zip', '.xlsx', '.xls', '.sqlite', '.sqlite3', '.db', '.pem', '.key', '.p12', '.pfx'} or
            (path.name.startswith('.env') and path.name != '.env.example') or
            any(part in {'.venv', 'node_modules', '__pycache__'} for part in path.relative_to(ROOT).parts)):
            blocked.append(name)
    immutable = json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))['immutable_files']
    changed_contracts = [item['path'] for item in immutable if sha(ROOT/item['path']) != item['sha256']]
    if args.dist:
        files += [p for p in args.dist.rglob('*') if p.is_file()]
    secret = settings.model_api_key.get_secret_value()
    leaks = [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name
             for p in files if secret and secret.encode('utf-8') in p.read_bytes()]
    disabled = (not settings.allow_paid_model_calls and settings.model_max_total_requests == 0
                and settings.model_max_total_tokens == 0 and settings.model_max_tokens_per_run == 0)
    manifest = json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
    source_checks = [dict(path=item['path'], actual=sha(ROOT/item['path']), expected=item['sha256'])
                     for item in manifest['files'].values()]
    result = dict(scope='tracked_files_contract_integrity_configured_key_and_paid_gate',
        status='PASS' if not (blocked or changed_contracts or leaks) and disabled
                         and all(x['actual'] == x['expected'] for x in source_checks) else 'FAIL',
        tracked_files=len(names), immutable_files=len(immutable), excluded_file_violations=blocked,
        changed_contracts=changed_contracts, configured_key_present=bool(secret), configured_key_leak_files=leaks,
        configured_key_scan='EXECUTED' if secret else 'NOT_APPLICABLE_NO_CONFIGURED_KEY',
        paid_gate_disabled_and_zero_budgets=disabled,
        official_source_checks=source_checks,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'data/raw').glob('*')
                       if p.suffix.lower() in ('.zip', '.xlsx')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
