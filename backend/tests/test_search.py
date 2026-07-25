from ada.services import search
from ada.services.search import SearchService


class _FakeJob:
    def __init__(self, title: str, company: str, location: str) -> None:
        self.title, self.company, self.location = title, company, location
        self.id = 1
        self.url = "https://example.com/job/1"


class _FakeJobs:
    def __init__(self, rows) -> None:
        self._rows = rows

    async def knn(self, vector, k):
        return self._rows[:k]


def test_fit_label_bands():
    assert "Strong" in search._fit_label(0.80)
    assert "Good" in search._fit_label(0.60)
    assert "Stretch" in search._fit_label(0.30)


async def test_match_shapes_and_scores(monkeypatch):
    monkeypatch.setattr(search, "vertex_client", lambda: object())
    svc = SearchService()

    async def fake_embed(_):
        return [0.0] * 768

    svc.embed = fake_embed  # type: ignore[method-assign]
    jobs = _FakeJobs(
        [
            (_FakeJob("Backend Engineer", "Paystack", "Lagos"), 0.10),
            (_FakeJob("Data Engineer", "Jumia", "Remote"), 0.50),
        ]
    )
    out = await svc.match(jobs=jobs, target_role="Backend", cv_text="cv", k=2)
    assert [m["title"] for m in out] == ["Backend Engineer", "Data Engineer"]
    assert out[0]["match"] == 90  # (1 - 0.10) * 100
    assert out[1]["match"] == 50
    assert out[0]["company"] == "Paystack" and "reason" in out[0]
