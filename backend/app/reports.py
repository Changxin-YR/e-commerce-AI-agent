"""Deterministic reports and read-only, citation-checked historical exports."""
import json
import re
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Query, Request, Response
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.agent.budget import now
from backend.app.agent.contracts import Claim
from backend.app.agent.validation import resolve_claim
from backend.app.errors import AppError
from backend.app.metrics.contracts import METRICS, Identifier, SeriesParams, StrictModel
from backend.app.metrics.service import digest
from backend.app.metrics.tool_contracts import Period
from backend.app.metrics.tools import execute_tool
from backend.app.models import AgentToolCall, AnalysisRun, Report

LABELS = dict(positive_amount='正向交易行金额', cancellation_amount='取消类金额',
              net_amount='净交易金额', positive_invoice_count='有效发票数')
LIMITATIONS = ['真实公开历史交易数据，不代表当前店铺经营。',
               '金额包含符合口径的费用条目，不是纯商品 GMV、财务收入或实际退款。',
               '缺少采购成本、广告、库存和活动资料，无法判断利润、ROAS 或商业因果。',
               '重复候选保留；源时区未声明；不完整期间仅代表已观测交易。']


class CreateReport(StrictModel):
    dataset_id: Identifier
    idempotency_key: str = Field(min_length=1, max_length=128)
    query: SeriesParams
    baseline: Period | None = None


def provenance(profile):
    return {key: profile.get(key) for key in ('dataset_id', 'data_hash', 'transform_version',
            'metric_version', 'source_url', 'source_time_min', 'source_time_max', 'row_count')}


