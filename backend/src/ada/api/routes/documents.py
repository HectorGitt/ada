"""CV uploads: accept PDF/DOCX/TXT, archive the original to GCS, list + preview."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import UploadedDocumentRepository
from ada.db.session import get_session
from ada.services.documents import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    UnsupportedDocument,
    process_cv_upload,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class CvUploadOut(BaseModel):
    id: int
    cv_text: str
    gcs_uri: str | None
    filename: str


class UploadedDocOut(BaseModel):
    id: int
    filename: str
    size_bytes: int
    archived: bool
    created_at: str


class UploadedDocDetailOut(UploadedDocOut):
    cv_text: str


@router.post("/cv", response_model=CvUploadOut)
async def upload_cv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
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
    doc = await UploadedDocumentRepository(session).add(
        user_id=user.id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(data),
        gcs_uri=gcs_uri,
        cv_text=text,
    )
    return CvUploadOut(id=doc.id, cv_text=text, gcs_uri=gcs_uri, filename=filename)


@router.get("", response_model=list[UploadedDocOut])
async def list_documents(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[UploadedDocOut]:
    docs = await UploadedDocumentRepository(session).list_for_user(user.id)
    return [
        UploadedDocOut(
            id=d.id,
            filename=d.filename,
            size_bytes=d.size_bytes,
            archived=d.gcs_uri is not None,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=UploadedDocDetailOut)
async def get_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> UploadedDocDetailOut:
    doc = await UploadedDocumentRepository(session).get_for_user(doc_id, user.id)
    if doc is None:
        raise HTTPException(404, "Document not found.")
    return UploadedDocDetailOut(
        id=doc.id,
        filename=doc.filename,
        size_bytes=doc.size_bytes,
        archived=doc.gcs_uri is not None,
        created_at=doc.created_at.isoformat(),
        cv_text=doc.cv_text,
    )
