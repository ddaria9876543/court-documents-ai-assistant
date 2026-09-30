from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentFileResponse(BaseModel):
    filename: str
    file_format: str

    model_config = ConfigDict(from_attributes=True)


class DocumentHistoryResponse(BaseModel):
    event_type: str
    message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    id: int
    status: str
    document_type: str | None
    created_at: datetime
    files: list[DocumentFileResponse]

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    id: int
    status: str
    document_type: str | None
    created_at: datetime
    files: list[DocumentFileResponse]
    history: list[DocumentHistoryResponse]

    model_config = ConfigDict(from_attributes=True)


class UploadedDocumentResponse(BaseModel):
    document_id: int
    filename: str
    status: str


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