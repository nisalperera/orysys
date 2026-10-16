import asyncio
import json
from types import SimpleNamespace
import pytest
from app.auth.models import USERS
from app.rlm.jsonutil import extract_json
from tests.test_rlm import engine, FakeLLM, QUESTION


class MissingMetricCatalog:
    def __init__(self, catalog):
        self.catalog = catalog
    def stats(self, user):
        return self.catalog.stats(user)
    def select(self, user, **kwargs):
        return self.catalog.select(user, **kwargs)
    def body(self, doc_id):
        text = self.catalog.body(doc_id)
        if doc_id == "INC-2025-031":
            return "\n".join(line for line in text.splitlines() if "Failed transactions" not in line)
        return text


@pytest.mark.asyncio
async def test_executor_marks_missing_metrics_and_discloses_subtotal():
    eng, _ = engine(FakeLLM())
    eng.catalog = MissingMetricCatalog(eng.catalog)
    result = await eng.run(USERS["viewer1"], QUESTION)
    coverage = result.analysis["metric_coverage"]["failed_transactions"]
    assert coverage["known_documents"] == 4 and coverage["total_documents"] == 5
    assert coverage["missing_doc_ids"] == ["INC-2025-031"]
    assert result.degraded and "known subtotal" in result.answer
    assert any("measurements are incomplete" in reason for reason in result.degraded_reasons)


@pytest.mark.asyncio
async def test_final_reducer_receives_measurement_limitations():
    prompts = []
    class SpyLLM(FakeLLM):
        async def __call__(self, messages):
            if messages[0]["content"].startswith("[task:reduce]"):
                prompts.append(messages[-1]["content"])
            return await super().__call__(messages)
    eng, _ = engine(SpyLLM())
    eng.catalog = MissingMetricCatalog(eng.catalog)
    await eng.run(USERS["viewer1"], QUESTION)
    assert prompts and "Completeness limitations" in prompts[-1]
    assert "measurements are incomplete" in prompts[-1]


@pytest.mark.asyncio
async def test_overlapping_causes_reach_executor_result_and_answer():
    class ConflictingLLM(FakeLLM):
        async def __call__(self, messages):
            raw = await super().__call__(messages)
            if messages[0]["content"].startswith("[task:analyze]"):
                data = extract_json(raw)
                finding = dict(data["findings"][0])
                finding["root_cause"] = "Unrelated scheduler deadlock"
                data["findings"].append(finding)
                return json.dumps(data)
            return raw
    eng, _ = engine(ConflictingLLM())
    result = await eng.run(USERS["viewer1"], QUESTION)
    assert result.analysis["root_cause_groups_overlap"]
    assert result.degraded
    assert "cause-group totals overlap" in result.answer


class PartialFailureLLM(FakeLLM):
    async def __call__(self, messages):
        if messages[0]["content"].startswith("[task:partial]"):
            raise ConnectionError("private-provider-marker")
        return await super().__call__(messages)


@pytest.mark.asyncio
async def test_partial_failure_without_loss_still_records_fallback():
    eng, events = engine(PartialFailureLLM())
    run = SimpleNamespace(sem=asyncio.Semaphore(1), reasons=[])
    group = ["[INC-2026-007] record one", "[INC-2026-011] record two"]
    assert await eng._partial(group, run) == "\n".join(group)
    assert any("retained 2 of 2" in reason for reason in run.reasons)
    assert any(event["type"] == "partial_reduce_fallback" and event["omitted"] == 0 for event in events)


@pytest.mark.asyncio
async def test_partial_failure_with_loss_preserves_whole_records():
    eng, events = engine(PartialFailureLLM())
    run = SimpleNamespace(sem=asyncio.Semaphore(1), reasons=[])
    first = "[INC-2026-007] " + "x" * 900
    second = "[INC-2026-011] " + "y" * 900
    assert await eng._partial([first, second], run) == first
    assert any("retained 1 of 2" in reason for reason in run.reasons)
    assert any(event["type"] == "partial_reduce_fallback" and event["omitted"] == 1 for event in events)


@pytest.mark.asyncio
async def test_partial_failure_is_disclosed_in_final_answer():
    eng, _ = engine(PartialFailureLLM(), fan_in=2)
    result = await eng.run(USERS["viewer1"], QUESTION)
    assert result.degraded and "Partial aggregation failed" in result.answer
    assert "private-provider-marker" not in result.answer


@pytest.mark.asyncio
async def test_final_reducer_failure_preserves_completeness_notes():
    eng, _ = engine(FakeLLM(fail_reduce=True))
    eng.catalog = MissingMetricCatalog(eng.catalog)
    result = await eng.run(USERS["viewer1"], QUESTION)
    assert result.degraded and "automatic summary" in result.answer
    assert "known subtotal" in result.answer
    assert "[INC-2025-031]" in result.answer
    assert result.answer.count("Analysis limitations:") == 1
