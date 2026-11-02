"""Independent read-only SQL cross-check of the actual saved browser responses.

Uses no production calculator. Input responses must be captured from the real UI.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--responses', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checks = []
    def check(name, actual, expected):
        checks.append({'name': name, 'actual': actual, 'expected': expected, 'pass': actual == expected})
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as conn:
        check('source_rows', conn.execute('select count(*) from transaction_rows').fetchone()[0], 541909)
        check('one_dataset', conn.execute('select count(*) from dataset_snapshots').fetchone()[0], 1)
        for saved in json.loads(args.responses.read_text(encoding='utf-8')):
            result = saved['result']
            scope = (result['dataset_id'], result['period_start'], result['period_end_exclusive'])
            positive, negative, invoices = conn.execute('''select
                sum(case when primary_class='POSITIVE' then line_amount_milli_gbp else 0 end),
                -sum(case when primary_class='CANCELLATION' then line_amount_milli_gbp else 0 end),
                count(distinct case when primary_class='POSITIVE' then invoice_no end)
                from transaction_rows where dataset_id=? and invoice_date_source>=? and invoice_date_source<?''', scope).fetchone()
            for field, integer in [('positive_amount', positive), ('cancellation_amount', negative), ('net_amount', positive-negative)]:
                exact = Decimal(integer) / 1000
                check(result['month']+'_'+field+'_exact', result[field+'_exact'], f'{exact:.3f}')
                check(result['month']+'_'+field+'_display', result[field+'_display'], str(exact.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)))
            check(result['month']+'_invoices', result['positive_invoice_count'], invoices)
            stored = conn.execute('select result, result_sha256 from query_history where query_id=?', (saved['query_id'],)).fetchone()
            check(result['month']+'_saved_json', json.loads(stored[0]), result)
            check(result['month']+'_saved_hash', stored[1], saved['result_sha256'])
        check('saved_count', conn.execute('select count(*) from query_history').fetchone()[0], 2)
    report = {'status': 'PASS' if all(c['pass'] for c in checks) else 'FAIL', 'checks': checks,
              'responses_sha256': hashlib.sha256(args.responses.read_bytes()).hexdigest(), 'database': str(args.database),
              'source': 'real_browser_HTTP_responses_and_independent_SQL', 'model_calls': 0}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"UI_SQL={report['status']} CHECKS={len(checks)}")
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
