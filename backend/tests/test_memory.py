"""Memory is best-effort: recall/remember must never raise into the chat path.
Without model credentials the embed/generate calls fail, exercising that contract."""


class _FakeMemRepo:
    async def list_for_user(self, user_id: str) -> list:
        return []

    async def recall(self, user_id: str, vector: list, k: int) -> list:
        return []

    async def add_many(self, user_id: str, pairs: list) -> int:
        return len(pairs)


async def test_recall_returns_empty_on_failure():
    from ada.services.memory import MemoryService

    result = await MemoryService().recall(_FakeMemRepo(), "user-1", "career background")
    assert result == []


async def test_remember_returns_zero_on_failure():
    from ada.services.memory import MemoryService

    kept = await MemoryService().remember(_FakeMemRepo(), "user-1", "You: I lead a team.")
    assert kept == 0
