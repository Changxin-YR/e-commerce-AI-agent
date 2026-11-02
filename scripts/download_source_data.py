#!/usr/bin/env python3
r"""Get or verify the UCI 352 original file. This does NOT import it into the app.

Only an official hash-verified copy may be considered the previously audited baseline.
Windows: python scripts/download_source_data.py --download
Or:      python scripts/download_source_data.py --verify-xlsx "C:\path\Online Retail.xlsx"
"""
from __future__ import annotations
import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'data' / 'raw' / 'online_retail_uci352.zip'
OFFICIAL_URL = 'https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip'
EXPECTED_ZIP = 'f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b'
EXPECTED_XLSX = '43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d'
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_XLSX_BYTES = 60 * 1024 * 1024

def file_hash(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()

def check_xlsx(path: Path) -> None:
    actual=file_hash(path)
    if actual != EXPECTED_XLSX:
        raise ValueError(f'XLSX SHA256 differs. actual={actual}; expected={EXPECTED_XLSX}. Record version and re-audit; do not use old reference values.')
    print('XLSX_SHA256=PASS', actual)

def check_zip(path: Path) -> None:
    if path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError('ZIP too large for known baseline')
    actual=file_hash(path)
    if actual != EXPECTED_ZIP:
        raise ValueError(f'ZIP SHA256 differs. actual={actual}; expected={EXPECTED_ZIP}. Record source changes, do not use old reference values.')
    with zipfile.ZipFile(path) as z:
        items=[x for x in z.infolist() if not x.is_dir()]
        if len(items)!=1 or Path(items[0].filename).name not in ('Online Retail.xlsx','Online_Retail.xlsx'):
            raise ValueError('Unexpected UCI ZIP layout')
        if items[0].file_size>MAX_XLSX_BYTES or items[0].filename.startswith(('/', '\\')) or '..' in Path(items[0].filename).parts:
            raise ValueError('Unsafe ZIP member')
        h=hashlib.sha256()
        with z.open(items[0]) as f:
            for b in iter(lambda:f.read(1024*1024),b''):
                h.update(b)
        if h.hexdigest()!=EXPECTED_XLSX:
            raise ValueError('XLSX inside ZIP hash differs from audited baseline')
    print('UCI_352_SOURCE=PASS', actual)
    print('ORIGINAL_FILE=', path)

def download() -> None:
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    if TARGET.exists():
        check_zip(TARGET)
        return
    fd,tmp=tempfile.mkstemp(prefix='uci352_',suffix='.partial',dir=TARGET.parent)
    os.close(fd)
    tmp=Path(tmp)
    try:
        req=urllib.request.Request(OFFICIAL_URL, headers={'User-Agent':'University research dataset reproducibility downloader/1.0'})
        with urllib.request.urlopen(req,timeout=40) as response, tmp.open('wb') as out:
            total=0
            while True:
                b=response.read(1024*1024)
                if not b: break
                total += len(b)
                if total>MAX_ZIP_BYTES:
                    raise ValueError('Download exceeds size limit')
                out.write(b)
        check_zip(tmp)
        os.replace(tmp,TARGET)
        print('SAVED=',TARGET)
    finally:
        tmp.unlink(missing_ok=True)

def main()->int:
    p=argparse.ArgumentParser(description='Download or verify UCI Online Retail original bytes')
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--download',action='store_true',help='Download official ZIP if absent; verify SHA before saving')
    g.add_argument('--verify-zip',type=Path,help='Verify an existing ZIP, e.g. manual download')
    g.add_argument('--verify-xlsx',type=Path,help='Verify an existing extracted XLSX')
    args=p.parse_args()
    try:
        if args.download: download()
        elif args.verify_zip: check_zip(args.verify_zip)
        else: check_xlsx(args.verify_xlsx)
        return 0
    except (OSError,ValueError,zipfile.BadZipFile,TimeoutError) as e:
        print('SOURCE_DATA=BLOCKED_OR_DIFFERENT:',e,file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
