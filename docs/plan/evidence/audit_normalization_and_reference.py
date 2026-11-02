"""Independent one-pass OOXML audit and frozen-policy monthly references.

Reads original XLSX XML without pandas or production metric functions.
The explicit 0.001 GBP normalization is accepted only if every raw Excel
numeric value differs by at most 1e-9 GBP from that decimal grid.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from openpyxl.utils.datetime import from_excel

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'Online_Retail.xlsx'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
QUANTUM = Decimal('0.001')
MAX_REPRESENTATION_DIFFERENCE = Decimal('0.000000001')
MONTHS = ('2011-09', '2011-10')

with zipfile.ZipFile(SOURCE) as book:
    strings_root = ET.fromstring(book.read('xl/sharedStrings.xml'))
    strings = [''.join(si.itertext()) for si in strings_root.findall(NS+'si')]
    invoices = {}
    monthly = {m:{'positive_milligbp':0,'cancellation_milligbp':0,
                  'positive_rows':0,'cancellation_rows':0,
                  'positive_invoice_ids':set(),'cancellation_invoice_ids':set(),
                  'included_non_digit_stock_codes':defaultdict(int)} for m in MONTHS}
    max_diff = Decimal(0)
    max_diff_rows = []
    changed_rows = 0
    excessive_rows = 0
    over_two_decimal_rows = []
    count = 0
    with book.open('xl/worksheets/sheet1.xml') as stream:
        for event,node in ET.iterparse(stream, events=('end',)):
            if node.tag != NS+'row':
                continue
            row_number = int(node.attrib['r'])
            if row_number == 1:
                node.clear()
                continue
            values = {}
            for cell in node.findall(NS+'c'):
                column = ''.join(c for c in cell.attrib.get('r','') if c.isalpha())
                v = cell.find(NS+'v')
                if v is None or v.text is None:
                    values[column] = None
                elif cell.attrib.get('t') == 's':
                    values[column] = strings[int(v.text)]
                else:
                    values[column] = v.text
            count += 1
            price = Decimal(values['F'])
            normalized = price.quantize(QUANTUM, rounding=ROUND_HALF_UP)
            diff = abs(price-normalized)
            if diff > 0:
                changed_rows += 1
            if diff > MAX_REPRESENTATION_DIFFERENCE:
                excessive_rows += 1
            sample = {'excel_row':row_number,'invoice_no':values['A'],
                      'raw_price':str(price),'normalized_price':str(normalized),
                      'difference_gbp':str(diff)}
            if diff > max_diff:
                max_diff = diff
                max_diff_rows = [sample]
            elif diff == max_diff and len(max_diff_rows) < 10:
                max_diff_rows.append(sample)
            if normalized != normalized.quantize(Decimal('0.01')):
                over_two_decimal_rows.append(sample | {'stock_code':values['B']})
            millis_decimal = normalized*1000
            assert millis_decimal == millis_decimal.to_integral_value()
            millis = int(millis_decimal)
            quantity = Decimal(values['D'])
            assert quantity == quantity.to_integral_value()
            quantity = int(quantity)
            timestamp = from_excel(float(values['E']))
            assert isinstance(timestamp,datetime)
            invoice = values['A']
            timestamp_text = timestamp.isoformat(sep=' ')
            date_text = timestamp.date().isoformat()
            month = date_text[:7]
            entry = invoices.setdefault(invoice,{'timestamps':set(),'dates':set(),'months':set()})
            entry['timestamps'].add(timestamp_text)
            entry['dates'].add(date_text)
            entry['months'].add(month)
            if month in monthly:
                target = monthly[month]
                is_cancel = invoice.upper().startswith('C')
                if not is_cancel and quantity > 0 and millis > 0:
                    target['positive_milligbp'] += quantity*millis
                    target['positive_rows'] += 1
                    target['positive_invoice_ids'].add(invoice)
                    if not values['B'].isdigit():
                        target['included_non_digit_stock_codes'][values['B']] += 1
                elif is_cancel and quantity < 0 and millis > 0:
                    target['cancellation_milligbp'] += -(quantity*millis)
                    target['cancellation_rows'] += 1
                    target['cancellation_invoice_ids'].add(invoice)
            node.clear()

assert count == 541909, 'Unexpected source row count; review source identity.'
assert excessive_rows == 0, 'Do not use three-decimal normalization: significant price precision would be lost.'

for month,result in monthly.items():
    result['net_milligbp'] = result['positive_milligbp']-result['cancellation_milligbp']
    for prefix in ('positive','cancellation','net'):
        exact = Decimal(result[prefix+'_milligbp'])/1000
        result[prefix+'_gbp_exact'] = format(exact,'.3f')
        result[prefix+'_gbp_display_half_up_2dp'] = format(exact.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
    result['positive_invoice_count'] = len(result.pop('positive_invoice_ids'))
    result['cancellation_invoice_count'] = len(result.pop('cancellation_invoice_ids'))
    result['included_non_digit_stock_codes'] = dict(sorted(result['included_non_digit_stock_codes'].items()))

multi_timestamps = {k:v for k,v in invoices.items() if len(v['timestamps'])>1}
cross_dates = {k:v for k,v in invoices.items() if len(v['dates'])>1}
cross_months = {k:v for k,v in invoices.items() if len(v['months'])>1}
serializable_invoice = lambda v: {k:sorted(values) for k,values in v.items()}
result = {
    'audited_at_utc':datetime.now(timezone.utc).isoformat(),
    'source_url':'https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip',
    'source_xlsx_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'rows':count,
    'method':'Direct OOXML records, integer milligbp arithmetic; independent from pandas audit and future production metric functions.',
    'normalization':{
        'quantum_gbp':str(QUANTUM),
        'rounding':'ROUND_HALF_UP',
        'allowed_representation_difference_gbp':str(MAX_REPRESENTATION_DIFFERENCE),
        'rows_with_any_difference':changed_rows,
        'rows_exceeding_allowed_difference':excessive_rows,
        'max_absolute_difference_gbp':str(max_diff),
        'max_difference_examples':max_diff_rows,
        'normalized_prices_requiring_more_than_2_decimal_places':over_two_decimal_rows,
        'meaning':'Workbook binary floating-point representation tails are normalized only within the stated tiny tolerance; genuine 0.001 GBP prices remain 0.001. This rule is specific to this audited XLSX snapshot, not a blanket rule for arbitrary CSV data.'
    },
    'metric_policy':{
        'metric_version':'reference-policy-2026-10-31-v1',
        'positive':'InvoiceNo not starting C/c AND Quantity>0 AND normalized UnitPrice>0; sum Quantity*UnitPrice',
        'cancellation':'InvoiceNo starting C/c AND Quantity<0 AND normalized UnitPrice>0; sum abs(Quantity*UnitPrice)',
        'net':'positive minus cancellation',
        'duplicates':'Retain exact duplicate source rows',
        'missing_customer_id':'Retain in non-customer metrics',
        'non_merchandise_lines':'Include qualifying POST, BANK CHARGES, manual or other non-merchandise codes; these are research-policy invoice-line amounts, not merchandise-only GMV or financially recognized revenue.',
        'time':'Source local unspecified; each line assigned by its original InvoiceDate; month is a half-open calendar interval.',
        'currency':'GBP'
    },
    'monthly_reference':monthly,
    'invoice_time_consistency':{
        'distinct_invoice_count':len(invoices),
        'multiple_timestamp_invoice_count':len(multi_timestamps),
        'multiple_date_invoice_count':len(cross_dates),
        'multiple_month_invoice_count':len(cross_months),
        'multiple_timestamp_details':{k:serializable_invoice(v) for k,v in sorted(multi_timestamps.items())},
        'multiple_date_details':{k:serializable_invoice(v) for k,v in sorted(cross_dates.items())},
        'multiple_month_details':{k:serializable_invoice(v) for k,v in sorted(cross_months.items())},
        'interpretation':'Multiple times do not imply multiple invoices. Count distinct InvoiceNo under the metric filters. If cross-period invoices appear in future files, a frozen invoice-period rule must explicitly handle them.'
    }
}
out=BASE/'audit_normalization_and_reference.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({
    'rows':count,
    'normalization':result['normalization'],
    'monthly_reference':monthly,
    'invoice_time_consistency_counts':{k:v for k,v in result['invoice_time_consistency'].items() if k.endswith('_count')}
},ensure_ascii=False,indent=2))
