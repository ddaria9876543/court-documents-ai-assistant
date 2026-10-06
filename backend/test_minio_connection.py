from app.services.storage_service import storage_service


def main() -> None:
    storage_service.ensure_bucket()

    object_name = storage_service.upload_bytes(
        object_name="test/hello.txt",
        data=b"MinIO connection works",
        content_type="text/plain",
    )

    print(f"Uploaded: {object_name}")


if __name__ == "__main__":
    main()