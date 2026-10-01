from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


DocumentStatus = Literal[
    "new",
    "processing",
    "processed",
    "needs_review",
    "error",
    "sent",
]


class DocumentFileResponse(BaseModel):
    filename: str
    file_format: Literal["pdf", "xml"]

    model_config = ConfigDict(from_attributes=True)


class DocumentHistoryResponse(BaseModel):
    event_type: str
    message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    id: int
    filename: str
    documentType: str | None = None
    caseNumber: str | None = None
    enforcementNumber: str | None = None
    status: DocumentStatus
    createdAt: datetime
    summary: str = ""
    needsReview: bool = False
    reviewReason: str | None = None
    files: list[DocumentFileResponse]
    debtor: str | None = None
    amount: float | None = None
    fileFormat: Literal["pdf", "xml"]

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentListResponse):
    history: list[DocumentHistoryResponse]


class UploadedDocumentResponse(BaseModel):
    document_id: int
    filename: str
    status: DocumentStatus


class DuplicateResponse(BaseModel):
    status: str
    filename: str
    existing_document_id: int


class UploadErrorResponse(BaseModel):
    filename: str
    error: str


class UploadResponse(BaseModel):
    uploaded: list[UploadedDocumentResponse]
    duplicates: list[DuplicateResponse]
    errors: list[UploadErrorResponse]


class StatusUpdate(BaseModel):
    status: DocumentStatus