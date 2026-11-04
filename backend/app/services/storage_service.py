
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import tempfile
from typing import Iterator

from minio import Minio

from app.core.config import settings


class StorageService:
    def __init__(self) -> None:
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.ensure_bucket()

        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

        return object_name

    def download_to_temp(
        self,
        object_name: str,
        suffix: str = "",
    ) -> Path:
        self.ensure_bucket()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=object_name,
                file_path=str(temp_path),
            )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        return temp_path

    @contextmanager
    def open_document(
        self,
        file_path: str,
        file_format: str = "",
    ) -> Iterator[Path]:
        """
        Provide a local path for a document.

        Local files are used directly.
        MinIO objects are downloaded temporarily.

        Temporary files are removed automatically.
        """
        local_path = Path(file_path)

        if local_path.is_file():
            yield local_path
            return

        # MinIO object keys created by the upload endpoint.
        if not file_path.startswith("originals/"):
            raise FileNotFoundError(
                f"Local document not found: {file_path}"
            )

        suffix = (
            f".{file_format.lstrip('.')}"
            if file_format
            else ""
        )

        temp_path = self.download_to_temp(
            object_name=file_path,
            suffix=suffix,
        )

        try:
            yield temp_path
        finally:
            temp_path.unlink(missing_ok=True)


storage_service = StorageService()
