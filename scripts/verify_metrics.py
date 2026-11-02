"""D3 real HTTP acceptance against independent OOXML audit and independent SQL.

Requires an already imported/migrated database; never creates or imports missing
data. Reuploads only known existing containers to test idempotence. Writes one
explicit history query. Stops only its own local server. No model calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def independent_sql(database, dataset_id):
    """Reclassify stored source fields and multiply quantity*price independently."""
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        result = {'classes': dict(db.execute('SELECT primary_class,COUNT(*) FROM transaction_rows WHERE dataset_id=? GROUP BY 1',(dataset_id,))),
                  'rows': db.execute('SELECT COUNT(*) FROM transaction_rows WHERE dataset_id=?',(dataset_id,)).fetchone()[0]}
        result['monthly']={}
        for month,following in [('2011-09','2011-10'),('2011-10','2011-11')]:
            params=(dataset_id,month+'-01 00:00:00',following+'-01 00:00:00')
            base=' FROM transaction_rows WHERE dataset_id=? AND invoice_date_source>=? AND invoice_date_source<? '
            pos="AND lower(substr(invoice_no,1,1))!='c' AND quantity>0 AND unit_price_milli_gbp>0"
            can="AND lower(substr(invoice_no,1,1))='c' AND quantity<0 AND unit_price_milli_gbp>0"
            positive=db.execute('SELECT SUM(quantity*unit_price_milli_gbp),COUNT(DISTINCT invoice_no),COUNT(*)'+base+pos,params).fetchone()
            cancellation=db.execute('SELECT -SUM(quantity*unit_price_milli_gbp),COUNT(*)'+base+can,params).fetchone()
            result['monthly'][month]=dict(positive_milligbp=positive[0],cancellation_milligbp=cancellation[0],
                net_milligbp=positive[0]-cancellation[0],positive_invoice_count=positive[1],positive_rows=positive[2],cancellation_rows=cancellation[1])
        result['milli_rows']=[list(r) for r in db.execute('SELECT source_row_num,unit_price_raw,unit_price_milli_gbp FROM transaction_rows WHERE dataset_id=? AND unit_price_milli_gbp=1 ORDER BY source_row_num',(dataset_id,))]
        result['examples']={}
        for name,predicate in [('negative_price','unit_price_milli_gbp<0'),('non_c_negative',"invoice_no NOT LIKE 'c%' AND quantity<0"),
                               ('zero_price','unit_price_milli_gbp=0'),('duplicate',"quality_flags LIKE '%DUPLICATE_CANDIDATE_AFTER_FIRST%'")]:
            result['examples'][name]=list(db.execute('SELECT source_row_num,primary_class,quality_flags'+
                ' FROM transaction_rows WHERE dataset_id=? AND '+predicate+' ORDER BY source_row_num LIMIT 1',(dataset_id,)).fetchone())
        result['tables']={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in
                          ('dataset_snapshots','import_batches','transaction_rows','analysis_runs','reports','query_history')}
        result['revision']=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        result['integrity']=db.execute('PRAGMA quick_check').fetchall()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New run directory; previous evidence is never overwritten')
    parser.add_argument('--reference',type=Path,default=ROOT/'docs/evidence/d1/audit_normalization_and_reference.json')
    parser.add_argument('--browser',action='store_true',help='Also verify saved real JSON through Edge and reload; no D4 business UI claim')
    args=parser.parse_args()
    args.database,args.output=args.database.resolve(),args.output.resolve()
    try:
        args.output.mkdir(parents=True,exist_ok=False)
    except FileExistsError:
        print('FAIL: choose a new evidence directory',file=sys.stderr)
        return 2
    report={'scope':'D3_development_acceptance_not_academic_experiment','started_at':datetime.now(timezone.utc).isoformat(),
            'checks':[],'model_calls':0,'business_ui':'NOT_IMPLEMENTED_D4'}
    process=log=client=None

    def check(name,actual,expected):
        ok=actual==expected
        report['checks'].append(dict(name=name,actual=actual,expected=expected,passed=ok))
        if not ok:
            raise AssertionError(name)

    def stop():
        nonlocal process,log
        if process:
            process.terminate()
            process.wait(timeout=15)
            report['servers'][-1].update(stop_exit_code=process.returncode,intentional_stop=True)
            process=None
        if log:
            log.close()
            log=None

    try:
        if not args.database.is_file():
            raise FileNotFoundError('Existing imported database is required')
        manifest=json.loads((ROOT/'data/manifest.json').read_text('utf-8'))
        d1_path=ROOT/'docs/evidence/d1/audit.json'
        d1=json.loads(d1_path.read_text('utf-8'))
        audit=json.loads(args.reference.read_text('utf-8'))
        report['reference']={'path':str(args.reference.resolve()),'sha256':sha(args.reference)}
        paths={kind:ROOT/info['path'] for kind,info in manifest['files'].items()}
        for kind,path in paths.items():
            check(kind+'_sha256',sha(path),manifest['files'][kind]['sha256'])
        check('independent_reference_source',audit['source_xlsx_sha256'],manifest['files']['xlsx']['sha256'])
        check('d1_classification_reference_hash',sha(d1_path),manifest['evidence']['docs/evidence/d1/audit.json'])
        with sqlite3.connect(args.database.as_uri()+'?mode=ro',uri=True) as db:
            found=db.execute("SELECT dataset_id,status FROM dataset_snapshots WHERE workbook_sha256=? AND metric_version='retail-v1.2'",
                             (manifest['files']['xlsx']['sha256'],)).fetchall()
        check('one_official_ready_snapshot',len(found),1)
        dataset_id,state=found[0]
        check('ready',state,'READY')
        report['dataset_id']=dataset_id
        sql=independent_sql(args.database,dataset_id)
        report['independent_sql']=sql
        check('rows',sql['rows'],audit['rows'])
        check('class_reconciliation',sum(sql['classes'].values()),sql['rows'])
        check('classes',sql['classes'],{k:v for k,v in d1['primary_class_counts'].items() if v})
        check('milli_row_numbers',[r[0] for r in sql['milli_rows']],
              [r['excel_row'] for r in audit['normalization']['normalized_prices_requiring_more_than_2_decimal_places']])
        check('milli_raw_values',[(r[1],r[2]) for r in sql['milli_rows']],[('1E-3',1)]*4)
        for key in ('negative_price','non_c_negative','zero_price'):
            check('class_'+key,sql['examples'][key][1],'EXCLUDED_OTHER')
        check('duplicate_quality', 'DUPLICATE_CANDIDATE_AFTER_FIRST' in json.loads(sql['examples']['duplicate'][2]),True)
        check('migration_revision',sql['revision'],'0003_query_history')
        check('sqlite_integrity',sql['integrity'],[('ok',)])

        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env=os.environ.copy()
        env.update(DATABASE_URL='sqlite:///'+args.database.as_posix(),IMPORT_CACHE_DIR=str(args.output/'uploads'),
                   APP_PORT=str(port),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        client=httpx.Client(base_url=base,timeout=60,trust_env=False)

        def start(label):
            nonlocal process,log
            log=(args.output/(label+'.log')).open('wb')
            argv=[sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',str(port)]
            process=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=log,stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            report.setdefault('servers',[]).append(dict(argv=argv,pid=process.pid,log=label+'.log'))
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    if client.get('/healthz').status_code==200:
                        return
                except httpx.HTTPError:
                    pass
                if process.poll() is not None:
                    break
                time.sleep(.15)
            raise RuntimeError('Owned server did not become healthy')

        start('server')
        prefix=f'/api/v1/datasets/{dataset_id}'
        report['http_monthly']={}
        before=sha(args.database)
        for month,reference in audit['monthly_reference'].items():
            response=client.get(prefix+'/metrics/monthly',params={'month':month})
            check(month+'_http',response.status_code,200)
            result=response.json()
            report['http_monthly'][month]=result
            check(month+'_status',result['status'],'PASS')
            for metric in ('positive','cancellation','net'):
                milli=reference[metric+'_milligbp']
                check(month+'_'+metric+'_sql',sql['monthly'][month][metric+'_milligbp'],milli)
                value=Decimal(milli)/1000
                check(month+'_'+metric+'_exact',result[metric+'_amount_exact'],format(value,'.3f'))
                check(month+'_'+metric+'_display',result[metric+'_amount_display'],format(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'))
            for field,ref in [('positive_invoice_count','positive_invoice_count'),('positive_row_count','positive_rows'),('cancel_row_count','cancellation_rows')]:
                check(month+'_'+field,result[field],reference[ref])
            check(month+'_row_reconciliation',sum(result['primary_class_counts'].values()),result['matched_row_count'])
        for month,expected in [('2011-12','PARTIAL_PERIOD'),('2012-01','NO_DATA')]:
            result=client.get(prefix+'/metrics/monthly',params={'month':month}).json()
            check(month+'_coverage',result['status'],expected)
            if expected=='NO_DATA':
                check('no_data_not_zero',result['net_amount_exact'],None)
        empty=client.get(prefix+'/metrics/monthly',params=dict(month='2011-09',country='test_fixture_nonexistent_country')).json()
        check('empty_result',empty['status'],'EMPTY_RESULT')
        check('empty_zero',empty['net_amount_exact'],'0.000')
        for extra in ({'sql':'SELECT 1'},{'path':'C:/private'},{'url':'https://example.invalid'},{'month':'2011-99'}):
            check('reject_'+next(iter(extra)),client.get(prefix+'/metrics/monthly',params={'month':'2011-09',**extra}).status_code,422)
        check('bad_host',client.get('/healthz',headers={'Host':'evil.example'}).status_code,400)
        check('unknown_dataset',client.get('/api/v1/datasets/missing/metrics/monthly?month=2011-09').status_code,404)
        series=client.get(prefix+'/metrics/series',params=dict(metric='net_amount',date_from='2011-09-01',date_to='2011-11-01')).json()
        check('series_monthly_equivalence',[p['value_exact'] for p in series['points']],
              [report['http_monthly'][m]['net_amount_exact'] for m in ('2011-09','2011-10')])
        schema=client.get('/openapi.json').json()
        (args.output/'openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        check('openapi_stage',schema['info']['version'],'0.3.0')
        check('ordinary_gets_do_not_write',sha(args.database),before)

        def upload(kind):
            with paths[kind].open('rb') as f:
                return client.post('/api/v1/datasets/imports',headers={'Origin':base},files={'file':(
                    paths[kind].name,f,'application/zip' if kind=='zip' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        for kind in ('zip','xlsx','zip'):
            response=upload(kind)
            check('idempotent_'+kind+'_http',response.status_code,200)
            check('idempotent_'+kind+'_dataset',response.json()['dataset_id'],dataset_id)
        check('corrupt_upload',client.post('/api/v1/datasets/imports',headers={'Origin':base},
            files={'file':('test_fixture_corrupt.zip',b'not a zip','application/zip')}).status_code,422)
        # A real oversized multipart payload exercises the HTTP size boundary.
        check('oversize_upload',client.post('/api/v1/datasets/imports',headers={'Origin':base},
            files={'file':('test_fixture_oversize.zip',b'x'*(50*1024*1024+1),'application/zip')}).status_code,413)
        check('after_bad_upload_healthy',client.get('/healthz').status_code,200)
        check('reupload_amount_unchanged',client.get(prefix+'/metrics/monthly?month=2011-09').json(),report['http_monthly']['2011-09'])

        body=dict(idempotency_key='d3-acceptance-'+args.output.name,query=dict(kind='monthly',month='2011-09'))
        saved_response=client.post(prefix+'/queries',json=body,headers={'Origin':base})
        check('history_created',saved_response.status_code,201)
        saved=saved_response.json()
        check('saved_result',saved['result'],report['http_monthly']['2011-09'])
        check('idempotent_history',client.post(prefix+'/queries',json=body,headers={'Origin':base}).json(),saved)
        report['saved_query']=saved
        before=sha(args.database)
        history_path='/api/v1/queries/'+saved['query_id']
        check('history_get',client.get(history_path).json(),saved)
        check('history_no_write',sha(args.database),before)
        stop()
        start('server-restart')
        check('history_after_restart',client.get(history_path).json(),saved)
        check('restart_no_write',sha(args.database),before)
        if args.browser:
            argv=[shutil.which('node') or 'node',str(ROOT/'frontend/scripts/verify-metrics-browser.mjs'),base,saved['query_id'],str(args.output/'browser')]
            browser_tmp=args.output/'browser-runtime'
            browser_tmp.mkdir()
            browser_env={**env, 'TEMP':str(browser_tmp),'TMP':str(browser_tmp),'TMPDIR':str(browser_tmp),
                         'PWTEST_CACHE_DIR':str(browser_tmp/'transform-cache')}
            browser=subprocess.run(argv,cwd=ROOT,capture_output=True,env=browser_env,timeout=60)
            (args.output/'browser.stdout.txt').write_bytes(browser.stdout)
            (args.output/'browser.stderr.txt').write_bytes(browser.stderr)
            report['browser_command']={'argv':argv,'exit_code':browser.returncode}
            check('edge_history_reload_exit',browser.returncode,0)
            report['browser']=json.loads((args.output/'browser/result.json').read_text('utf-8'))
            check('browser_read_only',sha(args.database),before)
        final=independent_sql(args.database,dataset_id)
        for table,count in sql['tables'].items():
            check('final_'+table,final['tables'][table],count+(1 if table=='query_history' else 0))
        check('final_classification',final['classes'],sql['classes'])
        report['status']='PASS'
    except Exception as exc:
        report.update(status='FAIL',error_type=type(exc).__name__,error=str(exc))
    finally:
        stop()
        if client:
            client.close()
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        if args.database.is_file():
            report['database_sha256']=sha(args.database)
        (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],checks=len(report['checks']),evidence=str(args.output/'verification.json')),ensure_ascii=False))
    return 0 if report['status']=='PASS' else 2


if __name__=='__main__':
    raise SystemExit(main())
