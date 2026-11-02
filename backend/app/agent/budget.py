"""Reserve before send; unknown outcomes retain their entire token reservation."""
from datetime import datetime, timezone
import json
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from backend.app.errors import AppError
from backend.app.metrics.service import digest
from backend.app.models import AnalysisRun, ModelAttempt, ModelBudget
from .provider import ProviderFailure, authorization_error


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]') if secret else value
    if isinstance(value, dict):
        return {k: redact(v,secret) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v,secret) for v in value]
    return value


def valid_usage(usage):
    if not isinstance(usage,dict):
        return None
    keys=('prompt_tokens','completion_tokens','total_tokens')
    if any(type(usage.get(k)) is not int or usage[k]<0 for k in keys):
        return None
    if usage['prompt_tokens']+usage['completion_tokens'] != usage['total_tokens']:
        return None
    return {k:usage[k] for k in keys}


class BudgetGateway:
    def __init__(self, service):
        self.service = service

    def call(self, run_id, step, messages, schemas, source):
        svc=self.service; cfg=svc.runtime_config(); provider=svc.provider
        if not provider.is_test:
            error=authorization_error(svc.settings)
            if error:
                raise AppError(error, 'Model authorization, credentials and positive budgets are required.', 409)
        # UTF-8 bytes plus fixed framing overhead is a deliberately conservative preflight bound.
        request=dict(messages=messages, tools=schemas, model=provider.model_id, max_tokens=cfg['output_tokens'])
        if len(json.dumps(request,ensure_ascii=False).encode('utf-8'))+2048+cfg['output_tokens']>cfg['tokens_per_request']:
            raise AppError('MODEL_CONTEXT_LIMIT', 'The bounded model context is full.', 409)
        request_hash=digest(request)
        with Session(svc.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE'))
            run=session.get(AnalysisRun,run_id)
            if run.cancel_requested:
                raise AppError('CANCELLED','Run was cancelled.',409)
            if run.config_hash != digest(cfg):
                raise AppError('RUN_CONFIG_CHANGED','Create a new run for this configuration.',409)
            previous=session.scalars(select(ModelAttempt).where(ModelAttempt.run_id==run_id,
                ModelAttempt.step==step).order_by(ModelAttempt.created_at.desc())).first()
            if previous and previous.status=='SUCCEEDED':
                if previous.request_hash!=request_hash:
                    raise AppError('ATTEMPT_REPLAY_CONFLICT','Stored model input does not match.',409)
                return previous.response
            ledger=session.get(ModelBudget,cfg['budget_scope'])
            if ledger is None:
                ledger=ModelBudget(scope=cfg['budget_scope'],requests_consumed=0,tokens_occupied=0)
                session.add(ledger)
            reserve=cfg['tokens_per_request']
            if (run.requests_consumed>=cfg['requests_per_run'] or ledger.requests_consumed>=cfg['total_requests']
                or run.tokens_occupied+reserve>cfg['tokens_per_run'] or ledger.tokens_occupied+reserve>cfg['total_tokens']):
                raise AppError('MODEL_BUDGET_EXHAUSTED','Model request or token budget is exhausted.',409)
            attempt=ModelAttempt(attempt_id='ma_'+uuid4().hex,run_id=run_id,step=step,status='RESERVED',source=source,
                request_hash=request_hash,provider=provider.name,model_id=provider.model_id,reserved_tokens=reserve,
                created_at=now())
            session.add(attempt)
            run.requests_consumed+=1; run.tokens_occupied+=reserve
            ledger.requests_consumed+=1; ledger.tokens_occupied+=reserve
            attempt_id=attempt.attempt_id
            session.commit()
        with Session(svc.write_engine) as session:
            attempt=session.get(ModelAttempt,attempt_id); attempt.status='SENT'; session.commit()
        try:
            reply=provider.complete(messages,schemas,cfg['output_tokens']).as_dict()
            if not isinstance(reply.get('message'),dict) or reply['message'].get('role')!='assistant':
                raise ProviderFailure('MODEL_INVALID_RESPONSE')
            reply=redact(reply,svc.settings.model_api_key.get_secret_value())
        except Exception as error:
            code=error.code if isinstance(error,(ProviderFailure,AppError)) else 'MODEL_OUTCOME_UNKNOWN'
            with Session(svc.write_engine) as session:
                attempt=session.get(ModelAttempt,attempt_id)
                attempt.status='UNKNOWN_OUTCOME'; attempt.error_code=code; attempt.finished_at=now()
                session.commit()
            raise AppError(code,'Model response was unavailable; usage may be unknown.',502) from None
        usage=valid_usage(reply.get('usage')); reply['usage']=usage
        with Session(svc.write_engine) as session:
            session.execute(text('BEGIN IMMEDIATE'))
            attempt=session.get(ModelAttempt,attempt_id); run=session.get(AnalysisRun,run_id)
            ledger=session.get(ModelBudget,cfg['budget_scope'])
            attempt.status='SUCCEEDED'; attempt.response=reply; attempt.usage=usage; attempt.finished_at=now()
            if usage is not None:
                adjustment=usage['total_tokens']-attempt.reserved_tokens
                run.tokens_occupied+=adjustment; ledger.tokens_occupied+=adjustment
            session.commit()
        if usage and usage['total_tokens']>reserve:
            raise AppError('PROVIDER_USAGE_EXCEEDED_RESERVATION','Provider reported usage exceeding the configured cap.',409)
        return reply
