from pathlib import Path
from decimal import Decimal
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd

BASE = Path(__file__).resolve().parent
source = BASE / 'Online_Retail.xlsx'
df = pd.read_excel(source, engine='openpyxl', dtype={'InvoiceNo':'string','StockCode':'string','Description':'string','CustomerID':'string'})
cancel = df.InvoiceNo.str.upper().str.startswith('C').fillna(False)
qsign = df.Quantity.map(lambda v: 'positive' if v > 0 else 'negative' if v < 0 else 'zero')
psign = df.UnitPrice.map(lambda v: 'positive' if v > 0 else 'negative' if v < 0 else 'zero')
report = {
    'audited_at_utc': datetime.now(timezone.utc).isoformat(),
    'source_url':'https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip',
    'scope':'Direct audit of original official XLSX; no cleaning or metric policy applied.',
    'file_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'file_bytes':source.stat().st_size,
    'rows':len(df),
    'columns':list(df.columns),
    'null_counts':{k:int(v) for k,v in df.isna().sum().items()},
    'date_min':str(df.InvoiceDate.min()),
    'date_max':str(df.InvoiceDate.max()),
    'invoice_unique_count':int(df.InvoiceNo.nunique()),
    'stock_code_unique_count':int(df.StockCode.nunique()),
    'cancellation_prefix_rows':int(cancel.sum()),
    'exact_duplicates_after_first_all_columns':int(df.duplicated().sum()),
    'rows_in_duplicate_groups_all_columns':int(df.duplicated(keep=False).sum()),
    'quantity_min':int(df.Quantity.min()),
    'quantity_max':int(df.Quantity.max()),
    'unit_price_min':str(df.UnitPrice.min()),
    'unit_price_max':str(df.UnitPrice.max()),
    'cancel_quantity_cross':pd.crosstab(cancel.map({True:'C_prefix',False:'non_C'}), qsign).to_dict(),
    'cancel_price_cross':pd.crosstab(cancel.map({True:'C_prefix',False:'non_C'}), psign).to_dict(),
    'quantity_price_cross':pd.crosstab(qsign, psign).to_dict(),
    'per_month_rows':{str(k):int(v) for k,v in df.groupby(df.InvoiceDate.dt.to_period('M')).size().items()},
}
price_scale = df.UnitPrice.map(lambda v: max(0, -Decimal(str(v)).normalize().as_tuple().exponent))
report['unit_price_scale_after_read_str_normalization'] = {str(k):int(v) for k,v in price_scale.value_counts().sort_index().items()}
report['unit_price_gt_2_decimals_examples'] = df.loc[price_scale>2,['InvoiceNo','StockCode','Description','Quantity','UnitPrice']].head(15).to_dict(orient='records')
special = ~df.StockCode.str.match(r'^\d{5}[A-Za-z]?$', na=False)
report['stock_codes_outside_5_digits_optional_suffix'] = {str(k):int(v) for k,v in df.loc[special,'StockCode'].value_counts().items()}
report['special_stock_examples'] = df.loc[special,['StockCode','Description']].drop_duplicates().head(35).fillna('').to_dict(orient='records')
report['nonC_negative_quantity_examples'] = df.loc[(~cancel)&(df.Quantity<0),['InvoiceNo','StockCode','Description','Quantity','UnitPrice']].head(15).fillna('').to_dict(orient='records')
report['negative_price_rows'] = df.loc[df.UnitPrice<0,['InvoiceNo','StockCode','Description','Quantity','UnitPrice']].fillna('').to_dict(orient='records')
report['price_scale_note'] = 'Decimal(str(parsed numeric value)); raw OOXML numeric strings also audited below to reveal storage representation.'
report['invoice_consistency_groups_with_multiple_non_null_values'] = {
    col:int((df.groupby('InvoiceNo')[col].nunique()>1).sum())
    for col in ['Country','CustomerID','InvoiceDate']
}
report['sheet_names'] = pd.ExcelFile(source, engine='openpyxl').sheet_names
out = BASE / 'audit_retail.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
raw_scales = Counter()
raw_fraction_examples = Counter()
with zipfile.ZipFile(source) as book:
    with book.open('xl/worksheets/sheet1.xml') as stream:
        for event,node in ET.iterparse(stream, events=('end',)):
            if node.tag == ns+'c':
                if node.attrib.get('r','').startswith('F') and node.attrib.get('t') != 's':
                    val = node.find(ns+'v')
                    if val is not None and val.text is not None:
                        d = Decimal(val.text)
                        scale = max(0, -d.normalize().as_tuple().exponent)
                        raw_scales[scale]+=1
                        if scale>2: raw_fraction_examples[val.text]+=1
                node.clear()
report['raw_OOXML_unit_price_normalized_scales'] = dict(sorted(raw_scales.items()))
report['raw_OOXML_unit_price_gt2_decimal_values'] = dict(raw_fraction_examples.most_common(25))
out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
