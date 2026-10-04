import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile


STORAGE_DIR = Path("storage/documents")

ALLOWED_EXTENSIONS = {".pdf", ".xml"}


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_file_extension(filename: str) -> str:
    extension = get_file_extension(filename)

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file format")

    return extension


async def read_file(file: UploadFile) -> bytes:
    content = await file.read()

    if not content:
        raise ValueError("File is empty")

    return content


def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_storage_filename(extension: str) -> str:
    return f"{uuid.uuid4()}{extension}"


def save_file(content: bytes, storage_filename: str) -> Path:
    STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = STORAGE_DIR / storage_filename

    file_path.write_bytes(content)

    return file_path