class ReportService:
    def __init__(self, metrics, engine):
        self.metrics, self.engine = metrics, engine

    def create(self, request, parent_run_id=None):
        started = now()
        profile = self.metrics.profile(request.dataset_id)
        body = request.model_dump(mode='json', exclude={'idempotency_key'})
        fingerprint = digest(dict(input=body, parent_run_id=parent_run_id, kind='B0'))
        with Session(self.metrics.engine) as session:
            existing = session.scalar(select(AnalysisRun).where(AnalysisRun.submission_key == request.idempotency_key))
            if existing:
                if existing.request_hash != fingerprint:
                    raise AppError('IDEMPOTENCY_CONFLICT', 'Submission key has different input.', 409)
                return self.get(existing.result_ref), False
        args = dict(dataset_id=request.dataset_id, **body['query'])
        results = [execute_tool(self.metrics, 'query_metric_series', dict(args, metric=metric)) for metric in METRICS]
        results += [execute_tool(self.metrics, 'rank_entities', dict(args, dimension=dimension, top_k=10))
                    for dimension in ('country', 'product')]
        if request.baseline:
            comparison = dict(dataset_id=request.dataset_id, metric=request.query.metric,
                baseline=body['baseline'], current={k: args[k] for k in ('date_from', 'date_to')},
                country=request.query.country, stock_code=request.query.stock_code)
            results.append(execute_tool(self.metrics, 'compare_periods', comparison))
            if request.query.metric != 'positive_invoice_count':
                results.append(execute_tool(self.metrics, 'decompose_change', dict(comparison, dimension='country', top_k=10)))
        claims = []
        for result in results:
            data = result['data']; name = result['tool']
            values = []
            if name == 'query_metric_series':
                values = [(f'points.{i}.value_exact', f"{p['month']} · {LABELS[data['metric']]}", p['value_exact'])
                          for i, p in enumerate(data['points'])]
            elif name == 'rank_entities':
                values = [(f'items.{i}.value_exact', f"{data['dimension']} · {p['entity_label']}", p['value_exact'])
                          for i, p in enumerate(data['items'])]
            elif name == 'compare_periods':
                values = [('baseline.value_exact', '基期', data['baseline']['value_exact']),
                          ('current.value_exact', '本期', data['current']['value_exact']), ('delta_exact', '期间差额', data['delta_exact'])]
            elif name == 'decompose_change':
                values = [(f'items.{i}.delta_exact', f"变化构成 · {p['entity_label']}", p['delta_exact'])
                          for i, p in enumerate(data['items'])]
                values.append(('other_delta_exact', '其他条目差额', data['other_delta_exact']))
            for path, label, value in values:
                if value is not None:
                    claim = resolve_claim(Claim(tool_call_id=result['tool_call_id'], field_path=path,
                        label=label[:200], value=value), results, request.dataset_id)
                    claim['unit'] = 'invoice_count' if data['metric'] == 'positive_invoice_count' else 'GBP'
                    claims.append(claim)
        stamp = now(); run_id = 'run_' + uuid4().hex; report_id = 'rep_' + uuid4().hex
        warnings = list(dict.fromkeys(w for result in results for w in result.get('warnings', [])))
        statuses = {r['status'] for r in results}
        outcome = 'PARTIAL_RESULT' if 'NO_DATA' in statuses and statuses != {'NO_DATA'} else (
            'PARTIAL_PERIOD' if 'PARTIAL_PERIOD' in statuses else results[0]['status'])
        content = dict(run_id=run_id, variant='B0', action='answer', business_result=outcome,
            message='按所选期间与筛选条件生成的确定性报表。全部关键数值来自保存的工具结果。',
            claims=claims, warnings=warnings, evidence_refs=[r['tool_call_id'] for r in results],
            tool_statuses=[dict(tool=r['tool'], status=r['status'], period=r['period']) for r in results],
            validation='DETERMINISTIC_TEMPLATE', test_fixture=False, provenance=provenance(profile),
            limitations=LIMITATIONS, parameters=body, report_schema='report-v1')
        with Session(self.engine) as session:
            session.execute(text('BEGIN IMMEDIATE'))
            existing = session.scalar(select(AnalysisRun).where(AnalysisRun.submission_key == request.idempotency_key))
            if existing:
                if existing.request_hash != fingerprint:
                    raise AppError('IDEMPOTENCY_CONFLICT', 'Submission key has different input.', 409)
                return self.get(existing.result_ref), False
            session.add(AnalysisRun(run_id=run_id, dataset_id=request.dataset_id, thread_id='thread_' + uuid4().hex,
                parent_run_id=parent_run_id, submission_key=request.idempotency_key, request_hash=fingerprint,
                variant='B0', status='PASS', phase='complete', revision=1, input=dict(body, question='确定性模板报表'),
                data_version={k: profile[k] for k in ('data_hash', 'transform_version', 'metric_version')},
                config=dict(provider='none', model_id=None, budget_scope='deterministic_no_model'),
                created_at=started, started_at=started, updated_at=stamp, ended_at=stamp, result_ref=report_id))
            session.flush()
            for i, result in enumerate(results):
                session.add(AgentToolCall(id='at_' + uuid4().hex, run_id=run_id, step=0, position=i,
                    model_call_id='B0_' + str(i), tool_name=result['tool'], arguments=result['arguments'],
                    result=result, created_at=stamp))
            session.add(Report(report_id=report_id, run_id=run_id, created_at=stamp, content=content))
            session.commit()
        return self.get(report_id), True

    def get(self, report_id):
        self.metrics.require_database()
        with Session(self.metrics.engine) as session:
            report = session.get(Report, report_id)
            if report is None:
                raise AppError('NOT_FOUND', 'Report not found.', 404)
            run = session.get(AnalysisRun, report.run_id)
            results = [c.result for c in session.scalars(select(AgentToolCall).where(
                AgentToolCall.run_id == run.run_id).order_by(AgentToolCall.step, AgentToolCall.position))]
            content = dict(report.content)
            for claim in content['claims']:
                resolved = resolve_claim(Claim(**{k: claim[k] for k in ('tool_call_id', 'field_path', 'label', 'value')}), results, run.dataset_id)
                if any(resolved[k] != claim[k] for k in ('value', 'snapshot_hash', 'metric_version', 'period', 'filters', 'dataset_snapshot_id')):
                    raise AppError('REPORT_EVIDENCE_MISMATCH', 'Stored report and evidence differ.', 409)
                if 'unit' in claim and claim['unit'] != resolved['unit']:
                    raise AppError('REPORT_EVIDENCE_MISMATCH', 'Stored report unit differs from evidence.', 409)
            # D6 reports remain immutable; missing presentation metadata is derived from saved run data only.
            content.setdefault('provenance', dict(dataset_id=run.dataset_id, **run.data_version))
            content.setdefault('parameters', run.input)
            content.setdefault('limitations', LIMITATIONS)
            content.setdefault('report_schema', 'report-v1')
            return dict(report_id=report_id, run_id=run.run_id, dataset_id=run.dataset_id,
                created_at=report.created_at, content=content, content_sha256=digest(report.content),
                evidence=results, run_status=run.status)

    def list(self, limit, offset):
        self.metrics.require_database()
        with Session(self.metrics.engine) as session:
            rows = session.scalars(select(Report).order_by(Report.created_at.desc(), Report.report_id).limit(limit).offset(offset))
            return dict(items=[dict(report_id=r.report_id, run_id=r.run_id, created_at=r.created_at,
                variant=r.content['variant'], test_fixture=r.content.get('test_fixture', False),
                business_result=r.content['business_result']) for r in rows],
                total=session.scalar(select(func.count()).select_from(Report)), limit=limit, offset=offset)

    def rerun(self, run_id, request):
        with Session(self.metrics.engine) as session:
            run = session.get(AnalysisRun, run_id)
            if run.revision != request.revision:
                raise AppError('REVISION_CONFLICT', 'Reload the current run.', 409)
            payload = {k: run.input[k] for k in ('dataset_id', 'query', 'baseline')}
        return self.create(CreateReport(**payload, idempotency_key=request.idempotency_key), parent_run_id=run_id)


