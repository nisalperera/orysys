"""Offline drills: real API + real LangGraph, fake external dependencies.
Run with T0-T5 installed. No OpenRouter/Pinecone/MCP requests or resource changes.
"""
import asyncio
import json
from contextlib import suppress

import pytest
pytest.importorskip('fastapi')
pytest.importorskip('langgraph')
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.service import ChatService
from app.auth.models import USERS
from app.graph.builder import build_graph
from app.tools.registry import Registry, Spec, ToolError
from pydantic import BaseModel
from tests.graph_helpers import FakeLLM, FakeStream, FakeSearch, FakeEngine, make_deps


def service(**kwargs):
    deps=make_deps(**kwargs)
    return ChatService(build_graph(deps),deps),deps

def app_for(svc):
    async def builder(): return svc
    return create_app(service_builder=builder)

def ask(client,message='What is the pool runbook?',key='dev-viewer-key',session='drill-session-001'):
    return client.post('/chat',headers={'X-API-Key':key},json={'message':message,'session_id':session})

@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    monkeypatch.setenv('LANGCHAIN_TRACING_V2','false')
    # Explicit demo identity mapping prevents developer-specific API_TOKENS breaking tests.
    monkeypatch.setenv('API_TOKENS',json.dumps({'dev-viewer-key':'viewer1','dev-analyst-key':'analyst1','dev-admin-key':'admin1'}))
    monkeypatch.setenv('RATE_LIMIT_CAPACITY','100')
    monkeypatch.setenv('RATE_LIMIT_REFILL_PER_SEC','1')


def test_vector_database_failure_is_honest_not_hallucinated():
    svc,deps=service(search=FakeSearch(error=ConnectionError('private-db-host')))
    with TestClient(app_for(svc)) as c:
        res=ask(c)
    assert res.status_code==200
    body=res.json()
    assert 'unable to search' in body['answer'].lower()
    assert body['citations']==[] and 'private-db-host' not in body['answer']
    assert not deps.fakes.stream.calls


def test_retrieval_timeout_finishes_with_clear_answer():
    async def slow(user,req): await asyncio.sleep(10)
    svc,deps=service()
    deps.search=slow;deps.search_timeout=.01
    with TestClient(app_for(svc)) as c:
        res=ask(c)
    assert res.status_code==200 and 'unable to search' in res.json()['answer'].lower()


def test_response_provider_failure_returns_extractive_evidence():
    svc,deps=service(stream=FakeStream(['unused'],fail=True))
    with TestClient(app_for(svc)) as c:
        res=ask(c)
    body=res.json()
    assert res.status_code==200 and body['degraded']
    assert 'INC-2026-007' in body['answer'] and body['citations']
    assert 'ConnectionError' not in body['answer']


def test_router_failure_uses_safe_heuristic():
    svc,deps=service(llm=FakeLLM(fail=['supervisor']))
    with TestClient(app_for(svc)) as c:
        res=ask(c)
    assert res.status_code==200 and res.json()['intent']=='knowledge_qa'
    assert deps.fakes.search.calls


def test_research_failure_falls_back_and_discloses_limitation():
    svc,deps=service(llm=FakeLLM(supervisor={'intent':'deep_research','standalone_query':'all payment outages'}),
                     engine=FakeEngine(error=ConnectionError('private-provider-detail')))
    with TestClient(app_for(svc)) as c:
        res=ask(c,'Summarize all payment outages',key='dev-analyst-key')
    body=res.json()
    assert res.status_code==200 and body['intent']=='knowledge_qa'
    assert 'standard search was used instead' in body['answer']
    assert 'private-provider-detail' not in body['answer']


def test_invalid_auth_and_request_shape_are_rejected_before_llm():
    svc,deps=service()
    with TestClient(app_for(svc)) as c:
        assert ask(c,key='bad-key').status_code==401
        assert c.post('/chat',headers={'X-API-Key':'dev-viewer-key'},json={'session_id':'too-short'}).status_code==422
    assert not deps.fakes.llm.calls


def test_session_cannot_be_reused_by_another_user():
    svc,deps=service()
    with TestClient(app_for(svc)) as c:
        assert ask(c).status_code==200
        assert ask(c,key='dev-admin-key').status_code==403


def test_rate_limit_applies_before_sse_headers_and_is_per_user(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_CAPACITY','1')
    monkeypatch.setenv('RATE_LIMIT_REFILL_PER_SEC','0.0001')
    svc,deps=service()
    with TestClient(app_for(svc)) as c:
        assert ask(c).status_code==200
        res=c.post('/chat/stream',headers={'X-API-Key':'dev-viewer-key'},
                   json={'message':'pool?', 'session_id':'drill-session-002'})
        assert res.status_code==429 and int(res.headers['Retry-After'])>=1
        assert ask(c,key='dev-analyst-key',session='analyst-drill-001').status_code==200


class Empty(BaseModel): pass

def tool_service(mode='ok'):
    svc,deps=service()
    registry=Registry(USERS)
    async def handler(user,args):
        if mode=='slow': await asyncio.sleep(10)
        if mode=='down': raise ConnectionError('secret-enterprise-endpoint')
        return {'mock':True,'status':'ok'}
    registry.register(Spec('enterprise_probe',Empty,frozenset({'analyst','admin'}),handler,.01))
    from types import SimpleNamespace
    deps.tools=SimpleNamespace(registry=registry)
    return svc,deps


def test_tool_denial_is_server_enforced_and_no_role_override():
    svc,deps=tool_service()
    with TestClient(app_for(svc)) as c:
        res=c.post('/tools/execute',headers={'X-API-Key':'dev-viewer-key'},
                   json={'name':'enterprise_probe','arguments':{}})
        assert res.status_code==403
        res=c.post('/tools/execute',headers={'X-API-Key':'dev-viewer-key'},
                   json={'name':'enterprise_probe','arguments':{},'role':'admin'})
        assert res.status_code==422


@pytest.mark.parametrize('mode,expected',[('slow',504),('down',503)])
def test_enterprise_tool_timeout_and_outage_are_safe(mode,expected):
    svc,deps=tool_service(mode)
    with TestClient(app_for(svc)) as c:
        res=c.post('/tools/execute',headers={'X-API-Key':'dev-analyst-key'},
                   json={'name':'enterprise_probe','arguments':{}})
    assert res.status_code==expected
    assert 'secret-enterprise-endpoint' not in res.text


def test_incomplete_answer_is_not_returned_on_turn_timeout():
    svc,deps=service()
    svc.turn_timeout=.01
    async def slow(messages): await asyncio.sleep(10);return '{}'
    deps.llm=slow
    with TestClient(app_for(svc)) as c:
        res=ask(c)
    assert res.status_code==200 and res.json()['degraded']
    assert 'Something went wrong' in res.json()['answer']


def test_disconnect_cancels_in_progress_generation():
    # Test service iterator directly: an in-process HTTP client may buffer streaming bodies.
    async def run():
        svc,deps=service(stream=FakeStream(['word '*500],delay=.005))
        gen=svc.stream(USERS['viewer1'],'disconnect-drill-001','What is the pool runbook?')
        async for ev in gen:
            if ev['type']=='token': break
        await gen.aclose()
        await asyncio.sleep(.02)
        assert not deps.buses
    asyncio.run(run())

def test_factory_registers_tool_route_for_injected_services():
    svc, _ = service()
    app = app_for(svc)

    assert "/tools/execute" in app.openapi()["paths"]

    matches = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/tools/execute"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(matches) == 1