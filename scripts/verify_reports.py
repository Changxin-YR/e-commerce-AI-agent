"""Verify captured browser reports using independent SQL/Decimal and persisted refs.

No production metric/report calculators are imported. Real UCI is required.
"""
import argparse
import json
from pathlib import Path
import sqlite3
from verify_tools import reference, number, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); checks = []
    def check(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected, passed=actual == expected))
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        check('real_source_rows', db.execute('select count(*) from transaction_rows').fetchone()[0], 541909)
        snapshot_hash = db.execute('select workbook_sha256 from dataset_snapshots').fetchone()[0]
        check('official_snapshot', snapshot_hash, '43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d')
        for report in json.loads(args.reports.read_text('utf-8')):
            saved = db.execute('select content from reports where report_id=?', (report['report_id'],)).fetchone()
            check('persisted_report', json.loads(saved[0]), report['content'])
            results = report['evidence']; dataset = report['dataset_id']
            for claim in report['content']['claims']:
                result = next(x for x in results if x['tool_call_id'] == claim['tool_call_id'])
                value = result['data']
                for part in claim['field_path'].split('.'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                check('claim:' + claim['label'], claim['value'], value)
                check('claim_source', claim['snapshot_hash'], snapshot_hash)
            for envelope in results:
                data, query, metric = envelope['data'], envelope['arguments'], envelope['data']['metric']
                # The browser acceptance uses unrestricted countries/products; never silently ignore a filter.
                assert not query.get('stock_code')
                country = query.get('country')
                if envelope['tool'] == 'query_metric_series':
                    for point in data['points']:
                        period = dict(date_from=point['period_start'][:10], date_to=point['period_end_exclusive'][:10])
                        actual = reference(db, dataset, period, metric, country=country)
                        check(metric + ':' + point['month'], point['value_exact'], None if point['status'] == 'NO_DATA' else number(actual, metric))
                elif envelope['tool'] == 'rank_entities':
                    groups = reference(db, dataset, query, metric, query['dimension'], country)
                    ordered = sorted(groups, key=lambda k: (-groups[k], k is None, k or ''))
                    check('rank_entities', [x['entity'] for x in data['items']], ordered[:10])
                    check('rank_values', [x['value_exact'] for x in data['items']], [number(groups[k], metric) for k in ordered[:10]])
                elif envelope['tool'] in ('compare_periods', 'decompose_change'):
                    before = reference(db, dataset, query['baseline'], metric, country=country)
                    after = reference(db, dataset, query['current'], metric, country=country)
                    check('period_delta', data['delta_exact'], number(after-before, metric))
                    if envelope['tool'] == 'decompose_change':
                        b = reference(db, dataset, query['baseline'], metric, query['dimension'], country)
                        c = reference(db, dataset, query['current'], metric, query['dimension'], country)
                        changes = {k: c.get(k, 0)-b.get(k, 0) for k in b.keys() | c.keys()}
                        order = sorted(changes, key=lambda k: (-abs(changes[k]), k is None, k or ''))
                        check('decomposition_keys', [x['entity'] for x in data['items']], order[:10])
                        check('decomposition_values', [x['delta_exact'] for x in data['items']], [number(changes[k], metric) for k in order[:10]])
                        check('other_changes', data['other_delta_exact'], number(sum(changes[k] for k in order[10:]), metric))
    result = dict(status='PASS' if all(x['passed'] for x in checks) else 'FAIL', checks=checks,
                  source='real_browser_reports_independent_SQL', reports_sha256=sha(args.reports), external_model_calls=0)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"REPORT_SQL={result['status']} CHECKS={len(checks)}")
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
