"""D5 real HTTP acceptance with independent SQL classification and Decimal values.

Never imports production calculations to generate expected values. No models.
Requires an existing real snapshot, preserves output directories and stops its server.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
PERIOD = dict(date_from="2011-09-01",date_to="2011-10-01")
CURRENT = dict(date_from="2011-10-01",date_to="2011-11-01")
METRICS = ("positive_amount","cancellation_amount","net_amount","positive_invoice_count")


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def number(value,metric):
    return str(value) if metric == "positive_invoice_count" else format(Decimal(value)/1000,".3f")


def percent(n,d):
    return None if not d else format((Decimal(n)*100/Decimal(d)).quantize(Decimal(".000001"),rounding=ROUND_HALF_UP),".6f")


def reference(db,dataset,period,metric,dimension=None,country=None):
    # Reclassify by original normalized inputs rather than using primary_class/line_amount.
    pos="lower(substr(invoice_no,1,1))!='c' AND quantity>0 AND unit_price_milli_gbp>0"
    can="lower(substr(invoice_no,1,1))='c' AND quantity<0 AND unit_price_milli_gbp>0"
    expressions={"positive_amount":f"COALESCE(SUM(CASE WHEN {pos} THEN quantity*unit_price_milli_gbp ELSE 0 END),0)",
        "cancellation_amount":f"COALESCE(SUM(CASE WHEN {can} THEN -quantity*unit_price_milli_gbp ELSE 0 END),0)",
        "net_amount":f"COALESCE(SUM(CASE WHEN ({pos}) OR ({can}) THEN quantity*unit_price_milli_gbp ELSE 0 END),0)",
        "positive_invoice_count":f"COUNT(DISTINCT CASE WHEN {pos} THEN invoice_no END)"}
    where=" FROM transaction_rows WHERE dataset_id=? AND invoice_date_source>=? AND invoice_date_source<?"
    params=[dataset,period["date_from"]+" 00:00:00",period["date_to"]+" 00:00:00"]
    if country is not None:
        where+=" AND country=?"
        params.append(country)
    if dimension:
        column={"product":"stock_code","country":"country"}[dimension]
        inclusion=pos if metric in {"positive_amount","positive_invoice_count"} else can if metric == "cancellation_amount" else f"({pos}) OR ({can})"
        return dict(db.execute("SELECT "+column+","+expressions[metric]+where+" AND ("+inclusion+") GROUP BY "+column,params))
    return db.execute("SELECT "+expressions[metric]+where,params).fetchone()[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    args.database,args.output=args.database.resolve(),args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(scope="D5_real_data_development_not_academic_experiment",started_at=datetime.now(timezone.utc).isoformat(),checks=[],calls=[],model_calls=0)
    process=log=client=db=None
    def check(name,actual,expected):
        passed=actual==expected
        report["checks"].append(dict(name=name,actual=actual,expected=expected,passed=passed))
        if not passed:
            raise AssertionError(name)
    try:
        if not args.database.is_file():
            raise FileNotFoundError("Existing imported database required")
        manifest=json.loads((ROOT/"data/manifest.json").read_text("utf-8"))
        report["source_hashes"]={}
        for kind,info in manifest["files"].items():
            value=sha(ROOT/info["path"])
            check(kind+"_sha",value,info["sha256"])
            report["source_hashes"][kind]=value
        db=sqlite3.connect(args.database.as_uri()+"?mode=ro",uri=True)
        found=db.execute("SELECT dataset_id,row_count FROM dataset_snapshots WHERE status='READY' AND workbook_sha256=?",(manifest["files"]["xlsx"]["sha256"],)).fetchall()
        check("single_real_snapshot",len(found),1)
        dataset,rows=found[0]
        check("official_rows",rows,541909)
        report["dataset_id"]=dataset
        report["database_before"]=sha(args.database)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
        env=os.environ.copy()
        env.update(DATABASE_URL="sqlite:///"+args.database.as_posix(),IMPORT_CACHE_DIR=str(args.output/"uploads"),
                   APP_PORT=str(port),PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1")
        argv=[sys.executable,"-m","uvicorn","backend.app.main:app","--host","127.0.0.1","--port",str(port)]
        log=(args.output/"server.log").open("wb")
        process=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        report["server"]=dict(argv=argv,pid=process.pid)
        client=httpx.Client(base_url=f"http://127.0.0.1:{port}",timeout=90,trust_env=False,headers={"Origin":"http://127.0.0.1:5173"})
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                if client.get("/healthz").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.15)
        else:
            raise RuntimeError("Owned server failed to start")
        schema=client.get("/api/v1/tools").json()["tools"]
        check("eight_tools",len(schema),8)
        (args.output/"tool-schemas.json").write_text(json.dumps(schema,ensure_ascii=False,indent=2),"utf-8")
        def call(name,params,expected_status=200):
            started=time.monotonic()
            response=client.post("/api/v1/tools/"+name,json=dict(dataset_id=dataset,**params))
            body=response.json()
            report["calls"].append(dict(tool=name,parameters=params,http=response.status_code,seconds=round(time.monotonic()-started,4),response=body))
            check(name+"_http_"+str(len(report["calls"])),response.status_code,expected_status)
            if expected_status==200:
                check(name+"_snapshot",body["snapshot_hash"],manifest["files"]["xlsx"]["sha256"])
                check(name+"_evidence",body["tool_call_id"],body["evidence"]["tool_call_id"])
                return body["data"]
            return body
        profile=call("get_dataset_profile",{})
        check("profile_rows",profile["row_count"],rows)
        defs=call("get_metric_definitions",{})
        check("four_definitions",len(defs["definitions"]),4)
        quality=call("get_quality_summary",{})
        check("classes",quality["primary_class_counts"],dict(db.execute("SELECT primary_class,COUNT(*) FROM transaction_rows WHERE dataset_id=? GROUP BY 1",(dataset,))) | {"INVALID":0})
        check("quality_flags",quality["quality_flags"],dict(db.execute("SELECT issue_code,COUNT(*) FROM quality_issues WHERE dataset_id=? GROUP BY 1",(dataset,))))
        scoped=call("get_quality_summary",PERIOD | dict(country="United Kingdom"))
        check("quality_period_count",scoped["matched_row_count"],db.execute("SELECT COUNT(*) FROM transaction_rows WHERE dataset_id=? AND invoice_date_source>=? AND invoice_date_source<? AND country=?",(dataset,"2011-09-01 00:00:00","2011-10-01 00:00:00","United Kingdom")).fetchone()[0])
        for metric in METRICS:
            before=reference(db,dataset,PERIOD,metric)
            after=reference(db,dataset,CURRENT,metric)
            series=call("query_metric_series",dict(metric=metric,date_from=PERIOD["date_from"],date_to=CURRENT["date_to"]))
            check(metric+"_series",[r["value_exact"] for r in series["points"]],[number(before,metric),number(after,metric)])
            comparison=call("compare_periods",dict(metric=metric,baseline=PERIOD,current=CURRENT))
            check(metric+"_baseline",comparison["baseline"]["value_exact"],number(before,metric))
            check(metric+"_current",comparison["current"]["value_exact"],number(after,metric))
            check(metric+"_delta",comparison["delta_exact"],number(after-before,metric))
            check(metric+"_growth",comparison["growth_percent"],percent(after-before,before))
            for dimension in ("country","product"):
                groups=reference(db,dataset,PERIOD,metric,dimension)
                rank=call("rank_entities",dict(metric=metric,dimension=dimension,**PERIOD,top_k=5))
                ordered=sorted(groups,key=lambda key:(-groups[key],key is None,key or ""))
                check(metric+dimension+"_rank_keys",[r["entity"] for r in rank["items"]],ordered[:5])
                check(metric+dimension+"_rank_values",[r["value_exact"] for r in rank["items"]],[number(groups[key],metric) for key in ordered[:5]])
                check(metric+dimension+"_other",rank["other_exact"],number(sum(groups[key] for key in ordered[5:]),metric))
                check(metric+dimension+"_total",rank["total_exact"],number(before,metric))
                if metric=="positive_invoice_count":
                    continue
                current=reference(db,dataset,CURRENT,metric,dimension)
                changes={k:current.get(k,0)-groups.get(k,0) for k in groups.keys() | current.keys()}
                ordered=sorted(changes,key=lambda key:(-abs(changes[key]),key is None,key or ""))
                parts=call("decompose_change",dict(metric=metric,dimension=dimension,baseline=PERIOD,current=CURRENT,top_k=5))
                check(metric+dimension+"_decompose_keys",[r["entity"] for r in parts["items"]],ordered[:5])
                check(metric+dimension+"_decompose_values",[r["delta_exact"] for r in parts["items"]],[number(changes[key],metric) for key in ordered[:5]])
                check(metric+dimension+"_decompose_other",parts["other_delta_exact"],number(sum(changes[key] for key in ordered[5:]),metric))
                check(metric+dimension+"_reconciles",parts["sum_delta_exact"],number(after-before,metric))
                check(metric+dimension+"_contributions",[r["contribution_percent"] for r in parts["items"]],[percent(changes[key],after-before) for key in ordered[:5]])
        inspection=call("inspect_transactions",dict(**PERIOD,limit=50))
        expected=db.execute("SELECT source_row_num,unit_price_raw,quantity*unit_price_milli_gbp FROM transaction_rows WHERE dataset_id=? AND invoice_date_source>=? AND invoice_date_source<? ORDER BY source_row_num LIMIT 50",(dataset,"2011-09-01 00:00:00","2011-10-01 00:00:00")).fetchall()
        check("inspection_50_rows",len(inspection["items"]),50)
        check("inspection_exact_source",[[r["source_row_num"],r["unit_price_raw"],r["line_amount_exact"]] for r in inspection["items"]],[[r[0],r[1],number(r[2],"net_amount")] for r in expected])
        cases={"get_dataset_profile":{},"get_metric_definitions":{},"get_quality_summary":{},
            "query_metric_series":dict(metric="net_amount",**PERIOD),"rank_entities":dict(metric="net_amount",dimension="country",**PERIOD),
            "compare_periods":dict(metric="net_amount",baseline=PERIOD,current=CURRENT),
            "decompose_change":dict(metric="net_amount",dimension="country",baseline=PERIOD,current=CURRENT),"inspect_transactions":{}}
        for name,params in cases.items():
            call(name,params | dict(sql="SELECT * FROM transaction_rows"),422)
        for name in ("get_quality_summary","query_metric_series","rank_entities","compare_periods","decompose_change","inspect_transactions"):
            for period,status in [(dict(date_from="2012-01-01",date_to="2012-02-01"),"NO_DATA"),(dict(date_from="2011-12-01",date_to="2012-01-01"),"PARTIAL_PERIOD")]:
                params=cases[name] | (dict(current=period) if name in {"compare_periods","decompose_change"} else period)
                check(name+status,call(name,params)["status"],status)
            check(name+"empty",call(name,cases[name] | dict(country="' OR 1=1 --"))["status"],"EMPTY_RESULT")
        call("inspect_transactions",dict(limit=51),422)
        call("rank_entities",cases["rank_entities"] | dict(top_k=True),422)
        call("decompose_change",cases["decompose_change"] | dict(metric="positive_invoice_count"),422)
        zero=call("compare_periods",cases["compare_periods"] | dict(country="not-a-country"))
        check("zero_baseline_reason",zero["growth_reason"],"ZERO_BASELINE")
        check("zero_baseline_percent",zero["growth_percent"],None)
        report["database_after"]=sha(args.database)
        check("database_bytes_unchanged",report["database_after"],report["database_before"])
        check("quick_check",db.execute("PRAGMA quick_check").fetchone()[0],"ok")
        report["status"]="PASS"
    except Exception as exc:
        report.update(status="FAIL",error_type=type(exc).__name__,error=str(exc))
    finally:
        if client:
            client.close()
        if db:
            db.close()
        if process:
            process.terminate()
            process.wait(timeout=15)
            report["server"].update(stop_exit_code=process.returncode,intentional_stop=True)
        if log:
            log.close()
        report["finished_at"]=datetime.now(timezone.utc).isoformat()
        (args.output/"verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n","utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"calls","checks"}},ensure_ascii=False,indent=2))
    print("CHECKS="+str(len(report["checks"]))+" HTTP_CALLS="+str(len(report["calls"])))
    return 0 if report["status"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
