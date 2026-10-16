"""Dependencies injected into nodes. Everything external (LLM, vector search, research engine) goes through here,
which keeps nodes testable and makes failure injection trivial."""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, AsyncIterator, Awaitable, Callable


@dataclass
class Deps:
    users: dict                                                 # user_id -> User (server side identity)
    llm: Callable[[list[dict]], Awaitable[str]]                 # non streaming, JSON and summaries
    llm_stream: Callable[[list[dict]], AsyncIterator[str]]      # streaming, final answers
    search: Callable[[Any, Any], Awaitable[Any]]                # (user, SearchRequest) -> RetrievalResult
    make_engine: Callable[[Callable[[dict], Any]], Any]         # emit -> RLMEngine (per request events)
    departments: Callable[[Any], set]                           # user -> known department names
    bank_name: str = "Lanka Meridian Bank"
    today: Callable[[], date] = date.today
    search_timeout: float = 25.0
    research_timeout: float = 150.0
    max_attempts: int = 2                                       # response generations per turn
    buses: dict = field(default_factory=dict)                   # request_id -> EventBus

    def emit(self, request_id: str, type_: str, node: str | None = None, **data) -> None:
        bus = self.buses.get(request_id)
        if bus is not None:
            bus.emit(type_, node, **data)
