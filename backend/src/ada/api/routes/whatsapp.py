"""Inbound WhatsApp — a candidate answers an intro by replying, without opening the app.

Twilio POSTs each inbound message here (form-encoded). We verify it's really Twilio, map
the sender's number to the candidate, and apply their YES/NO to their most recent open
intro — the same accept/decline path the app button uses. The reply is TwiML, so the
candidate gets an immediate confirmation in the same chat.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ada.config import get_settings
from ada.db.models import IntroStatus
from ada.db.repositories import IntroRepository, ProfileRepository
from ada.db.session import get_session
from ada.observability import log
from ada.services.intros import respond_to_intro
from ada.services.whatsapp import parse_reply, phone_digits, verify_twilio_signature

router = APIRouter(prefix="/webhooks", tags=["whatsapp"])


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _twiml(message: str) -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{_xml_escape(message)}</Message></Response>"
    )
    return Response(content=body, media_type="application/xml")


def _public_url(request: Request) -> str:
    """The URL Twilio actually called — behind Cloud Run the TLS scheme lives in the
    forwarded header, so rebuild it rather than trusting request.url.scheme."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    url = f"{proto}://{host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    return url


@router.post("/whatsapp")
async def inbound_whatsapp(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Response:
    settings = get_settings()
    params = {k: v for k, v in (await request.form()).multi_items() if isinstance(v, str)}

    if settings.twilio_validate_signature:
        ok = verify_twilio_signature(
            auth_token=settings.twilio_auth_token,
            url=_public_url(request),
            params=params,
            signature=request.headers.get("X-Twilio-Signature", ""),
        )
        if not ok:
            log.warning("whatsapp_inbound_bad_signature", frm=params.get("From"))
            return Response(status_code=403)

    sender = params.get("From", "")
    body = params.get("Body", "")
    action = parse_reply(body)
    if action is None:
        return _twiml("Reply YES to connect or NO to pass on your latest intro from Ada.")

    profile = await ProfileRepository(session).by_phone(phone_digits(sender))
    if profile is None:
        return _twiml(
            "We couldn't match this number to an Ada account. Add your phone in your "
            "profile, then reply here."
        )

    intro = await IntroRepository(session).latest_requested_for_candidate(profile.user_id)
    if intro is None:
        return _twiml("You have no intros waiting right now. We'll message you when one lands.")

    status = IntroStatus.ACCEPTED if action == "accept" else IntroStatus.DECLINED
    moved = await respond_to_intro(
        intro=intro, responder_id=profile.user_id, status=status,
        schedule=background.add_task,
    )
    if not moved:
        return _twiml("That intro was already answered — nothing more to do.")

    log.info("whatsapp_intro_response", user_id=profile.user_id, action=action)
    if action == "accept":
        return _twiml("Done — you're connected. We've emailed you their details. Good luck! 🎉")
    return _twiml("Got it — we've let them know. Ada will keep finding better-fit roles.")
