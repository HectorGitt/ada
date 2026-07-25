"""CV upload: accept a PDF/DOCX/TXT, return extracted text, archive original to GCS."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.services.documents import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    UnsupportedDocument,
    process_cv_upload,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class CvUploadOut(BaseModel):
    cv_text: str
    gcs_uri: str | None
    filename: str


@router.post("/cv", response_model=CvUploadOut)
async def upload_cv(
    file: UploadFile = File(...), user: User = Depends(current_user)
) -> CvUploadOut:
    filename = file.filename or "cv"
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "CV file is too large (5 MB max).")
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    try:
        text, gcs_uri = await process_cv_upload(user.id, filename, data, file.content_type)
    except UnsupportedDocument as exc:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(422, f"{exc} (accepted: {allowed})") from exc
    return CvUploadOut(cv_text=text, gcs_uri=gcs_uri, filename=filename)
