"""D1 read-only OOXML audit. No database import or application metrics.

Raw numeric text is read from OOXML, never reconstructed from float.
Every invocation writes into a new output directory; errors cannot leave a
previous successful report looking like the result of the failed invocation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from openpyxl.utils.datetime import from_excel, CALENDAR_WINDOWS_1900

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_source_data import EXPECTED_XLSX, EXPECTED_ZIP, OFFICIAL_URL, check_zip, check_xlsx, file_hash

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
FIELDS = ['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country']
CLASSES = ('INVALID', 'POSITIVE', 'CANCELLATION', 'EXCLUDED_OTHER')
QUANTUM = Decimal('0.001')
TOLERANCE = Decimal('1E-9')
INT64_MAX = 2**63 - 1
TRANSFORM_VERSION = 'uci352-ooxml-milligbp-v1'


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize_price(raw: str) -> tuple[Decimal, int, Decimal]:
    """Accept representation tails only; reject true sub-milli precision."""
    try:
        price = Decimal(raw)
        if not price.is_finite() or abs(price) > Decimal(INT64_MAX) / 1000:
            raise ValueError('PRICE_NONFINITE_OR_INT64_OVERFLOW')
        with localcontext() as ctx:
            ctx.prec = max(50, len(price.as_tuple().digits) + 10)
            normalized = price.quantize(QUANTUM, rounding=ROUND_HALF_UP)
            difference = abs(price - normalized)
            if difference > TOLERANCE:
                raise ValueError('PRICE_PRECISION_EXCEEDS_1E-9')
            milli = normalized * 1000
            if milli != milli.to_integral_value() or abs(milli) > INT64_MAX:
                raise ValueError('PRICE_INT64_OVERFLOW')
            return normalized, int(milli), difference
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('PRICE_NOT_DECIMAL') from exc


def classify(invoice: str | None, stock: str | None, raw_quantity: str | None,
             date: datetime | None, raw_price: str | None) -> dict:
    """Audit-only classifier; independent of any future D2 importer."""
    try:
        if not invoice or not stock or not isinstance(date, datetime):
            raise ValueError('MISSING_OR_INVALID_REQUIRED_FIELD')
        quantity = Decimal(raw_quantity)
        if not quantity.is_finite() or quantity != quantity.to_integral_value():
            raise ValueError('QUANTITY_NOT_INTEGER')
        if abs(quantity) > INT64_MAX:
            raise ValueError('QUANTITY_INT64_OVERFLOW')
        quantity = int(quantity)
        normalized, milli, difference = normalize_price(raw_price)
        amount = quantity * milli
        if abs(amount) > INT64_MAX:
            raise ValueError('LINE_AMOUNT_INT64_OVERFLOW')
    except (ValueError, InvalidOperation, TypeError) as exc:
        return {'primary_class': 'INVALID', 'reasons': [str(exc)]}
    cancel = invoice.upper().startswith('C')
    reasons = []
    if milli == 0:
        reasons.append('ZERO_PRICE')
    if milli < 0:
        reasons.append('NEGATIVE_PRICE')
    if not cancel and quantity < 0:
        reasons.append('NON_C_NEGATIVE_QUANTITY')
    if cancel and quantity >= 0:
        reasons.append('C_NONNEGATIVE_QUANTITY')
    if quantity == 0:
        reasons.append('ZERO_QUANTITY')
    primary = ('POSITIVE' if not cancel and quantity > 0 and milli > 0 else
               'CANCELLATION' if cancel and quantity < 0 and milli > 0 else 'EXCLUDED_OTHER')
    return {'primary_class': primary, 'reasons': reasons, 'quantity': quantity,
            'unit_price_milli_gbp': milli, 'normalized_price': str(normalized),
            'representation_difference_gbp': str(difference), 'line_amount_milli_gbp': amount}


def extract_verified(zip_path: Path, xlsx_path: Path) -> list[dict]:
    """Only extract the hash-verified official single member, without overwrite."""
    check_zip(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        info = archive.infolist()[0]
        layout = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                   'crc32': f'{i.CRC:08x}'} for i in archive.infolist()]
        if xlsx_path.exists():
            check_xlsx(xlsx_path)
        else:
            xlsx_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, xlsx_path.open('xb') as target:
                shutil.copyfileobj(source, target)
            check_xlsx(xlsx_path)
        return layout


def audit_workbook(path: Path) -> dict:
    classes = Counter({key: 0 for key in CLASSES})
    flags = Counter()
    reasons = Counter()
    nulls = Counter({key: 0 for key in FIELDS})
    examples = defaultdict(list)
    seen = Counter()
    invoices, stocks, countries = set(), set(), set()
    invoice_times = defaultdict(set)
    per_month = Counter()
    price_repr_scales = Counter()
    changed = 0
    max_difference = Decimal(0)
    date_min = date_max = None
    quantity_min = quantity_max = price_min = price_max = None
    max_abs_milli = max_abs_amount = absolute_amount_sum = 0
    count = 0
    formula_cells = 0
    with zipfile.ZipFile(path) as book:
        if book.testzip() is not None:
            raise ValueError('WORKBOOK_CRC_ERROR')
        workbook = ET.fromstring(book.read('xl/workbook.xml'))
        sheets = workbook.find(NS + 'sheets')
        names = [sheet.attrib['name'] for sheet in sheets]
        if names != ['Online Retail']:
            raise ValueError(f'UNEXPECTED_WORKSHEETS: {names}')
        properties = workbook.find(NS + 'workbookPr')
        if properties is not None and properties.get('date1904') in ('1', 'true'):
            raise ValueError('UNEXPECTED_DATE_EPOCH_1904')
        relationships = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in relationships}
        target = targets[sheets[0].attrib[REL + 'id']]
        sheet_path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
        strings_xml = ET.fromstring(book.read('xl/sharedStrings.xml'))
        strings = [''.join(t.text or '' for t in si.iter(NS + 't')) for si in strings_xml]
        members = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size} for i in book.infolist()]
        with book.open(sheet_path) as stream:
            events = ET.iterparse(stream, events=('start', 'end'))
            _, xml_root = next(events)
            sheet_data = None
            for event, node in events:
                if event == 'start' and node.tag == NS + 'sheetData':
                    sheet_data = node
                if event != 'end' or node.tag != NS + 'row':
                    continue
                row_number = int(node.attrib['r'])
                values, formulas = {}, []
                for cell in node.findall(NS + 'c'):
                    column = re.sub(r'\d', '', cell.attrib['r'])
                    value = cell.find(NS + 'v')
                    raw = value.text if value is not None else None
                    if cell.find(NS + 'f') is not None:
                        formulas.append(cell.attrib['r'])
                    if cell.get('t') == 's' and raw is not None:
                        raw = strings[int(raw)]
                    elif cell.get('t') == 'inlineStr':
                        raw = ''.join(t.text or '' for t in cell.iter(NS + 't'))
                    elif cell.get('t') in ('e', 'b'):
                        raise ValueError(f'UNEXPECTED_CELL_TYPE: {cell.attrib["r"]}')
                    values[column] = raw
                if row_number == 1:
                    headers = [values.get(chr(65 + i)) for i in range(8)]
                    if headers != FIELDS or len(values) != 8:
                        raise ValueError(f'UNEXPECTED_COLUMNS: {headers}')
                else:
                    if row_number != count + 2:
                        raise ValueError('NONCONTIGUOUS_SOURCE_ROW_NUMBERS')
                    count += 1
                    row = {field: values.get(chr(65 + i)) for i, field in enumerate(FIELDS)}
                    for field, value in row.items():
                        if value is None or value == '':
                            nulls[field] += 1
                    formula_cells += len(formulas)
                    try:
                        date = from_excel(float(row['InvoiceDate']), epoch=CALENDAR_WINDOWS_1900)
                    except (ValueError, TypeError, OverflowError):
                        date = None
                    item = classify(row['InvoiceNo'], row['StockCode'], row['Quantity'], date, row['UnitPrice'])
                    if formulas:
                        item = {'primary_class': 'INVALID', 'reasons': ['FORMULA_CELL']}
                    classes[item['primary_class']] += 1
                    reasons.update(item['reasons'])
                    tags = list(item['reasons'])
                    if row['CustomerID'] is None:
                        tags.append('MISSING_CUSTOMER_ID')
                    if row['Description'] is None:
                        tags.append('MISSING_DESCRIPTION')
                    if row['InvoiceNo']:
                        invoices.add(row['InvoiceNo'])
                        if row['InvoiceNo'].upper().startswith('C'):
                            tags.append('C_PREFIX')
                    if row['StockCode']:
                        stocks.add(row['StockCode'])
                        if not re.fullmatch(r'\d{5}[A-Za-z]?', row['StockCode']):
                            tags.append('STOCK_CODE_OUTSIDE_5_DIGITS_OPTIONAL_SUFFIX')
                    if row['Country']:
                        countries.add(row['Country'])
                    if isinstance(date, datetime):
                        date_min = min(date_min, date) if date_min else date
                        date_max = max(date_max, date) if date_max else date
                        per_month[date.strftime('%Y-%m')] += 1
                        invoice_times[row['InvoiceNo']].add(date)
                    if item['primary_class'] != 'INVALID':
                        quantity, milli = item['quantity'], item['unit_price_milli_gbp']
                        price = Decimal(row['UnitPrice'])
                        difference = Decimal(item['representation_difference_gbp'])
                        changed += difference != 0
                        max_difference = max(max_difference, difference)
                        price_repr_scales[max(0, -price.normalize().as_tuple().exponent)] += 1
                        max_abs_milli = max(max_abs_milli, abs(milli))
                        max_abs_amount = max(max_abs_amount, abs(item['line_amount_milli_gbp']))
                        absolute_amount_sum += abs(item['line_amount_milli_gbp'])
                        quantity_min = min(quantity_min, quantity) if quantity_min is not None else quantity
                        quantity_max = max(quantity_max, quantity) if quantity_max is not None else quantity
                        price_min = min(price_min, price) if price_min is not None else price
                        price_max = max(price_max, price) if price_max is not None else price
                        if quantity < 0:
                            tags.append('NEGATIVE_QUANTITY')
                        if milli == 1:
                            tags.append('PRICE_0_001_GBP')
                        if difference:
                            tags.append('PRICE_REPRESENTATION_TAIL')
                        key = (row['InvoiceNo'], row['StockCode'], row['Description'], quantity,
                               date, price, row['CustomerID'], row['Country'])
                        if seen[key]:
                            tags.append('DUPLICATE_CANDIDATE_AFTER_FIRST')
                        seen[key] += 1
                    flags.update(tags)
                    for tag in set(tags + [item['primary_class']]):
                        if len(examples[tag]) < 5:
                            examples[tag].append({'source_row_num': row_number, 'raw_values': row,
                                                  'invoice_date_source': str(date), **item})
                node.clear()
                if sheet_data is not None:
                    sheet_data.clear()
    if not count:
        raise ValueError('EMPTY_WORKBOOK')
    reconciled = sum(classes.values()) == count
    safe_sum = absolute_amount_sum <= INT64_MAX
    return {
        'status': 'PASS' if reconciled and not classes['INVALID'] and safe_sum else 'FAIL',
        'method': 'Direct OOXML strings and Decimal; date-only conversion uses openpyxl. Audit only, no database.',
        'transform_version': TRANSFORM_VERSION, 'rows': count, 'columns': FIELDS,
        'sheet_names': names, 'sheet_xml': sheet_path, 'xlsx_members': members,
        'date_epoch': '1900', 'source_timezone': 'UNSPECIFIED',
        'date_min': str(date_min), 'date_max': str(date_max), 'per_month_rows': dict(sorted(per_month.items())),
        'invoice_unique_count': len(invoices), 'stock_code_unique_count': len(stocks), 'country_unique_count': len(countries),
        'null_counts': dict(nulls), 'primary_class_counts': dict(classes), 'row_reconciliation': reconciled,
        'quality_flags_overlap': True, 'quality_flags': dict(sorted(flags.items())),
        'exclusion_and_invalid_reasons': dict(reasons),
        'duplicates_policy': 'Retain every source row; parsed eight-field duplicate candidates are quality labels only.',
        'duplicate_candidate_rows_after_first': sum(n - 1 for n in seen.values()),
        'rows_in_duplicate_groups': sum(n for n in seen.values() if n > 1),
        'invoice_time_consistency': {
            'multiple_timestamp_invoice_count': sum(len(v) > 1 for v in invoice_times.values()),
            'multiple_date_invoice_count': sum(len({d.date() for d in v}) > 1 for v in invoice_times.values()),
            'multiple_month_invoice_count': sum(len({d.strftime('%Y-%m') for d in v}) > 1 for v in invoice_times.values())},
        'quantity_min': quantity_min, 'quantity_max': quantity_max,
        'unit_price_min_raw_decimal': str(price_min), 'unit_price_max_raw_decimal': str(price_max),
        'formula_cells': formula_cells,
        'normalization': {'quantum_gbp': str(QUANTUM), 'rounding': 'ROUND_HALF_UP',
                          'allowed_representation_difference_gbp': str(TOLERANCE),
                          'rows_with_any_difference': changed, 'max_absolute_difference_gbp': str(max_difference),
                          'price_0_001_rows': flags['PRICE_0_001_GBP'],
                          'raw_decimal_scale_counts': dict(sorted(price_repr_scales.items())),
                          'raw_representation_retained': 'Original XLSX OOXML cell <v> text plus row-addressed examples; never rewritten.'},
        'int64_check': {'max_abs_unit_price_milli_gbp': max_abs_milli, 'max_abs_line_amount_milli_gbp': max_abs_amount,
                        'sum_absolute_line_amount_milli_gbp': absolute_amount_sum, 'limit': INT64_MAX, 'safe': safe_sum},
        'examples': dict(examples)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path)
    parser.add_argument('--xlsx', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory; never overwrite a prior run')
    parser.add_argument('--allow-new-version', action='store_true', help='Explicit separate-version audit; never imply historical reference match')
    args = parser.parse_args()
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print('AUDIT=FAIL: output directory already exists; choose a new run directory', file=sys.stderr)
        return 2
    identity = {}
    try:
        zip_layout = None
        if args.zip:
            identity['zip'] = {'path': str(args.zip.resolve()), 'bytes': args.zip.stat().st_size, 'sha256': file_hash(args.zip)}
            zip_layout = extract_verified(args.zip, args.xlsx)
        identity['xlsx'] = {'path': str(args.xlsx.resolve()), 'bytes': args.xlsx.stat().st_size, 'sha256': file_hash(args.xlsx)}
        match = identity['xlsx']['sha256'] == EXPECTED_XLSX
        if not match and not args.allow_new_version:
            raise ValueError('WORKBOOK_VERSION_DIFFERENT: record actual hash and rerun to a new directory with --allow-new-version; old references disabled')
        result = audit_workbook(args.xlsx)
        result.update({'audited_at_utc': datetime.now(timezone.utc).isoformat(), 'source_url': OFFICIAL_URL,
                       'files': identity, 'zip_members': zip_layout, 'historical_workbook_hash_match': match,
                       'version_status': 'HISTORICAL_BASELINE' if match else 'NEW_VERSION_REQUIRES_REVIEW',
                       'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                                       'openpyxl': metadata.version('openpyxl')},
                       'script_sha256': file_hash(Path(__file__)),
                       'git_sha_at_run': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()})
        write_json(args.output / 'audit.json', result)
        print(json.dumps({k: result[k] for k in ('status', 'rows', 'primary_class_counts', 'normalization', 'int64_check')}, indent=2))
        return 0 if result['status'] == 'PASS' else 2
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        write_json(args.output / 'failure.json', {'status': 'FAIL', 'error': str(exc), 'files': identity,
                                                'failed_at_utc': datetime.now(timezone.utc).isoformat()})
        print(f'AUDIT=FAIL: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
