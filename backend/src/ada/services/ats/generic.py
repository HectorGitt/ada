"""Agentic fallback for arbitrary application pages: read the DOM's form,
have the model map applicant facts onto it, fill, submit, verify."""
import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ada.config import get_settings
from ada.resilience import retry_async
from ada.services.ats import ApplicantAnswers, SubmitOutcome
from ada.services.ats.executor import (
    TOTAL_TIMEOUT_S,
    _any_visible,
    _collect_errors,
    _texts_for,
)
from ada.vertex import vertex_client

if TYPE_CHECKING:
    from playwright.async_api import Page

CV_FILE_MARKER = "__CV_FILE__"
APPLY_LINK_PATTERN = re.compile(r"\bapply\b", re.I)
CONFIRMATION_PATTERN = re.compile(
    r"thank you|application (received|submitted|sent)|successfully (applied|submitted)", re.I
)
FIELD_LIMIT = 40

_FIELD_JS = """
els => els.map(el => ({
  tag: el.tagName.toLowerCase(),
  type: el.getAttribute('type') || '',
  name: el.getAttribute('name') || '',
  id: el.id || '',
  placeholder: el.getAttribute('placeholder') || '',
  aria: el.getAttribute('aria-label') || '',
  label: (el.labels && el.labels[0] ? el.labels[0].innerText : '').slice(0, 120),
  required: el.required || el.getAttribute('aria-required') === 'true',
}))
"""


def mapping_prompt(fields: list[dict[str, Any]], answers: ApplicantAnswers) -> str:
    facts = {
        "full_name": answers.full_name,
        "first_name": answers.first_name,
        "last_name": answers.last_name,
        "email": answers.email,
        "phone": answers.phone or "",
        "linkedin_url": answers.linkedin_url or "",
    }
    return (
        "You are filling a job application form on behalf of a candidate.\n"
        f"Candidate facts (the ONLY information you may use): {json.dumps(facts)}\n"
        f"Form fields (indexed): {json.dumps(fields)}\n"
        "Return a JSON array of {\"index\": int, \"value\": string} objects.\n"
        "Rules: map each fillable field to a candidate fact when it clearly matches; "
        f'use "{CV_FILE_MARKER}" as the value for a resume/CV file field; '
        "NEVER invent an answer — omit any field you cannot fill from the facts alone."
    )


