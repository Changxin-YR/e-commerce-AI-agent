"""D5 test_fixture checks. Real UCI acceptance is scripts/verify_tools.py."""
from decimal import Decimal
import sqlite3

import pytest

from backend.app.errors import AppError
from backend.app.imports.source import sha256
from backend.app.metrics.tools import ARGUMENTS, execute_tool
from test_metrics import api, dataset, ORIGIN

PERIOD = dict(date_from="2011-09-01", date_to="2011-10-01")
CURRENT = dict(date_from="2011-10-01", date_to="2011-11-01")


def arguments(name, dataset_id):
    result = dict(dataset_id=dataset_id)
    if name in {"query_metric_series", "rank_entities"}:
        result.update(metric="net_amount", **PERIOD)
    if name in {"compare_periods", "decompose_change"}:
        result.update(metric="net_amount", baseline=PERIOD, current=CURRENT)
    if name in {"rank_entities", "decompose_change"}:
        result["dimension"] = "country"
    return result


@pytest.mark.parametrize("name", ARGUMENTS)
def test_all_tools_http_evidence_readonly_and_reject_unknown(api, dataset, name):
    client, app, dataset_id = api
    args = arguments(name, dataset_id)
    before = sha256(dataset[0].database_path)
    response = client.post("/api/v1/tools/"+name, json=args, headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == execute_tool(app.state.metric_service, name, args)
    assert body["result"] == body["data"]
    assert body["snapshot_hash"] == body["evidence"]["snapshot_hash"]
    assert len(body["snapshot_hash"]) == 64
    assert body["error"] is None
    assert body["tool_call_id"].startswith("tc_")
    assert client.post("/api/v1/tools/"+name, json={**args,"sql":"SELECT 1"}, headers=ORIGIN).status_code == 422
    assert client.post("/api/v1/tools/"+name, json={**args,"dataset_id":"missing"}, headers=ORIGIN).status_code == 404
    assert client.post("/api/v1/tools/"+name, json=args).status_code == 403
    assert sha256(dataset[0].database_path) == before


def test_tools_math_and_quality(api):
    _, app, d = api
    invoke = lambda name, **kw: execute_tool(app.state.metric_service,name,{**arguments(name,d),**kw})["data"]
    quality = invoke("get_quality_summary", **PERIOD)
    assert quality["raw_row_count"] == 9
    assert sum(quality["primary_class_counts"].values()) == 9
    assert quality["primary_class_counts"] == {"INVALID":0,"POSITIVE":4,"CANCELLATION":1,"EXCLUDED_OTHER":4}
    assert quality["quality_flags"]["DUPLICATE_CANDIDATE_AFTER_FIRST"] == 1
    assert quality["quality_flags"]["MISSING_CUSTOMER_ID"] == 9
    rank = invoke("rank_entities",top_k=1)
    assert rank["items"][0]["entity"] == "France"
    assert rank["items"][0]["value_exact"] == "2.000"
    assert rank["other_exact"] == "1.009"
    assert rank["total_exact"] == "3.009"
    compare = invoke("compare_periods")
    assert compare["delta_exact"] == "-0.009"
    assert compare["growth_percent"] == "-0.299103"
    parts = invoke("decompose_change",top_k=1)
    assert parts["items"][0]["entity"] == "France"
    assert parts["items"][0]["delta_exact"] == "-2.000"
    assert parts["other_delta_exact"] == "1.991"
    assert parts["sum_delta_exact"] == "-0.009" and parts["reconciled"]
    assert sum(Decimal(item["delta_exact"]) for item in parts["items"])+Decimal(parts["other_delta_exact"]) == Decimal(compare["delta_exact"])
    full = invoke("compare_periods",metric="positive_invoice_count",current=dict(date_from="2011-09-01",date_to="2011-11-01"))
    assert full["current"]["value_exact"] == "3"  # Repeated invoice 1 is counted once across months.


def test_ties_order_truncation_missing_dimension_and_nonadditivity(api, dataset):
    _,app,d=api
    with sqlite3.connect(dataset[0].database_path) as db:
        db.execute("UPDATE transaction_rows SET line_amount_milli_gbp=1010 WHERE invoice_no='F'")
    args = arguments("rank_entities",d) | dict(metric="positive_amount",top_k=1)
    result = execute_tool(app.state.metric_service,"rank_entities",args)["data"]
    assert result["items"][0]["entity"] == "France"
    result = execute_tool(app.state.metric_service,"rank_entities",args | dict(top_k=2))["data"]
    assert [row["rank"] for row in result["items"]] == [1,1]
    assert result["other_exact"] == "0.000"
    with sqlite3.connect(dataset[0].database_path) as db:
        db.execute("UPDATE transaction_rows SET country=NULL WHERE invoice_no='F'")
        db.execute("UPDATE transaction_rows SET stock_code='second' WHERE invoice_no='1' AND source_row_num=4")
    missing = execute_tool(app.state.metric_service,"rank_entities",args | dict(top_k=2))["data"]
    assert [i["entity"] for i in missing["items"]] == ["UK",None]
    assert missing["items"][1]["entity_label"] == "未知"
    count = execute_tool(app.state.metric_service,"rank_entities",args | dict(metric="positive_invoice_count", dimension="product",top_k=50))["data"]
    assert count["total_exact"] == "3" and count["group_total_exact"] == "4"
    assert "DISTINCT_INVOICES_ACROSS_ENTITIES_ARE_NOT_ADDITIVE" in count["warnings"]
    with pytest.raises(AppError,match="NON_ADDITIVE_METRIC"):
        execute_tool(app.state.metric_service,"decompose_change",arguments("decompose_change",d) | dict(metric="positive_invoice_count"))


@pytest.mark.parametrize("name", ["get_quality_summary","query_metric_series","rank_entities","compare_periods","decompose_change","inspect_transactions"])
def test_no_data_partial_and_empty_are_distinct(api,name):
    _,app,d=api
    args=arguments(name,d)
    for period,status in [(dict(date_from="2012-01-01",date_to="2012-02-01"),"NO_DATA"),
                          (dict(date_from="2011-12-01",date_to="2012-01-01"),"PARTIAL_PERIOD")]:
        request=args | (dict(current=period) if name in {"compare_periods","decompose_change"} else period)
        body=execute_tool(app.state.metric_service,name,request)["data"]
        assert body["status"] == status
        if name in {"compare_periods","decompose_change"} and status == "NO_DATA":
            assert body["delta_exact"] is None
        if name == "rank_entities" and status == "NO_DATA":
            assert body["total_exact"] is None and body["items"] == []
    empty=execute_tool(app.state.metric_service,name,args | dict(country="' OR 1=1 --"))["data"]
    assert empty["status"] == "EMPTY_RESULT"


def test_zero_negative_baseline_and_zero_change(api):
    _,app,d=api
    args=arguments("compare_periods",d) | dict(country="France",baseline=CURRENT,current=PERIOD)
    zero=execute_tool(app.state.metric_service,"compare_periods",args)["data"]
    assert zero["delta_exact"] == "2.000" and zero["growth_percent"] is None and zero["growth_reason"] == "ZERO_BASELINE"
    negative=execute_tool(app.state.metric_service,"compare_periods",arguments("compare_periods",d) | dict(
        baseline=dict(date_from="2011-09-02",date_to="2011-09-03")))["data"]
    assert negative["baseline"]["value_exact"] == "-0.001" and negative["growth_reason"] == "NEGATIVE_BASELINE"
    equal=execute_tool(app.state.metric_service,"decompose_change",arguments("decompose_change",d) | dict(current=PERIOD))["data"]
    assert equal["sum_delta_exact"] == "0.000" and equal["contribution_reason"] == "ZERO_TOTAL_CHANGE"
    assert all(item["contribution_percent"] is None for item in equal["items"])


def test_inspection_limit_filters_and_no_customers(api):
    _,app,d=api
    result=execute_tool(app.state.metric_service,"inspect_transactions",dict(dataset_id=d,limit=2,order="source_row_desc"))["data"]
    assert result["total_matches"] == 12 and result["returned_count"] == 2 and result["truncated"]
    assert [r["source_row_num"] for r in result["items"]] == [13,12]
    assert "customer_id" not in result["items"][0]
    excluded=execute_tool(app.state.metric_service,"inspect_transactions",dict(dataset_id=d,primary_class="EXCLUDED_OTHER"))["data"]
    assert excluded["total_matches"] == 4
    assert all(r["primary_class"] == "EXCLUDED_OTHER" for r in excluded["items"])


@pytest.mark.parametrize("name,patch", [
    ("inspect_transactions",{"limit":51}),("inspect_transactions",{"limit":True}),
    ("inspect_transactions",{"limit":"2"}),("inspect_transactions",{"limit":1.0}),
    ("inspect_transactions",{"order":"invoice_no;DROP TABLE"}),
    ("inspect_transactions",{"primary_class":"ANY"}),
    ("rank_entities",{"top_k":0}),("rank_entities",{"top_k":51}),("rank_entities",{"top_k":False}),
    ("rank_entities",{"dimension":"customer"}),("rank_entities",{"order":"random"}),
    ("rank_entities",{"metric":"profit"}),("compare_periods",{"metric":"profit"}),
    ("get_quality_summary",{"date_from":"2011-09-01"}),
    ("get_quality_summary",{"date_from":"2011-10-01","date_to":"2011-09-01"}),
    ("inspect_transactions",{"date_from":"2000-01-01","date_to":"2012-01-01"}),
    ("decompose_change",{"baseline":{"date_from":"2011-09-01","date_to":"2011-10-01","sql":"x"}}),
    ("rank_entities",{"country":"\n"}),
])
def test_invalid_parameters(api,name,patch):
    client,_,d=api
    result=client.post("/api/v1/tools/"+name,json=arguments(name,d)|patch,headers=ORIGIN)
    assert result.status_code == 422
    assert result.json()["error"]["code"] in {"VALIDATION_ERROR","UNSUPPORTED_METRIC"}


def test_registry_schema_and_no_arbitrary_tool(api):
    client,_,d=api
    schemas=client.get("/api/v1/tools").json()["tools"]
    assert len(schemas) == 8
    assert all(item["function"]["parameters"]["additionalProperties"] is False for item in schemas)
    assert client.post("/api/v1/tools/shell",json={"command":"echo nope"},headers=ORIGIN).json()["error"]["code"] == "UNSUPPORTED_TOOL"
    assert client.post("/api/v1/tools/rank_entities?sql=x",json=arguments("rank_entities",d),headers=ORIGIN).status_code == 422
