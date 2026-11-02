"""Verify current raw bytes against three actual audit outputs; no database use."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_source_data import file_hash, check_zip, check_xlsx
from scripts.run_independent_audits import compare_values


def verify(zip_path: Path, xlsx_path: Path, evidence: Path) -> dict:
    check_zip(zip_path)
    check_xlsx(xlsx_path)
    load = lambda p: json.loads(p.read_text(encoding='utf-8'))
    audit = load(evidence / 'audit.json')
    retail = load(evidence / 'audit_retail.json')
    precision = load(evidence / 'audit_normalization_and_reference.json')
    comparison = load(evidence / 'comparison.json')
    checks = {}
    checks['audit_status'] = audit['status'] == comparison['status'] == 'PASS'
    checks['same_real_workbook'] = (audit['files']['xlsx']['sha256'] == retail['file_sha256'] ==
                                    precision['source_xlsx_sha256'] == comparison['source_xlsx_sha256'] == file_hash(xlsx_path))
    checks['same_real_container'] = audit['files']['zip']['sha256'] == file_hash(zip_path)
    checks['audit_script_identity'] = audit['script_sha256'] == file_hash(ROOT / 'scripts/audit_source_data.py')
    for result in comparison['results']:
        name = result['name']
        checks[name + '_script_identity'] = result['original_script_sha256'] == file_hash(ROOT / 'docs/plan/evidence' / (name + '.py'))
        checks[name + '_result_identity'] = result['result_sha256'] == file_hash(evidence / (name + '.json'))
        checks[name + '_comparison'] = (result['exit_code'] == 0 and result['differences'] == [] and
                                        not compare_values(load(ROOT / 'docs/plan/evidence' / (name + '.json')), load(evidence / (name + '.json'))))
    for field in ['rows', 'columns', 'sheet_names', 'date_min', 'date_max', 'null_counts',
                  'invoice_unique_count', 'stock_code_unique_count', 'per_month_rows', 'quantity_min', 'quantity_max']:
        checks[field] = audit[field] == retail[field]
    classes = audit['primary_class_counts']
    cross = retail['cancel_price_cross']
    checks['mutually_exclusive_classes'] = (classes['POSITIVE'] == cross['positive']['non_C'] and
                                           classes['CANCELLATION'] == cross['positive']['C_prefix'] and
                                           classes['EXCLUDED_OTHER'] == sum(cross['zero'].values()) + sum(cross['negative'].values()) and
                                           classes['INVALID'] == 0)
    checks['row_reconciliation'] = audit['row_reconciliation'] and sum(classes.values()) == retail['rows'] == precision['rows']
    checks['duplicates_retained'] = audit['duplicate_candidate_rows_after_first'] == retail['exact_duplicates_after_first_all_columns']
    checks['duplicate_groups'] = audit['rows_in_duplicate_groups'] == retail['rows_in_duplicate_groups_all_columns']
    norm = audit['normalization']
    reference_norm = precision['normalization']
    for field in ['rows_with_any_difference', 'max_absolute_difference_gbp', 'rounding']:
        checks['precision_' + field] = norm[field] == reference_norm[field]
    checks['precision_tolerance'] = Decimal(norm['allowed_representation_difference_gbp']) == Decimal(reference_norm['allowed_representation_difference_gbp'])
    checks['precision_no_silent_loss'] = reference_norm['rows_exceeding_allowed_difference'] == 0
    checks['true_milli_prices_preserved'] = norm['price_0_001_rows'] == len(reference_norm['normalized_prices_requiring_more_than_2_decimal_places'])
    checks['int64_amounts'] = audit['int64_check']['safe'] and audit['int64_check']['sum_absolute_line_amount_milli_gbp'] <= 2**63 - 1
    checks['invoice_timestamps'] = all(v == precision['invoice_time_consistency'][k] for k, v in audit['invoice_time_consistency'].items())
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'checks': checks, 'check_count': len(checks), 'failed_checks': [k for k, v in checks.items() if not v],
            'zip_sha256': file_hash(zip_path), 'xlsx_sha256': file_hash(xlsx_path),
            'rows': audit['rows'], 'primary_class_counts': classes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, default=ROOT / 'data/raw/online_retail_uci352.zip')
    parser.add_argument('--xlsx', type=Path, default=ROOT / 'data/raw/Online_Retail.xlsx')
    parser.add_argument('--evidence', type=Path, default=ROOT / 'docs/evidence/d1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print('D1_VERIFY=FAIL: choose a new output file', file=sys.stderr)
        return 2
    try:
        result = verify(args.zip, args.xlsx, args.evidence)
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'FAIL', 'error': str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