def markdown(report):
    def safe(value):
        value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return re.sub(r'([\\`*_{}\[\]()#+.!|~-])', r'\\\1', value).replace('\r', ' ').replace('\n', ' ')
    c = report['content']
    lines = ['# 历史交易分析报告', '', '报告：' + safe(report['report_id']),
             '方案：' + c['variant'], '生成时间：' + report['created_at'],
             '模型来源：' + ('测试夹具，非真实模型' if c['test_fixture'] else ('无模型' if c['variant'] == 'B0' else '实际提供方，详见任务用量')), '',
             safe(c['message']), '', '## 精确数值与引用', '', '| 指标 | 精确值 | 引用 |', '|---|---|---|']
    for claim in c['claims']:
        lines.append('| ' + ' | '.join(safe(x) for x in (claim['label'], str(claim['value']) + ' ' + claim.get('unit', ''),
                     claim['tool_call_id'] + ':' + claim['field_path'])) + ' |')
    for heading, value in [('数据来源与版本', c['provenance']), ('参数与过滤器', c['parameters'])]:
        lines += ['', '## ' + heading, '', safe(json.dumps(value, ensure_ascii=False, sort_keys=True))]
    lines += ['', '## 证据状态', ''] + [safe(json.dumps(x, ensure_ascii=False)) for x in c['tool_statuses']]
    lines += ['', '## 限制与警告', ''] + ['- ' + safe(w) for w in c['limitations'] + c['warnings']]
    lines += ['', '保存内容 SHA-256：' + report['content_sha256'], '']
    return '\n'.join(lines)


router = APIRouter(prefix='/api/v1/reports', tags=['reports'])


@router.post('', status_code=201)
def create_report(body: CreateReport, request: Request, response: Response):
    result, created = request.app.state.report_service.create(body)
    response.status_code = 201 if created else 200
    return result


@router.get('')
def list_reports(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0, le=10000)] = 0):
    return request.app.state.report_service.list(limit, offset)


@router.get('/{report_id}')
def get_report(report_id: str, request: Request):
    return request.app.state.report_service.get(report_id)


@router.get('/{report_id}/export')
def export_report(report_id: str, request: Request, format: Literal['json', 'markdown'] = 'json'):
    report = request.app.state.report_service.get(report_id)
    content = json.dumps(report, ensure_ascii=False, indent=2) if format == 'json' else markdown(report)
    # Use an internal hash for the filename; never reflect route input in response headers.
    filename = 'report-' + digest(report_id)[:24] + ('.json' if format == 'json' else '.md')
    return Response(content, media_type='application/json' if format == 'json' else 'text/plain',
        headers={'Content-Disposition': f'attachment; filename="{filename}"', 'X-Content-Type-Options': 'nosniff'})
