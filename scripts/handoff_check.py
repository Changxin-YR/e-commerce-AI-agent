#!/usr/bin/env python3
"""Check only the immutable handoff package. Not an app/business/LLM test."""
from __future__ import annotations
import json, hashlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'PACKAGE_MANIFEST.json'

def main()->int:
    problems=[]
    try:
        m=json.loads(MANIFEST.read_text(encoding='utf-8'))
        if m.get('version')!='1.5': problems.append('wrong manifest version')
        if m.get('project_id')!=ROOT.name: problems.append('project root mismatch')
        if m.get('implementation_status')!='NOT_STARTED':
            problems.append('handoff manifest incorrectly claims business implementation')
        members=m.get('immutable_files')
        if not isinstance(members,list) or not members:
            problems.append('manifest missing immutable_files')
            members=[]
        for item in members:
            rel=item['path']; p=ROOT/rel
            if not p.is_file(): problems.append('missing: '+rel); continue
            b=p.read_bytes()
            if len(b)!=item['bytes'] or hashlib.sha256(b).hexdigest()!=item['sha256']:
                problems.append('immutable file changed: '+rel)
        for rel in ['DEV_FIRST.md','CODEX_START.md','CODEX_FIRST_STEP.md','docs/dev/DEVELOPMENT_ROADMAP.md','docs/dev/FEATURE_ACCEPTANCE.md','docs/dev/steps/00_00_BOOTSTRAP.md','docs/plan/21_V14_DECISIONS.md','scripts/download_source_data.py']:
            if not any(item.get('path')==rel for item in members): problems.append('missing new immutable target: '+rel)
        status=ROOT/'docs/STATUS.json'
        j=json.loads(status.read_text(encoding='utf-8'))
        if j.get('project_id')!=ROOT.name: problems.append('STATUS.json project mismatch')
        for x in (ROOT/'docs/plan/fixtures').glob('*.json'):
            f=json.loads(x.read_text(encoding='utf-8'))
            if f.get('source_kind')!='test_fixture':
                problems.append('not tagged test_fixture: '+x.name)
    except (OSError,ValueError,KeyError,TypeError) as e:
        problems.append('invalid JSON or read error: '+str(e))
    if problems:
        print('HANDOFF_CHECK=FAIL')
        for x in problems: print('-',x)
        return 1
    print('HANDOFF_CHECK=PASS')
    print('CHECKED_IMMUTABLE_FILES=',len(members))
    print('PROJECT=',ROOT.name)
    print('BUSINESS_IMPLEMENTATION=NOT_TESTED_BY_HANDOFF_CHECK')
    return 0
if __name__=='__main__': raise SystemExit(main())
