import pytest

from ada.api.routes.assess import _rate_limited
from ada.services.assess import _heuristic_assessment
from ada.services.documents import UnsupportedDocument, extract_cv_text


def test_heuristic_assessment_shape():
    a = _heuristic_assessment("Senior engineer. Grew revenue 40% over 3 years. "
                              "Managed a team. BSc from university. " * 6)
    assert 0 <= a.score <= 100
    assert len(a.fixes) == 3
    assert a.method == "heuristic"
    assert a.headline


def test_rate_limiter_caps_per_ip():
    ip = "test-ip-1.2.3.4"
    # first `limit` calls pass, the next is limited
    assert all(not _rate_limited(ip, limit=3, window=3600) for _ in range(3))
    assert _rate_limited(ip, limit=3, window=3600) is True
    # a different IP is independent
    assert _rate_limited("other-ip", limit=3, window=3600) is False


async def test_extract_cv_text_reads_txt_and_rejects_unknown():
    text = await extract_cv_text("cv.txt", b"Senior Engineer with 8 years in fintech. " * 4)
    assert "Senior Engineer" in text
    with pytest.raises(UnsupportedDocument):
        await extract_cv_text("resume.exe", b"not a document")
