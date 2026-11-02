"""Real UCI + real HTTP/checkpoints/process restart, with a named scripted provider.

This is engineering verification only. No live model calls or academic evaluation.
The child fixture app is isolated from the ordinary application entry point.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def server_app():
    from backend.app.config import Settings
    from backend.app.main import create_app
    from backend.app.agent.provider import ScriptedProvider
    output=Path(os.environ['AGENT_FIXTURE_OUTPUT'])
    settings=Settings(_env_file=None,app_env='test',database_url='sqlite:///'+os.environ['AGENT_FIXTURE_DATABASE'],
        app_port=int(os.environ['AGENT_FIXTURE_PORT']),import_cache_dir=output/'uploads',allow_paid_model_calls=False,
        model_max_total_requests=200,model_max_total_tokens=5_000_000,model_max_tokens_per_run=300_000)
    def model(messages,n):
        initial=json.loads(messages[1]['content']); d=initial['dataset_id']
        scenario=initial['question'].split('test_fixture_case=')[-1]
        if scenario=='crash' and os.environ.get('AGENT_FIXTURE_CRASH')=='1':
            (output/'attempt-sent.marker').write_text('test_fixture provider entered after durable SENT',encoding='utf-8')
            time.sleep(120)
        prior=[json.loads(m['content']) for m in messages if m['role']=='tool']
        def answer(action,message,claims=None,fields=None):
            return dict(role='assistant',content=json.dumps(dict(action=action,message=message,claims=claims or [],fields=fields or []),ensure_ascii=False))
        def call(name,args):
            return dict(role='assistant',content=None,tool_calls=[dict(id='fixture_'+str(len(prior)),type='function',
                function=dict(name=name,arguments=json.dumps(args)))])
        if scenario=='unsupported': return answer('unsupported','源数据没有采购成本，无法计算利润。')
        if scenario=='clarify' and len(messages)==2: return answer('clarify','请提供历史月份。',fields=['period'])
        if scenario=='tool_error' and not prior: return call('execute_sql',dict(query='not allowed'))
        successful=[x for x in prior if not x.get('error')]
        if not successful:
            if scenario=='compare':
                return call('compare_periods',dict(dataset_id=d,metric='net_amount',
                    baseline=dict(date_from='2011-09-01',date_to='2011-10-01'),
                    current=dict(date_from='2011-10-01',date_to='2011-11-01')))
            dates={'partial':('2011-12-01','2012-01-01'),'no_data':('2012-01-01','2012-02-01')}.get(scenario,('2011-09-01','2011-10-01'))
            return call('query_metric_series',dict(dataset_id=d,metric='net_amount',date_from=dates[0],date_to=dates[1]))
        result=successful[-1]
        if result['status']=='NO_DATA': return answer('answer','所选期间没有数据，无法给出交易金额。')
        field='delta_exact' if scenario=='compare' else 'points.0.value_exact'
        value=result['data']['delta_exact'] if scenario=='compare' else result['data']['points'][0]['value_exact']
        return answer('answer','数值来自保存的工具结果；覆盖范围和限制见证据。',[
            dict(tool_call_id=result['tool_call_id'],field_path=field,label='净交易金额差额' if scenario=='compare' else '净交易金额',value=value)])
    return create_app(settings,test_provider=ScriptedProvider(model))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.database=args.database.resolve(); args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(scope='D6_real_UCI_HTTP_and_process_restart_with_test_fixture_provider',
        started_at=datetime.now(timezone.utc).isoformat(),checks=[],runs=[],servers=[],external_model_calls=0,
        live_model_verified='BLOCKED_AUTHORIZATION',formal_experiments='NOT_STARTED',invocation_id=uuid4().hex)
    process=client=log=db=None; ordinal=0
    def check(name,actual,expected):
        report['checks'].append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
        if actual!=expected: raise AssertionError(name)
    def stop():
        nonlocal process,client,log
        if client: client.close(); client=None
        if process:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            report['servers'][-1]['exit_code']=process.returncode; process=None
        if log: log.close(); log=None
    def start(crash=False):
        nonlocal process,client,log,ordinal
        ordinal+=1
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        env=os.environ.copy(); env.update(AGENT_FIXTURE_DATABASE=args.database.as_posix(),AGENT_FIXTURE_OUTPUT=str(args.output),
            AGENT_FIXTURE_PORT=str(port),AGENT_FIXTURE_CRASH='1' if crash else '0',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        argv=[sys.executable,'-m','uvicorn','scripts.verify_agent:server_app','--factory','--host','127.0.0.1','--port',str(port)]
        log=(args.output/f'server-{ordinal}.log').open('wb')
        process=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        report['servers'].append(dict(argv=argv,pid=process.pid,test_fixture=True,crash_fixture=crash))
        client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=60,trust_env=False,headers={'Origin':'http://127.0.0.1:5173'})
        for _ in range(160):
            try:
                if client.get('/healthz').status_code==200: return
            except httpx.HTTPError: pass
            time.sleep(.1)
        raise RuntimeError('Owned fixture server failed startup')
    def create(variant,scenario):
        body=dict(dataset_id=dataset,variant=variant,question='开发工程夹具 test_fixture_case='+scenario,idempotency_key=report['invocation_id']+'-'+variant+'-'+scenario)
        response=client.post('/api/v1/runs',json=body); check(variant+'_'+scenario+'_accepted',response.status_code,202)
        return response.json()['run_id']
    def wait(run_id):
        for _ in range(400):
            response=client.get('/api/v1/runs/'+run_id); response.raise_for_status(); result=response.json()
            if result['run_status'] not in ('QUEUED','RUNNING'): return result
            time.sleep(.05)
        raise AssertionError('Run timeout')
    def saved_report(run):
        return json.loads(db.execute('SELECT content FROM reports WHERE report_id=?',(run['result_ref'],)).fetchone()[0])
    try:
        db=sqlite3.connect(args.database.as_uri()+'?mode=ro',uri=True)
        dataset,rows=db.execute("SELECT dataset_id,row_count FROM dataset_snapshots WHERE status='READY'").fetchone()
        check('real_UCI_rows',rows,541909)
        report['dataset_id']=dataset
        # Independent normalized source-column SQL, never the application's metric implementation.
        from scripts.verify_tools import reference,PERIOD,CURRENT,number,sha
        sep=reference(db,dataset,PERIOD,'net_amount'); octv=reference(db,dataset,CURRENT,'net_amount')
        dec=reference(db,dataset,dict(date_from='2011-12-01',date_to='2012-01-01'),'net_amount')
        report['independent_reference']=dict(september=number(sep,'net_amount'),delta=number(octv-sep,'net_amount'),december=number(dec,'net_amount'))
        report['source_hashes']={k:v['sha256'] for k,v in json.loads((ROOT/'data/manifest.json').read_text('utf-8'))['files'].items()}
        start()
        for variant in ('B1','B2'):
            for scenario in ('single','compare','unsupported','tool_error','partial','no_data'):
                run_id=create(variant,scenario); run=wait(run_id); report['runs'].append(run)
                check(variant+'_'+scenario+'_status',run['run_status'],'PASS')
                content=saved_report(run)
                if scenario in ('single','tool_error','compare','partial'):
                    expected={'compare':octv-sep,'partial':dec}.get(scenario,sep)
                    check(variant+'_'+scenario+'_exact',content['claims'][0]['value'],number(expected,'net_amount'))
                if scenario=='partial': check(variant+'_partial_warning','PERIOD_NOT_FULLY_COVERED' in content['warnings'],True)
                if scenario=='no_data': check(variant+'_no_data_no_numbers',content['claims'],[])
                if scenario=='unsupported': check(variant+'_unsupported_action',content['action'],'unsupported')
                if scenario=='tool_error': check(variant+'_recovered_tool_error',run['tool_calls'][0]['result']['error']['code'],'UNSUPPORTED_TOOL')
                before=(len(run['attempts']),run['usage'],run['result_ref'])
                for _ in range(3):
                    again=client.get('/api/v1/runs/'+run_id).json()
                    check(variant+'_'+scenario+'_history_readonly',(len(again['attempts']),again['usage'],again['result_ref']),before)
        waiting=[]
        for variant in ('B1','B2'):
            run=wait(create(variant,'clarify')); check(variant+'_waiting',run['run_status'],'WAITING_INPUT'); waiting.append(run)
        stop(); start()
        for original in waiting:
            run_id=original['run_id']; current=client.get('/api/v1/runs/'+run_id).json()
            check(original['variant']+'_restart_waiting',current,original)
            payload=dict(revision=current['revision'],idempotency_key='clarification',answers={'period':'2011-09'})
            response=client.post('/api/v1/runs/'+run_id+'/input',json=payload); check('reply_accepted',response.status_code,200)
            done=wait(run_id); report['runs'].append(done); check('reply_completed',done['run_status'],'PASS')
            check('thread_unchanged',done['thread_id'],original['thread_id']); check('exact_after_restart',saved_report(done)['claims'][0]['value'],number(sep,'net_amount'))
            for _ in range(3): check('duplicate_reply_unchanged',client.post('/api/v1/runs/'+run_id+'/input',json=payload).json(),done)
            check('single_report',db.execute('SELECT COUNT(*) FROM reports WHERE run_id=?',(run_id,)).fetchone()[0],1)
        stop(); start(crash=True)
        run_id=create('B2','crash')
        marker=args.output/'attempt-sent.marker'
        for _ in range(200):
            if marker.exists(): break
            time.sleep(.05)
        check('inflight_marker',marker.exists(),True)
        stop(); start()
        interrupted=client.get('/api/v1/runs/'+run_id).json()
        report['interrupted_before_resume']=interrupted
        check('process_restart_interrupted',interrupted['run_status'],'INTERRUPTED')
        check('sent_outcome_unknown',interrupted['attempts'][0]['status'],'UNKNOWN_OUTCOME')
        check('unknown_tokens_not_zero',interrupted['usage']['confirmed_total_tokens'],None)
        check('unknown_reservation_retained',interrupted['usage']['tokens_occupied'],32768)
        response=client.post('/api/v1/runs/'+run_id+'/resume',json=dict(revision=interrupted['revision'],idempotency_key='explicit-resume'))
        check('explicit_resume',response.status_code,200)
        done=wait(run_id); report['runs'].append(done); check('interrupted_resumed',done['run_status'],'PASS')
        check('unknown_attempt_retained',done['usage']['unknown_usage_attempts'],1)
        check('new_attempts_counted',done['usage']['requests_reserved'],3)
        check('unknown_total_remains_unknown',done['usage']['confirmed_total_tokens'],None)
        check('exact_after_interruption',saved_report(done)['claims'][0]['value'],number(sep,'net_amount'))
        stop()
        check('database_integrity',db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        check('original_transaction_rows',db.execute('SELECT COUNT(*) FROM transaction_rows').fetchone()[0],541909)
        check('earlier_query_history',db.execute('SELECT COUNT(*) FROM query_history').fetchone()[0],2)
        report['database_after_sha256']=sha(args.database)
        report['status']='PASS'
    except Exception as error:
        report['status']='FAIL'; report['error_type']=type(error).__name__; report['error']=str(error)
        raise
    finally:
        stop()
        if db: db.close()
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:report[k] for k in ('scope','status','external_model_calls','live_model_verified')}|{'checks':len(report['checks']),'runs':len(report['runs'])},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
