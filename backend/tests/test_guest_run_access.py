from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from ada.api.routes.runs import _authorize
from ada.auth.tokens import mint
from ada.db.models import Run, User


def _run(**over):
    base = dict(id="r", reference="r", email="x@e.com", target_role="PM", cv_text="cv",
                user_id=None, access_token_hash=None, created_at=datetime.now(UTC))
    base.update(over)
    return Run(**base)


def test_guest_run_needs_valid_unexpired_token():
    raw, token_hash = mint()
    run = _run(access_token_hash=token_hash)
    _authorize(run, None, raw)                                   # correct token → ok
    with pytest.raises(HTTPException):
        _authorize(run, None, None)                             # id alone is not enough
    with pytest.raises(HTTPException):
        _authorize(run, None, "wrong-token")                   # bad token
    expired = _run(access_token_hash=token_hash,
                   created_at=datetime.now(UTC) - timedelta(days=999))
    with pytest.raises(HTTPException):
        _authorize(expired, None, raw)                         # past the guest TTL


def test_owned_run_is_owner_only():
    run = _run(user_id="u1")
    _authorize(run, User(id="u1", email="a@e.com"), None)       # owner → ok
    with pytest.raises(HTTPException):
        _authorize(run, User(id="u2", email="b@e.com"), None)  # other user → 404
    with pytest.raises(HTTPException):
        _authorize(run, None, "any-token")                     # anonymous → 404
