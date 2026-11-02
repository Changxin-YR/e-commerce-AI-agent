"""Production OOXML reader, independent of the D1/pandas audit implementation."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from defusedxml import ElementTree as ET

from backend.app.imports.source import HEADERS, NS, check_time, fail, inspect_zip

INT64_MAX = 2**63 - 1
GRID = Decimal("0.001")
TOLERANCE = Decimal("1E-9")


def bounded_decimal(value: str | None) -> Decimal:
    if value is None or len(value) > 64:
        raise ValueError("MISSING_OR_OVERSIZED_NUMBER")
    number = Decimal(value)
    if not number.is_finite() or abs(number) > INT64_MAX:
        raise ValueError("NUMBER_RANGE")
    return number


def price_milli(value: str | None) -> tuple[int, bool]:
    price = bounded_decimal(value)
    normalized = price.quantize(GRID, rounding=ROUND_HALF_UP)
    if abs(price - normalized) > TOLERANCE:
        raise ValueError("PRICE_PRECISION")
    milli = int(normalized * 1000)
    if abs(milli) > INT64_MAX:
        raise ValueError("MONEY_OVERFLOW")
    return milli, price != normalized


def source_date(cell: dict) -> str:
    value = cell["value"]
    if cell["type"] == "n":
        days = bounded_decimal(value)
        if not 1 <= days < 73051:
            raise ValueError("INVALID_DATE")
        # Match XLSX millisecond resolution without binary-float price arithmetic.
        if days < 60:
            days += 1
        millis = int((days * 86400000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        result = datetime(1899, 12, 30) + timedelta(milliseconds=millis)
    elif cell["type"] == "d":
        result = datetime.fromisoformat(value)
        if result.tzinfo is not None:
            raise ValueError("TIMEZONE_NOT_SUPPORTED")
    else:
        raise ValueError("INVALID_DATE")
    return result.isoformat(sep=" ", timespec="milliseconds")


def identifier(cell: dict, required: bool = True) -> str | None:
    value = cell["value"]
    if value is None or not str(value).strip():
        if required:
            raise ValueError("MISSING_IDENTIFIER")
        return None
    if cell["type"] == "n":
        number = bounded_decimal(value)
        if number != number.to_integral_value():
            raise ValueError("INVALID_IDENTIFIER")
        return str(int(number))
    if cell["type"] not in {"s", "inlineStr", "str"}:
        raise ValueError("INVALID_IDENTIFIER")
    return value


def read_rows(path: Path, deadline: float):
    with ZipFile(path) as archive:
        inspect_zip(archive, workbook=True)
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = book.findall(f"{NS}sheets/{NS}sheet")
        props = book.find(f"{NS}workbookPr")
        if len(sheets) != 1 or sheets[0].get("name") != "Online Retail":
            fail("WORKSHEET_MISMATCH")
        if props is not None and props.get("date1904") in {"1", "true"}:
            fail("UNSUPPORTED_DATE_EPOCH")
        relid = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        matching = [r for r in rels if r.get("Id") == relid]
        if len(matching) != 1 or matching[0].get("Target") not in {"worksheets/sheet1.xml", "/xl/worksheets/sheet1.xml"}:
            fail("WORKSHEET_RELATIONSHIP_MISMATCH")
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            if archive.getinfo("xl/sharedStrings.xml").file_size > 32 * 1024 * 1024:
                fail("SHARED_STRING_LIMIT")
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(si.itertext()) for si in root]
        row_number = 0
        sheet_data = None
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            for event, element in ET.iterparse(stream, events=("start", "end")):
                if event == "start" and element.tag == NS + "sheetData":
                    sheet_data = element
                if event != "end" or element.tag != NS + "row":
                    continue
                check_time(deadline)
                row_number += 1
                if row_number > 600001 or element.get("r") != str(row_number):
                    fail("ROW_LAYOUT_OR_LIMIT")
                cells = [{"type": "n", "raw": None, "value": None} for _ in HEADERS]
                seen_columns = set()
                for cell in element:
                    reference = cell.get("r", "")
                    match = re.fullmatch(r"([A-H])([1-9][0-9]*)", reference)
                    if not match or int(match[2]) != row_number or match[1] in seen_columns:
                        fail("COLUMN_LAYOUT_MISMATCH")
                    seen_columns.add(match[1])
                    kind = cell.get("t", "n")
                    raw = cell.findtext(NS + "v")
                    value = raw
                    if kind == "s":
                        if raw is None or not raw.isdecimal() or int(raw) >= len(strings):
                            fail("INVALID_SHARED_STRING")
                        value = strings[int(raw)]
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(NS + "t"))
                    if value is not None and len(value) > 32767:
                        fail("CELL_SIZE_LIMIT")
                    record = {"type": kind, "raw": raw, "value": value}
                    formula = cell.find(NS + "f")
                    if formula is not None:
                        record["formula"] = formula.text or ""
                    cells[ord(match[1]) - ord("A")] = record
                if row_number == 1:
                    if tuple(c["value"] for c in cells) != HEADERS or any("formula" in c for c in cells):
                        fail("HEADER_MISMATCH")
                else:
                    yield row_number, cells
                element.clear()
                if sheet_data is not None:
                    sheet_data.remove(element)
        if row_number < 2:
            fail("EMPTY_WORKBOOK")


def transform_row(dataset_id: str, row_number: int, cells: list[dict]) -> dict:
    flags: list[str] = []
    row = dict(dataset_id=dataset_id, source_row_num=row_number, raw_fields=cells,
               invoice_no=None, stock_code=None, description=cells[2]["value"], quantity=None,
               invoice_date_source=None, customer_id=None, country=cells[7]["value"],
               unit_price_raw=cells[5]["raw"], unit_price_milli_gbp=None,
               line_amount_milli_gbp=None, primary_class="INVALID", quality_flags=flags)
    errors = []
    for index, field in ((0, "invoice_no"), (1, "stock_code"), (6, "customer_id")):
        try:
            row[field] = identifier(cells[index], required=index != 6)
        except (ValueError, InvalidOperation):
            errors.append("INVALID_" + field.upper())
    try:
        quantity = bounded_decimal(cells[3]["value"])
        if quantity != quantity.to_integral_value():
            raise ValueError()
        row["quantity"] = int(quantity)
    except (ValueError, InvalidOperation):
        errors.append("INVALID_QUANTITY")
    try:
        row["invoice_date_source"] = source_date(cells[4])
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        errors.append("INVALID_INVOICE_DATE")
    try:
        if cells[5]["type"] != "n":
            raise ValueError("INVALID_PRICE_TYPE")
        row["unit_price_milli_gbp"], adjusted = price_milli(cells[5]["raw"])
        if adjusted:
            flags.append("PRICE_REPRESENTATION_TAIL")
    except (ValueError, InvalidOperation) as exc:
        errors.append("PRICE_PRECISION" if str(exc) == "PRICE_PRECISION" else "INVALID_UNIT_PRICE")
    if any("formula" in cell for cell in cells):
        errors.append("FORMULA_CELL")
    quantity, price = row["quantity"], row["unit_price_milli_gbp"]
    if quantity is not None and price is not None:
        amount = quantity * price
        if abs(amount) > INT64_MAX:
            errors.append("MONEY_OVERFLOW")
        else:
            row["line_amount_milli_gbp"] = amount
    cancel = bool(row["invoice_no"] and row["invoice_no"].lower().startswith("c"))
    if cancel:
        flags.append("C_PREFIX")
    if row["customer_id"] is None:
        flags.append("MISSING_CUSTOMER_ID")
    if not row["description"]:
        flags.append("MISSING_DESCRIPTION")
    if not row["country"]:
        flags.append("MISSING_COUNTRY")
    if row["stock_code"] and not re.fullmatch(r"\d{5}[A-Za-z]?", row["stock_code"]):
        flags.append("STOCK_CODE_OUTSIDE_5_DIGITS_OPTIONAL_SUFFIX")
    if quantity is not None:
        if quantity < 0:
            flags.append("NEGATIVE_QUANTITY")
            if not cancel:
                flags.append("NON_C_NEGATIVE_QUANTITY")
        if quantity == 0:
            flags.append("ZERO_QUANTITY")
        if cancel and quantity >= 0:
            flags.append("C_NONNEGATIVE_QUANTITY")
    if price is not None:
        if price == 1:
            flags.append("PRICE_0_001_GBP")
        if price == 0:
            flags.append("ZERO_PRICE")
        if price < 0:
            flags.append("NEGATIVE_PRICE")
    if not errors:
        if not cancel and quantity > 0 and price > 0:
            row["primary_class"] = "POSITIVE"
        elif cancel and quantity < 0 and price > 0:
            row["primary_class"] = "CANCELLATION"
        else:
            row["primary_class"] = "EXCLUDED_OTHER"
    flags.extend(errors)
    # Equality of parsed source values, before price-grid normalization; never delete matches.
    identity = [row[k] for k in ("invoice_no", "stock_code", "description", "quantity", "invoice_date_source")]
    try:
        identity.append(str(bounded_decimal(row["unit_price_raw"]).normalize()))
    except (ValueError, InvalidOperation):
        identity.append(row["unit_price_raw"])
    identity.extend([row["customer_id"], row["country"]])
    row["row_fingerprint"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return row
