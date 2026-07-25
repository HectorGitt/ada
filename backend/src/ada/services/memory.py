"""Ada's long-term memory: extract durable facts from chat, recall them by similarity.

Write path (remember): after a chat exchange, a cheap extraction pass pulls out facts
worth keeping ("prefers remote", "8 years in fintech"), skipping anything already
remembered; new facts are embedded and stored. Failures are logged, never raised —
memory must not break the conversation it learns from.

Read path (recall): embed the user's latest message, KNN over their memories, and hand
the closest facts to the coach prompt.
"""
import json

from google.genai import types

from ada.config import get_settings
from ada.db.repositories import UserMemoryRepository
from ada.observability import log
from ada.services.search import SearchService
from ada.vertex import vertex_client

_EXTRACT_SYSTEM = """You maintain Ada's long-term memory about a job candidate. From the \
conversation excerpt, extract durable facts worth remembering for future career coaching: \
preferences, constraints, goals, background, decisions ("prefers remote work", "relocating \
to Canada in 2027", "8 years in fintech sales"). Rules: only facts the candidate actually \
stated; nothing transient or small-talk; one short sentence per fact; at most 5 facts. You \
are given the facts already remembered — do not repeat or rephrase any of them. Return JSON \
of the exact shape {"facts": [str, ...]}; return {"facts": []} when nothing new is worth \
keeping."""

_RECALL_K = 6
_MAX_EXISTING_IN_PROMPT = 60


class MemoryService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model
        self._search = SearchService()

    async def remember(
        self, repo: UserMemoryRepository, user_id: str, exchange: str
    ) -> int:
        """Extract + store new facts from a chat exchange. Returns how many were kept."""
        try:
            existing = [m.content for m in await repo.list_for_user(user_id)]
            facts = await self._extract(existing[:_MAX_EXISTING_IN_PROMPT], exchange)
            if not facts:
                return 0
            vectors = await self._search.embed_many(facts)
            stored = await repo.add_many(user_id, list(zip(facts, vectors, strict=True)))
            log.info("memories_stored", user_id=user_id, count=stored)
            return stored
        except Exception as exc:  # noqa: BLE001 — memory is best-effort by design
            log.warning("memory_write_failed", user_id=user_id, error=str(exc))
            return 0

    async def recall(
        self, repo: UserMemoryRepository, user_id: str, query: str, k: int = _RECALL_K
    ) -> list[str]:
        """Facts most relevant to the query, or [] — never raises into the chat path."""
        try:
            vector = await self._search.embed(query[:2_000])
            return [m.content for m in await repo.recall(user_id, vector, k)]
        except Exception as exc:  # noqa: BLE001
            log.warning("memory_recall_failed", user_id=user_id, error=str(exc))
            return []

    async def _extract(self, existing: list[str], exchange: str) -> list[str]:
        remembered = "\n".join(f"- {f}" for f in existing) or "(nothing yet)"
        prompt = f"ALREADY REMEMBERED:\n{remembered}\n\nCONVERSATION EXCERPT:\n{exchange[:12_000]}"
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_SYSTEM,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(resp.text or "{}")
        facts = data.get("facts", [])
        return [f.strip() for f in facts if isinstance(f, str) and len(f.strip()) >= 8][:5]