def parse_mapping(raw: str, field_count: int) -> list[tuple[int, str]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    mapped: list[tuple[int, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        index, value = item.get("index"), item.get("value")
        if isinstance(index, int) and 0 <= index < field_count and isinstance(value, str) and value:
            mapped.append((index, value))
    return mapped


async def _model_map(
    fields: list[dict[str, Any]], answers: ApplicantAnswers
) -> list[tuple[int, str]]:
    s = get_settings()
    client = vertex_client()
    resp = await retry_async(
        lambda: client.aio.models.generate_content(
            model=s.vertex_model,
            contents=mapping_prompt(fields, answers),
            config={"response_mime_type": "application/json"},
        ),
        attempts=s.llm_max_attempts,
    )
    return parse_mapping(resp.text or "", len(fields))


async def submit_generic(url: str, answers: ApplicantAnswers) -> SubmitOutcome:
    try:
        return await asyncio.wait_for(_run(url, answers), timeout=TOTAL_TIMEOUT_S)
    except TimeoutError:
        return SubmitOutcome(
            status="needs_attention",
            detail="The application page took too long to respond — try again shortly.",
        )


async def _run(url: str, answers: ApplicantAnswers) -> SubmitOutcome:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await _follow_apply_link(page)
            fields = await _collect_fields(page)
            if not fields:
                return SubmitOutcome(
                    status="needs_attention",
                    detail="Couldn't find an application form on that page — it may "
                    "require a login or list the job elsewhere.",
                )
            mapping = await _model_map(fields, answers)
            if not any(v == CV_FILE_MARKER for _, v in mapping) and not mapping:
                return SubmitOutcome(
                    status="needs_attention",
                    detail="The form's questions couldn't be answered from your profile alone.",
                )
            filled = await _fill(page, fields, mapping, answers)
            if not filled:
                return SubmitOutcome(
                    status="needs_attention",
                    detail="The form fields wouldn't accept input — it may be login-walled.",
                )
            if not await _submit(page):
                return SubmitOutcome(
                    status="needs_attention",
                    detail="Couldn't find a working submit button on the form.",
                )
            await page.wait_for_load_state("networkidle", timeout=30_000)
            if await _confirmed(page):
                return SubmitOutcome(status="submitted")
            errors = await _collect_errors(page)
            detail = (
                "The form needs answers only you can give: " + "; ".join(errors[:5])
                if errors
                else "No submission confirmation appeared — the form may have extra steps."
            )
            return SubmitOutcome(status="needs_attention", detail=detail)
        finally:
            await browser.close()


async def _follow_apply_link(page: "Page") -> None:
    for _ in range(2):
        if await _collect_fields(page):
            return
        try:
            link = page.get_by_role("link", name=APPLY_LINK_PATTERN).first
            button = page.get_by_role("button", name=APPLY_LINK_PATTERN).first
            target = link if await link.count() else button
            await target.click(timeout=5_000)
            await page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Exception:
            return


async def _collect_fields(page: "Page") -> list[dict[str, Any]]:
    try:
        handles = page.locator(
            "input:visible:not([type=hidden]):not([type=submit]):not([type=button]), "
            "textarea:visible, select:visible, input[type=file]"
        )
        raw = await handles.evaluate_all(_FIELD_JS)
    except Exception:
        return []
    fields = []
    for i, f in enumerate(raw[:FIELD_LIMIT]):
        fields.append({"index": i, **f})
    return fields


async def _fill(
    page: "Page",
    fields: list[dict[str, Any]],
    mapping: list[tuple[int, str]],
    answers: ApplicantAnswers,
) -> bool:
    locator = page.locator(
        "input:visible:not([type=hidden]):not([type=submit]):not([type=button]), "
        "textarea:visible, select:visible, input[type=file]"
    )
    from ada.services.ats.executor import _attempt

    any_filled = False
    with tempfile.TemporaryDirectory() as tmp:
        cv_path = Path(tmp) / answers.cv_filename
        cv_path.write_bytes(answers.cv_bytes)
        for index, value in mapping:
            target = locator.nth(index)
            if value == CV_FILE_MARKER or fields[index].get("type") == "file":
                done = await _attempt(target.set_input_files(str(cv_path), timeout=8_000))
            elif fields[index].get("tag") == "select":
                done = await _attempt(target.select_option(label=value, timeout=8_000))
            else:
                done = await _attempt(target.fill(value, timeout=8_000))
            any_filled = any_filled or done
    return any_filled


async def _submit(page: "Page") -> bool:
    candidates = (
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Submit")',
        'button:has-text("Apply")',
    )
    from ada.services.ats.executor import _attempt

    for selector in candidates:
        if await _attempt(page.locator(selector).first.click(timeout=8_000)):
            return True
    return False


async def _confirmed(page: "Page") -> bool:
    if await _any_visible(
        page, ("text=Thank you for applying", "text=Application submitted",
               "text=Application received", '[role="status"]:has-text("submitted")')
    ):
        return True
    # A stray "thank you" banner never removes the form — require the application
    # form to be gone AND a confirmation phrase before calling it submitted.
    if not await _form_gone(page):
        return False
    for region in ("h1", "h2", "main", '[role="status"]', ".confirmation"):
        for text in await _texts_for(page, region):
            if CONFIRMATION_PATTERN.search(text):
                return True
    return False


async def _form_gone(page: "Page") -> bool:
    selector = (
        "input:visible:not([type=hidden]):not([type=submit]):not([type=button]), "
        "textarea:visible"
    )
    try:
        remaining = await page.locator(selector).count()
    except Exception:
        return False
    return remaining == 0
