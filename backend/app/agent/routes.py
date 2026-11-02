from typing import Annotated
from fastapi import APIRouter, Query, Request, Response
from .contracts import CreateRun, AnswerRun, ResumeRun

router=APIRouter(prefix='/api/v1',tags=['agent'])


@router.get('/agent/capabilities')
def capabilities(request: Request):
    return request.app.state.agent_service.capabilities()


@router.post('/runs',status_code=202)
def create_run(body: CreateRun,request: Request,response: Response):
    result,created=request.app.state.agent_service.create(body)
    response.status_code=202 if created else 200
    return result


@router.get('/runs')
def list_runs(request: Request,limit: Annotated[int,Query(ge=1,le=100)]=20,offset: Annotated[int,Query(ge=0,le=10000)]=0):
    return request.app.state.agent_service.list(limit,offset)


@router.get('/runs/{run_id}')
def get_run(run_id: str,request: Request):
    return request.app.state.agent_service.get(run_id)


@router.post('/runs/{run_id}/input')
def answer_run(run_id: str,body: AnswerRun,request: Request):
    return request.app.state.agent_service.submit(run_id,body,'input')


@router.post('/runs/{run_id}/resume')
def resume_run(run_id: str,body: ResumeRun,request: Request):
    return request.app.state.agent_service.submit(run_id,body,'resume')


@router.post('/runs/{run_id}/rerun',status_code=202)
def rerun(run_id: str,body: ResumeRun,request: Request,response: Response):
    result,created=request.app.state.agent_service.rerun(run_id,body)
    response.status_code=202 if created else 200
    return result


@router.post('/runs/{run_id}/cancel')
def cancel_run(run_id: str,request: Request):
    return request.app.state.agent_service.cancel(run_id)
