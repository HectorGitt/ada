"""Job matching node: embed the candidate + role, KNN over seeded jobs via pgvector.

Deliberately model-light in the hot path — one embedding call, then a vector
search. The human-readable "why this matched" label is derived from the cosine
similarity, not a second Gemini round-trip.
"""
from google.genai import types

from ada.config import get_settings
from ada.db.models import EMBED_DIM, Job
from ada.db.repositories import JobRepository
from ada.resilience import retry_async
from ada.vertex import vertex_client


def _fit_label(similarity: float) -> str:
    if similarity >= 0.75:
        return "Strong fit for your background"
    if similarity >= 0.55:
        return "Good fit — worth a tailored application"
    return "Stretch role — highlight transferable skills"


class SearchService:
    def __init__(self) -> None:
        s = get_settings()
        self._client = vertex_client()
        self._attempts = s.llm_max_attempts
        # AI Studio ships gemini-embedding-001 (native 3072-dim); reduce to our column
        # width. Vertex keeps text-embedding-004. Cosine distance is scale-invariant,
        # so truncated vectors rank consistently as long as every vector uses one model.
        if s.gemini_api_key:
            self._model = s.gemini_embedding_model
            self._config: types.EmbedContentConfig | None = types.EmbedContentConfig(
                output_dimensionality=EMBED_DIM
            )
        else:
            self._model = s.embedding_model
            self._config = None

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_many([text]))[0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        resp = await retry_async(
            lambda: self._client.aio.models.embed_content(
                model=self._model, contents=texts, config=self._config
            ),
            attempts=self._attempts,
        )
        if not resp.embeddings:
            raise RuntimeError("embedding API returned no vectors")
        vectors: list[list[float]] = []
        for e in resp.embeddings:
            if e.values is None:
                raise RuntimeError("embedding API returned an empty vector")
            vectors.append(list(e.values))
        return vectors

    async def match(
        self, *, jobs: JobRepository, target_role: str, cv_text: str, k: int = 5
    ) -> list[dict]:
        query = f"{target_role}\n\n{cv_text}"
        vector = await self.embed(query)
        rows = await jobs.knn(vector, k)
        return [self._to_match(job, distance) for job, distance in rows]

    @staticmethod
    def _to_match(job: Job, distance: float) -> dict:
        similarity = max(0.0, 1.0 - distance)
        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "match": round(similarity * 100),
            "reason": _fit_label(similarity),
        }
