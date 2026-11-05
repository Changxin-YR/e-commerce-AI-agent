"""Single local executor; API state is persisted before work is scheduled."""
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from backend.app.errors import AppError
from backend.app.imports.locks import WriterLease
from backend.app.metrics.service import digest
from backend.app.metrics.tools import execute_tool
from backend.app.models import AnalysisRun, ModelAttempt, AgentToolCall, RunSubmission, Report, AgentReview
from .budget import BudgetGateway, now, redact
from .contracts import CreateRun
from .provider import DeepSeekProvider, authorization_error
from .workflow import build_graph, SYSTEM_PROMPT, PROMPT_VERSION
from .streaming import visible_message


TERMINAL={'PASS','FAIL','CANCELLED'}


class AgentService:
    def __init__(self, settings, metrics, write_engine, provider=None):
        if provider is not None and (settings.app_env!='test' or not provider.is_test):
            raise ValueError('Provider injection is restricted to explicit test fixtures')
        self.settings=settings; self.metrics=metrics; self.write_engine=write_engine
        self.provider=provider or DeepSeekProvider(settings)
        self.gateway=BudgetGateway(self)
        self.lease=WriterLease(settings.database_path.with_suffix('.agent.lock'))
        self.pool=None; self.connection=None; self.graph=None
        self.guard=threading.Lock(); self.scheduled=set()
        source_paths=sorted(Path(__file__).parent.glob('*.py'))+sorted((Path(__file__).parent.parent/'metrics').glob('*.py'))
        self.code_hash=digest({p.parent.name+'/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})

    def runtime_config(self):
        s=self.settings
        return dict(graph_version=PROMPT_VERSION,code_hash=self.code_hash,provider=self.provider.name,model_id=self.provider.model_id,
            budget_scope='test_fixture' if self.provider.is_test else 'paid_project',
            requests_per_run=s.model_max_requests_per_run,tools_per_run=s.model_max_tool_calls_per_run,
            tokens_per_run=s.model_max_tokens_per_run,total_requests=s.model_max_total_requests,
            total_tokens=s.model_max_total_tokens,tokens_per_request=s.model_max_tokens_per_request,
            output_tokens=s.model_max_output_tokens,temperature=0,automatic_retries=0,
            streaming=True,budget_reservation='utf8_request_bound_v1',
            base_url=s.model_base_url,checkpoint_schema='sqlite-v1')

    def start(self):
        try:
            self.metrics.require_database()
        except AppError:
            return
        if not self.lease.acquire():
            return
        # Never allow environment-enabled external tracing of questions or tool results.
        os.environ['LANGSMITH_TRACING']='false'; os.environ['LANGCHAIN_TRACING_V2']='false'
        with Session(self.write_engine) as session:
            interrupted=session.scalars(select(AnalysisRun).where(AnalysisRun.status=='RUNNING')).all()
            for run in interrupted:
                run.status='INTERRUPTED'; run.error_code='PROCESS_INTERRUPTED'; run.updated_at=now(); run.revision+=1
            for attempt in session.scalars(select(ModelAttempt).where(ModelAttempt.status.in_(['RESERVED','SENT']))):
                attempt.status='UNKNOWN_OUTCOME'; attempt.error_code='PROCESS_INTERRUPTED'; attempt.finished_at=now()
            # Preserve QUEUED and WAITING_INPUT. Startup does not silently issue requests.
            session.commit()
        self.connection=sqlite3.connect(str(self.settings.checkpoint_path),check_same_thread=False,timeout=10)
        saver=SqliteSaver(self.connection,serde=JsonPlusSerializer(pickle_fallback=False,
            allowed_json_modules=[],allowed_msgpack_modules=[]))
        saver.setup()
        self.graph=build_graph(self,saver)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='retail-agent')

    def close(self):
        if self.pool:
            self.pool.shutdown(wait=True)
            self.pool=None
        close_provider = getattr(self.provider, 'close', None)
        if close_provider is not None:
            close_provider()
        if self.connection:
            self.connection.close(); self.connection=None
        self.lease.close()

    def capabilities(self):
        error=authorization_error(self.settings)
        return dict(variants=['B1','B2'],live_model_status='BLOCKED' if error else 'CONFIGURED_UNVERIFIED',
            blocker_code=error,provider=self.settings.model_provider or None,model_id=self.settings.model_id or None,
            executor_ready=self.pool is not None,paid_calls_enabled=self.settings.allow_paid_model_calls,
            test_fixture=self.provider.is_test,limits=self.runtime_config(),formal_experiments='DEFERRED')

    def _ready(self):
        self.metrics.require_database()
        if self.pool is None:
            raise AppError('AGENT_EXECUTOR_UNAVAILABLE','Another process may own the local executor.',409)

    def _get(self,session,run_id):
        run=session.get(AnalysisRun,run_id)
        if run is None:
            raise AppError('NOT_FOUND','Run not found.',404)
        return run

    def run_input(self, run_id):
        with Session(self.metrics.engine) as session:
            return self._get(session,run_id).input

    def create(self, request, *, parent_run_id=None):
        self._ready()
        profile=self.metrics.profile(request.dataset_id)
        if request.conversation_parent_run_id:
            previous = self.get(request.conversation_parent_run_id)
            if previous['run_status'] not in TERMINAL:
                raise AppError('RUN_STATE_CONFLICT', 'Finish or cancel the previous turn first.', 409)
            if previous['dataset_id'] != request.dataset_id:
                raise AppError('DATASET_SCOPE_VIOLATION', 'A conversation must use the same dataset.', 422)
            parent_run_id = parent_run_id or request.conversation_parent_run_id
        body=request.model_dump(mode='json',exclude={'idempotency_key'})
        if body.get('conversation_parent_run_id') is None:
            body.pop('conversation_parent_run_id', None)
        body=redact(body,self.settings.model_api_key.get_secret_value())
        request_hash=digest(dict(input=body,parent_run_id=parent_run_id))
        with Session(self.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE'))
            existing=session.scalar(select(AnalysisRun).where(AnalysisRun.submission_key==request.idempotency_key))
            if existing:
                if existing.request_hash!=request_hash:
                    raise AppError('IDEMPOTENCY_CONFLICT','Submission key has different input.',409)
                run_id=existing.run_id; created=False
            else:
                cfg=self.runtime_config(); stamp=now(); run_id='run_'+uuid4().hex
                run=AnalysisRun(run_id=run_id,dataset_id=request.dataset_id,variant=request.variant,status='QUEUED',
                    thread_id='thread_'+uuid4().hex,parent_run_id=parent_run_id,submission_key=request.idempotency_key,
                    request_hash=request_hash,input=body,config=cfg,config_hash=digest(cfg),
                    data_version={k:profile[k] for k in ('data_hash','transform_version','metric_version')},
                    phase='received',created_at=stamp,updated_at=stamp)
                session.add(run); session.commit(); created=True
        if created: self.schedule(run_id)
        return self.get(run_id),created

    def schedule(self,run_id):
        with self.guard:
            if run_id not in self.scheduled:
                self.scheduled.add(run_id)
                self.pool.submit(self.execute,run_id)

    def get(self,run_id):
        self.metrics.require_database()
        with Session(self.metrics.engine) as session:
            run=self._get(session,run_id)
            attempts=list(session.scalars(select(ModelAttempt).where(ModelAttempt.run_id==run_id).order_by(ModelAttempt.created_at)))
            calls=list(session.scalars(select(AgentToolCall).where(AgentToolCall.run_id==run_id).order_by(AgentToolCall.step,AgentToolCall.position)))
            reviews=list(session.scalars(select(AgentReview).where(AgentReview.run_id==run_id).order_by(AgentReview.step)))
            report=session.get(Report,run.result_ref) if run.result_ref else None
            messages = [dict(id=run_id + ':question', role='user', text=run.input.get('question', ''),
                             created_at=run.created_at, status='complete')]
            submissions = session.scalars(select(RunSubmission).where(RunSubmission.run_id==run_id,
                RunSubmission.kind=='input').order_by(RunSubmission.created_at)).all()
            for reply in submissions:
                messages.append(dict(id=reply.id,role='user',text='\n'.join(reply.payload.get('answers', {}).values()),
                    created_at=reply.created_at,status='complete'))
            for attempt in attempts:
                content = visible_message((attempt.response or {}).get('message', {}).get('content'))
                if content:
                    rejected = any(r.step==attempt.step and r.kind=='answer' and r.result.get('errors') for r in reviews)
                    messages.append(dict(id=attempt.attempt_id,role='assistant',text=content,step=attempt.step,
                        created_at=attempt.created_at,status='rejected' if rejected else 'draft' if attempt.status=='SENT'
                        else 'complete' if attempt.status=='SUCCEEDED' else 'interrupted'))
            for call in calls:
                messages.append(dict(id=call.id,role='tool',text=call.tool_name,created_at=call.created_at,
                    status=call.result.get('status','UNKNOWN'),arguments=call.arguments,
                    error_code=(call.result.get('error') or {}).get('code'),evidence_ref=call.result.get('tool_call_id')))
            messages.sort(key=lambda item:item['created_at'])
            conversation = self._conversation(session, run.input.get('conversation_parent_run_id'))
            known=[a.usage['total_tokens'] for a in attempts if a.usage is not None]
            return dict(run_id=run_id,thread_id=run.thread_id,parent_run_id=run.parent_run_id,dataset_id=run.dataset_id,
                variant=run.variant,run_status=run.status,phase=run.phase,revision=run.revision,input=run.input,
                data_version=run.data_version,config=run.config,config_hash=run.config_hash,checkpoint_id=run.checkpoint_id,
                pending_input=run.pending_input,error_code=run.error_code,result_ref=run.result_ref,
                cancel_requested=bool(run.cancel_requested),messages=messages,conversation_history=conversation,
                result=report.content if report else None,
                business_result=report.content['business_result'] if report else None,
                action=report.content['action'] if report else ('clarify' if run.status=='WAITING_INPUT' else None),
                warnings=report.content['warnings'] if report else [],
                evidence_refs=[c.result.get('tool_call_id') for c in calls if c.result.get('tool_call_id')],
                usage=dict(requests_reserved=run.requests_consumed,tokens_occupied=run.tokens_occupied,
                    confirmed_total_tokens=sum(known) if len(known)==len(attempts) else None,
                    known_partial_tokens=sum(known),unknown_usage_attempts=len(attempts)-len(known),confirmed_cost=None,
                    basis='deterministic_no_model' if run.variant=='B0' else ('test_fixture_no_network' if run.config.get('budget_scope')=='test_fixture' else 'provider_reported_or_unknown')),
                attempts=[dict(attempt_id=a.attempt_id,step=a.step,status=a.status,source=a.source,provider=a.provider,
                    model_id=a.model_id,request_hash=a.request_hash,reserved_tokens=a.reserved_tokens,usage=a.usage,
                    request_id=a.response.get('request_id') if a.response else None,
                    finish_reason=a.response.get('finish_reason') if a.response else None,
                    error_code=a.error_code,created_at=a.created_at,finished_at=a.finished_at) for a in attempts],
                tool_calls=[dict(id=c.id,step=c.step,model_call_id=c.model_call_id,tool_name=c.tool_name,
                    arguments=c.arguments,result=c.result) for c in calls],
                reviews=[dict(step=r.step,kind=r.kind,**r.result) for r in reviews],
                created_at=run.created_at,started_at=run.started_at,updated_at=run.updated_at,ended_at=run.ended_at)

    def _conversation(self, session, parent_id):
        """Bounded previous turns; historical reads never resume or issue model calls."""
        turns=[]; seen=set()
        while parent_id and parent_id not in seen and len(turns)<8:
            seen.add(parent_id)
            parent=self._get(session,parent_id)
            report=session.get(Report,parent.result_ref) if parent.result_ref else None
            turns.append(dict(run_id=parent.run_id,question=parent.input.get('question',''),
                message=report.content['message'] if report else '',
                claims=report.content.get('claims',[]) if report else [],status=parent.status))
            parent_id=parent.input.get('conversation_parent_run_id')
        return list(reversed(turns))

    def list(self,limit=20,offset=0):
        self.metrics.require_database()
        with Session(self.metrics.engine) as session:
            rows=session.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).offset(offset))
            items=[dict(run_id=r.run_id,variant=r.variant,dataset_id=r.dataset_id,run_status=r.status,phase=r.phase,
                question=r.input.get('question'),created_at=r.created_at,result_ref=r.result_ref,error_code=r.error_code) for r in rows]
            return dict(items=items,total=session.scalar(select(func.count()).select_from(AnalysisRun)),limit=limit,offset=offset)

    def submit(self,run_id,request,kind):
        self._ready()
        payload=redact(request.model_dump(mode='json',exclude={'idempotency_key'}),self.settings.model_api_key.get_secret_value())
        request_hash=digest(dict(kind=kind,**payload))
        with Session(self.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE'))
            run=self._get(session,run_id)
            existing=session.scalar(select(RunSubmission).where(RunSubmission.run_id==run_id,
                RunSubmission.submission_key==request.idempotency_key))
            if existing:
                if existing.request_hash!=request_hash: raise AppError('IDEMPOTENCY_CONFLICT','Reply key has different input.',409)
                return self.get(run_id)
            if run.revision!=request.revision: raise AppError('REVISION_CONFLICT','Reload the current run before submitting.',409)
            if run.config_hash!=digest(self.runtime_config()): raise AppError('RUN_CONFIG_CHANGED','Create a new run for this configuration.',409)
            if kind=='input':
                if run.status!='WAITING_INPUT': raise AppError('RUN_STATE_CONFLICT','Run is not waiting for input.',409)
                if set(payload['answers'])!=set(run.pending_input['fields']):
                    raise AppError('INPUT_FIELDS_MISMATCH','Supply exactly the requested fields.',422)
                run.resume_payload=payload['answers']
            elif run.status not in ('QUEUED','INTERRUPTED'):
                raise AppError('RUN_STATE_CONFLICT','Only queued or interrupted runs may resume.',409)
            session.add(RunSubmission(id='sub_'+uuid4().hex,run_id=run_id,submission_key=request.idempotency_key,
                request_hash=request_hash,kind=kind,payload=payload,created_at=now()))
            run.status='QUEUED'; run.revision+=1; run.updated_at=now(); run.error_code=None
            session.commit()
        self.schedule(run_id)
        return self.get(run_id)

    def cancel(self,run_id):
        self.metrics.require_database()
        with Session(self.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE')); run=self._get(session,run_id)
            if run.status not in TERMINAL and not run.cancel_requested:
                run.cancel_requested=1; run.revision+=1; run.updated_at=now()
                if run.status!='RUNNING': run.status='CANCELLED'; run.ended_at=now()
                session.commit()
        return self.get(run_id)

    def rerun(self,run_id,request):
        old=self.get(run_id)
        if old['revision']!=request.revision: raise AppError('REVISION_CONFLICT','Reload the current run.',409)
        return self.create(CreateRun(**old['input'],idempotency_key=request.idempotency_key),parent_run_id=run_id)

    def boundary(self,run_id,phase):
        with Session(self.write_engine) as session:
            run=self._get(session,run_id)
            if run.cancel_requested: raise AppError('CANCELLED','Cancellation reached a safe boundary.',409)
            run.phase=phase; run.updated_at=now(); session.commit()

    def execute(self,run_id):
        config=None
        try:
            with Session(self.write_engine) as session:
                session.execute(text('BEGIN IMMEDIATE')); run=self._get(session,run_id)
                if run.status!='QUEUED': return
                if run.config_hash!=digest(self.runtime_config()): raise AppError('RUN_CONFIG_CHANGED','Configuration changed.',409)
                profile=self.metrics.profile(run.dataset_id)
                if any(profile[k]!=v for k,v in run.data_version.items()): raise AppError('RUN_DATA_CHANGED','Dataset version changed.',409)
                run.status='RUNNING'; run.started_at=run.started_at or now(); run.updated_at=now(); run.revision+=1
                config={'configurable':{'thread_id':run.thread_id},'recursion_limit':120,'callbacks':[]}
                initial=dict(run_id=run_id,dataset_id=run.dataset_id,variant=run.variant,step=0,repairs=0,results=[],
                    messages=[dict(role='system',content=SYSTEM_PROMPT),dict(role='user',content=json.dumps(dict(
                        **run.input,data_version=run.data_version,source_coverage={k:profile.get(k) for k in ('source_time_min','source_time_max')}),ensure_ascii=False))])
                history=self._conversation(session,run.input.get('conversation_parent_run_id'))
                if history:
                    # Context is bounded and explicitly untrusted; new numeric claims still require fresh tools.
                    initial['messages'].insert(1,dict(role='user',content='Previous conversation for context only. '
                        'Obtain fresh tool evidence for this turn; do not cite earlier tool IDs.\n'+json.dumps(history,ensure_ascii=False)))
                resume=run.resume_payload; session.commit()
            snapshot=self.graph.get_state(config)
            if snapshot.values:
                if snapshot.next:
                    argument=Command(resume=resume) if resume is not None and any(t.interrupts for t in snapshot.tasks) else None
                    self.graph.invoke(argument,config,durability='sync')
                # A completed checkpoint with a lagging business status is reconciled below.
            else:
                self.graph.invoke(initial,config,durability='sync')
            snapshot=self.graph.get_state(config)
            with Session(self.write_engine) as session:
                run=self._get(session,run_id)
                run.checkpoint_id=snapshot.config['configurable'].get('checkpoint_id')
                run.resume_payload=None; run.updated_at=now(); run.revision+=1
                pending=[i.value for t in snapshot.tasks for i in t.interrupts]
                if run.cancel_requested:
                    run.status='CANCELLED'; run.ended_at=now()
                elif pending:
                    run.status='WAITING_INPUT'; run.phase='clarify'; run.pending_input=pending[0]
                elif run.result_ref:
                    run.status='PASS'; run.phase='complete'; run.pending_input=None; run.ended_at=now(); run.error_code=None
                else:
                    run.status='FAIL'; run.error_code='MISSING_FINAL_REPORT'; run.ended_at=now()
                session.commit()
        except Exception as error:
            code=error.code if isinstance(error,AppError) else 'AGENT_INTERNAL_ERROR'
            with Session(self.write_engine) as session:
                run=self._get(session,run_id)
                run.status='CANCELLED' if code=='CANCELLED' else 'FAIL'; run.error_code=code
                run.updated_at=now(); run.ended_at=now(); run.revision+=1
                if config:
                    try:
                        snapshot=self.graph.get_state(config)
                        run.checkpoint_id=snapshot.config['configurable'].get('checkpoint_id') if snapshot.config else None
                    except Exception:
                        pass
                session.commit()
        finally:
            with self.guard:
                self.scheduled.discard(run_id)
                # A reply can be accepted just as the preceding worker publishes WAITING_INPUT.
                with Session(self.metrics.engine) as session:
                    queued=self._get(session,run_id).status=='QUEUED'
                if queued and self.pool:
                    self.scheduled.add(run_id); self.pool.submit(self.execute,run_id)

    def tool(self,run_id,step,position,call):
        self.boundary(run_id,'tools')
        if not isinstance(call,dict) or not isinstance(call.get('id'),str) or not 1<=len(call['id'])<=128:
            raise AppError('INVALID_TOOL_CALL','Invalid model tool identifier.',422)
        with Session(self.metrics.engine) as session:
            old=session.scalar(select(AgentToolCall).where(AgentToolCall.run_id==run_id,AgentToolCall.step==step,AgentToolCall.position==position))
            if old: return old.result
            count=session.scalar(select(func.count()).select_from(AgentToolCall).where(AgentToolCall.run_id==run_id))
            run=self._get(session,run_id); dataset_id=run.dataset_id; constraints=run.input.get('constraints'); variant=run.variant
        if count>=self.settings.model_max_tool_calls_per_run: raise AppError('TOOL_CALL_LIMIT','Tool budget exhausted.',409)
        name='invalid'; args={}
        try:
            function=call['function']; name=function['name']; args=json.loads(function['arguments'])
            if not isinstance(name,str) or len(name)>64 or not isinstance(args,dict): raise ValueError('shape')
            args=redact(args,self.settings.model_api_key.get_secret_value())
            if args.get('dataset_id',dataset_id)!=dataset_id: raise AppError('DATASET_SCOPE_VIOLATION','Tool dataset differs from run.',422)
            if variant=='B2' and constraints and name in ('query_metric_series','rank_entities'):
                for key in ('metric','date_from','date_to','country','stock_code'):
                    if args.get(key)!=constraints.get(key): raise AppError('TASK_CONDITION_MISMATCH','Tool arguments differ from explicit user conditions.',422)
            result=execute_tool(self.metrics,name,args)
        except (KeyError,TypeError,ValueError):
            result=dict(status='FAIL',error={'code':'INVALID_TOOL_ARGUMENTS'},tool=name)
        except AppError as error:
            result=dict(status='FAIL',error={'code':error.code},tool=name)
        with Session(self.write_engine) as session:
            session.add(AgentToolCall(id='at_'+uuid4().hex,run_id=run_id,step=step,position=position,model_call_id=call['id'],
                tool_name=name if isinstance(name,str) else 'invalid',arguments=args if isinstance(args,dict) else {},
                result=result,created_at=now()))
            session.commit()
        return result

    def review(self,run_id,step,kind,errors):
        with Session(self.write_engine) as session:
            old=session.scalar(select(AgentReview).where(AgentReview.run_id==run_id,AgentReview.step==step,AgentReview.kind==kind))
            if not old:
                session.add(AgentReview(id='rv_'+uuid4().hex,run_id=run_id,step=step,kind=kind,
                    result=dict(status='FAIL' if errors else 'PASS',errors=errors,reviewer='deterministic_program_not_human'),created_at=now()))
                session.commit()

    def finalize(self,state):
        from backend.app.reports import provenance, LIMITATIONS
        run_id=state['run_id']; decision=state['decision']; results=state.get('results',[])
        warnings=list(dict.fromkeys(w for result in results for w in result.get('warnings',[])))
        warnings.append('MODEL_COMMENTARY_REQUIRES_HUMAN_REVIEW')
        if self.provider.is_test: warnings.append('TEST_FIXTURE_PROVIDER_NOT_LIVE_MODEL')
        content=dict(run_id=run_id,variant=state['variant'],action=decision['action'],business_result=decision['action'],
            message=decision['message'],claims=state['claims'],warnings=warnings,
            evidence_refs=[r['tool_call_id'] for r in results if r.get('tool_call_id')],
            tool_statuses=[dict(tool=r.get('tool'),status=r.get('status'),period=r.get('period')) for r in results],
            validation='B2_BUSINESS_CHECKS' if state['variant']=='B2' else 'B1_REFERENCE_CHECKS',test_fixture=self.provider.is_test,
            provenance=provenance(self.metrics.profile(state['dataset_id'])),limitations=LIMITATIONS,
            parameters=self.run_input(run_id),report_schema='report-v1')
        with Session(self.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE')); run=self._get(session,run_id)
            old=session.scalar(select(Report).where(Report.run_id==run_id))
            if old:
                if digest(old.content)!=digest(content): raise AppError('REPORT_IDEMPOTENCY_CONFLICT','Existing finalized report differs.',409)
                run.result_ref=old.report_id
            else:
                report_id='rep_'+uuid4().hex
                session.add(Report(report_id=report_id,run_id=run_id,created_at=now(),content=content)); run.result_ref=report_id
            session.commit()
