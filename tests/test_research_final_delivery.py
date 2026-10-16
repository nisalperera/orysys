import json
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.api.service import ChatService
from app.auth.models import USERS
from app.graph.builder import build_graph
from app.rlm.jsonutil import extract_json
from tests.graph_helpers import make_deps, FakeLLM as GraphLLM
from tests.test_rlm import engine, FakeLLM, QUESTION, run


class MissingMeasurements:
    def __init__(self, catalog):
        self.catalog = catalog
    def stats(self, user):
        return self.catalog.stats(user)
    def select(self, user, **kwargs):
        return self.catalog.select(user, **kwargs)
    def body(self, doc_id):
        body = self.catalog.body(doc_id)
        if doc_id == "INC-2025-031":
            return "\n".join(line for line in body.splitlines()
                             if "Duration:" not in line and "Failed transactions" not in line)
        return body


class RejectedEvidenceLLM(FakeLLM):
    async def __call__(self, messages):
        raw = await super().__call__(messages)
        if messages[0]["content"].startswith("[task:analyze]"):
            data = extract_json(raw)
            for finding in data["findings"]:
                finding["relevant"] = True
                finding["evidence"] = ["UNSUPPORTED#99"]
            return json.dumps(data)
        return raw


class PartialFailureLLM(FakeLLM):
    async def __call__(self, messages):
        if messages[0]["content"].startswith("[task:partial]"):
            raise ConnectionError("private-partial-marker")
        return await super().__call__(messages)


def test_executor_rejected_evidence_is_inconclusive():
    research, _ = engine(RejectedEvidenceLLM())
    result = run(research.run(USERS["viewer1"], QUESTION))
    assert result.docs_considered > 0 and not result.relevant_doc_ids
    assert result.degraded and "could not establish supported relevance" in result.answer
    assert "No relevant documents" not in result.answer


def test_automatic_summary_labels_incomplete_downtime():
    research, _ = engine(FakeLLM(fail_reduce=True))
    research.catalog = MissingMeasurements(research.catalog)
    result = run(research.run(USERS["viewer1"], QUESTION))
    assert "min known downtime subtotal" in result.answer
    assert "known subtotal" in result.answer and result.degraded


def api_result(monkeypatch, llm_factory, missing=False, **settings):
    monkeypatch.setenv("API_TOKENS", json.dumps({"integration-analyst-key": "analyst1"}))
    monkeypatch.setenv("RATE_LIMIT_CAPACITY", "100")
    async def build_service():
        class PerRequestResearch:
            def factory(self, emit):
                research, _ = engine(llm_factory(), **settings)
                research._emit_cb = emit
                if missing:
                    research.catalog = MissingMeasurements(research.catalog)
                return research
        deps = make_deps(
            llm=GraphLLM(supervisor={"intent": "deep_research", "standalone_query": QUESTION}),
            engine=PerRequestResearch(),
        )
        return ChatService(build_graph(deps), deps)
    with TestClient(create_app(service_builder=build_service)) as client:
        response = client.post("/chat", headers={"X-API-Key": "integration-analyst-key"},
                               json={"message": QUESTION, "session_id": "research-final-check"})
    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "deep_research"
    return result


def test_missing_measurements_survive_real_graph_and_api(monkeypatch):
    result = api_result(monkeypatch, FakeLLM, missing=True)
    assert result["degraded"] is True
    assert "known subtotal" in result["answer"]
    assert result["validation"]["final_ok"] is True
    assert result["citations"]
    assert "INC-9999-999" not in json.dumps(result["citations"])


def test_partial_fallback_warning_survives_real_graph_and_api(monkeypatch):
    result = api_result(monkeypatch, PartialFailureLLM, fan_in=2)
    assert result["degraded"] is True
    assert "Partial aggregation failed" in result["answer"]
    assert "private-partial-marker" not in result["answer"]
    assert result["validation"]["final_ok"] is True
    assert result["citations"]


def test_inconclusive_relevance_survives_real_graph_and_api(monkeypatch):
    result = api_result(monkeypatch, RejectedEvidenceLLM)
    assert result["degraded"] is True
    assert "could not establish supported relevance" in result["answer"]
    assert "No relevant documents" not in result["answer"]
    assert result["citations"] == []
