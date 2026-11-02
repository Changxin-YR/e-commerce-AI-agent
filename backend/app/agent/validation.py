"""Common reference safety and separate B2 business validation, using Decimal."""
from decimal import Decimal, InvalidOperation
import re
from backend.app.errors import AppError
from backend.app.metrics.service import digest


def resolve_claim(claim, results, dataset_id):
    envelope=next((v for v in results if v.get('tool_call_id')==claim.tool_call_id), None)
    if not envelope or envelope.get('dataset_id')!=dataset_id or envelope.get('error'):
        raise AppError('INVALID_EVIDENCE_REF','Report references unavailable tool evidence.',422)
    value=envelope['data']
    try:
        for part in claim.field_path.split('.'):
            value=value[int(part)] if isinstance(value,list) and part.isdigit() else value[part]
    except (KeyError,IndexError,TypeError,ValueError):
        raise AppError('INVALID_EVIDENCE_REF','Report field path cannot be resolved.',422) from None
    # Only numeric claims; arbitrary product descriptions are never promoted into instructions.
    if type(value) is not int and (not isinstance(value,str) or not re.fullmatch(r'-?\d+(?:\.\d+)?',value)):
        raise AppError('NON_NUMERIC_EVIDENCE','The referenced field is not a numeric result.',422)
    evidence=envelope['evidence']
    return dict(claim_id='claim_'+digest(dict(tool=claim.tool_call_id,path=claim.field_path))[:24],label=claim.label,
        value=value,model_value=claim.value,tool_call_id=claim.tool_call_id,field_path=claim.field_path,
        dataset_snapshot_id=dataset_id,snapshot_hash=evidence['snapshot_hash'],metric_version=evidence['metric_version'],
        period=evidence['period'],filters=evidence['filters'])


def validate_b2_tools(results, constraints=None):
    errors=[]
    comparisons={}
    for item in results:
        if item.get('error'):
            continue
        data=item['data']; name=item['tool']; args=item['arguments']
        if constraints and name in ('query_metric_series','rank_entities'):
            for key in ('metric','date_from','date_to','country','stock_code'):
                if args.get(key)!=constraints.get(key):
                    errors.append('TASK_CONDITION_MISMATCH:'+key)
        try:
            if name in ('compare_periods','decompose_change') and data.get('delta_exact') is not None:
                delta=Decimal(data['current']['value_exact'])-Decimal(data['baseline']['value_exact'])
                if delta!=Decimal(data['delta_exact']): errors.append('PERIOD_DELTA_MISMATCH')
                key=str((args['metric'],args['baseline'],args['current'],args.get('country'),args.get('stock_code')))
                values=(data['baseline']['value_exact'],data['current']['value_exact'],data['delta_exact'])
                if key in comparisons and comparisons[key]!=values: errors.append('CROSS_TOOL_MISMATCH')
                comparisons[key]=values
                if name=='decompose_change':
                    total=sum((Decimal(x['delta_exact']) for x in data['items']),Decimal(0))+Decimal(data['other_delta_exact'])
                    if total!=delta or Decimal(data['reconciliation_exact'])!=0: errors.append('DECOMPOSITION_MISMATCH')
            if name=='rank_entities' and data.get('group_total_exact') is not None:
                total=sum((Decimal(x['value_exact']) for x in data['items']),Decimal(0))+Decimal(data['other_exact'])
                if total!=Decimal(data['group_total_exact']): errors.append('RANK_TOTAL_MISMATCH')
                if data['metric']!='positive_invoice_count' and total!=Decimal(data['total_exact']): errors.append('RANK_RECONCILIATION_MISMATCH')
        except (KeyError,TypeError,InvalidOperation):
            errors.append('INVALID_TOOL_NUMBERS')
    return list(dict.fromkeys(errors))


def validate_b2_answer(decision, claims, results, constraints=None):
    errors=validate_b2_tools(results,constraints)
    if any(str(c['value'])!=str(c['model_value']) for c in claims):
        errors.append('CLAIM_VALUE_MISMATCH')
    # All key figures belong in cited claims; free prose is explicitly unverified commentary.
    prose=' '.join([decision.message]+[c['label'] for c in claims])
    if re.search(r'\d|[零一二三四五六七八九十百千万亿两〇]+(?:英镑|元|GBP|%|笔|张)',prose):
        errors.append('UNCITED_NUMBER_IN_TEXT')
    if re.search(r'导致|因为|证明|caused by|because|proves',decision.message,re.I):
        errors.append('UNSUPPORTED_CAUSAL_ASSERTION')
    if decision.action=='answer' and not results: errors.append('MISSING_TOOL_EVIDENCE')
    if decision.action=='answer' and not claims and any(x.get('evidence',{}).get('exact_values') for x in results):
        errors.append('MISSING_NUMERIC_CLAIMS')
    if constraints and decision.action=='answer' and not any(not x.get('error') and x['tool'] in ('query_metric_series','rank_entities') for x in results):
        errors.append('TASK_CONDITION_NOT_COVERED')
    if decision.action=='answer' and any(c.get('tool_call_id') is None for c in claims): errors.append('MISSING_CITATION')
    return list(dict.fromkeys(errors))
