"""D1 audit boundary tests. Small synthetic inputs here are test_fixture only."""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts import download_source_data as download
from scripts.audit_source_data import INT64_MAX, classify, normalize_price, audit_workbook
from scripts.run_independent_audits import compare_values

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('raw,normalized,milli,difference', [
    ('0.001', '0.001', 1, '0'),
    ('1E-3', '0.001', 1, '0'),
    ('2.5499999999999998', '2.550', 2550, '2E-16'),
    ('1.000000001', '1.000', 1000, '1E-9'),
    ('0', '0.000', 0, '0'),
    ('-11062.06', '-11062.060', -11062060, '0'),
])
def test_decimal_normalization_preserves_milli_prices(raw, normalized, milli, difference):
    price, value, diff = normalize_price(raw)
    assert str(price) == normalized
    assert value == milli
    assert diff == Decimal(difference)


@pytest.mark.parametrize('raw', ['0.0005', '1.0000000011', 'NaN', 'Infinity', '-Infinity', 'test_fixture', '', '1e40'])
def test_reject_precision_loss_and_nonfinite_prices(raw):
    with pytest.raises(ValueError):
        normalize_price(raw)


@pytest.mark.parametrize('invoice,quantity,price,expected,reason', [
    ('536365', '1', '0.001', 'POSITIVE', None),
    ('C536365', '-1', '2', 'CANCELLATION', None),
    ('c536365', '-1', '2', 'CANCELLATION', None),
    ('C536365', '1', '2', 'EXCLUDED_OTHER', 'C_NONNEGATIVE_QUANTITY'),
    ('C536365', '0', '2', 'EXCLUDED_OTHER', 'C_NONNEGATIVE_QUANTITY'),
    ('536365', '-1', '0', 'EXCLUDED_OTHER', 'NON_C_NEGATIVE_QUANTITY'),
    ('536365', '1', '0', 'EXCLUDED_OTHER', 'ZERO_PRICE'),
    ('536365', '1', '-2', 'EXCLUDED_OTHER', 'NEGATIVE_PRICE'),
    ('536365', '1.2', '2', 'INVALID', 'QUANTITY_NOT_INTEGER'),
    ('536365', '1', '0.0005', 'INVALID', 'PRICE_PRECISION_EXCEEDS_1E-9'),
    ('536365', str(INT64_MAX), '2', 'INVALID', 'LINE_AMOUNT_INT64_OVERFLOW'),
    ('536365', str(INT64_MAX + 1), '0', 'INVALID', 'QUANTITY_INT64_OVERFLOW'),
    (None, '1', '2', 'INVALID', 'MISSING_OR_INVALID_REQUIRED_FIELD'),
])
def test_mutually_exclusive_classes(invoice, quantity, price, expected, reason):
    result = classify(invoice, 'test_fixture', quantity, datetime(2011, 9, 1), price)
    assert result['primary_class'] == expected
    if reason:
        assert reason in result['reasons']


@pytest.mark.parametrize('option,kind', [('--verify-zip', 'missing'), ('--verify-xlsx', 'missing'),
                                       ('--verify-zip', 'corrupt'), ('--verify-xlsx', 'corrupt'),
                                       ('--verify-zip', 'different_zip')])
def test_download_cli_fails_clearly(tmp_path, option, kind):
    source = tmp_path / 'test_fixture.bin'
    if kind == 'corrupt':
        source.write_bytes(b'test_fixture: corrupt file')
    elif kind == 'different_zip':
        with zipfile.ZipFile(source, 'w') as z:
            z.writestr('Online Retail.xlsx', b'test_fixture: different workbook')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/download_source_data.py'), option, str(source)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'SOURCE_DATA=BLOCKED_OR_DIFFERENT' in result.stderr
    assert '=PASS' not in result.stdout


def test_download_network_error_leaves_no_success_file(tmp_path, monkeypatch):
    target = tmp_path / 'test_fixture.zip'
    monkeypatch.setattr(download, 'TARGET', target)
    def fail(*args, **kwargs):
        raise TimeoutError('test_fixture network timeout')
    monkeypatch.setattr(download.urllib.request, 'urlopen', fail)
    with pytest.raises(TimeoutError):
        download.download()
    assert not target.exists()
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('kind', ['missing', 'different', 'corrupt_structure'])
def test_audit_cli_never_fakes_success(tmp_path, kind):
    source = tmp_path / 'test_fixture.xlsx'
    if kind != 'missing':
        source.write_bytes(b'test_fixture: not an xlsx')
    output = tmp_path / 'run'
    command = [sys.executable, str(ROOT / 'scripts/audit_source_data.py'), '--xlsx', str(source), '--output', str(output)]
    if kind == 'corrupt_structure':
        command.append('--allow-new-version')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert not (output / 'audit.json').exists()
    failure = json.loads((output / 'failure.json').read_text('utf-8'))
    assert failure['status'] == 'FAIL'
    if kind == 'different':
        assert failure['files']['xlsx']['sha256']
        assert 'VERSION_DIFFERENT' in failure['error']


def test_existing_evidence_is_not_overwritten(tmp_path):
    output = tmp_path / 'run'
    output.mkdir()
    sentinel = output / 'audit.json'
    sentinel.write_text('test_fixture previous evidence', 'utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/audit_source_data.py'), '--xlsx', 'missing.xlsx',
                             '--output', str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert sentinel.read_text('utf-8') == 'test_fixture previous evidence'
    assert 'already exists' in result.stderr


def test_independent_comparison_ignores_only_run_timestamp():
    assert compare_values({'audited_at_utc': 'old', 'rows': 2}, {'audited_at_utc': 'new', 'rows': 2}) == []
    assert compare_values({'rows': 2}, {'rows': 3}) == [{'path': '$.rows', 'old': 2, 'new': 3}]
    assert compare_values({'nested': {'audited_at_utc': 'old'}}, {'nested': {'audited_at_utc': 'new'}})


def test_zip_layout_and_inner_hash_rejected_even_if_outer_hash_gate_is_bypassed_for_fixture(tmp_path, monkeypatch):
    source = tmp_path / 'test_fixture.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('unexpected.xlsx', b'test_fixture')
    monkeypatch.setattr(download, 'EXPECTED_ZIP', download.file_hash(source))
    with pytest.raises(ValueError, match='layout'):
        download.check_zip(source)
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('Online Retail.xlsx', b'test_fixture')
    monkeypatch.setattr(download, 'EXPECTED_ZIP', download.file_hash(source))
    with pytest.raises(ValueError, match='inside ZIP hash differs'):
        download.check_zip(source)
