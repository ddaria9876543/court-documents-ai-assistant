import json
import sys
import time
from pathlib import Path

from confluent_kafka import Consumer

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_history import DocumentHistory
from app.services.document_service import (
    apply_processing_result,
)
from app.services.kafka_service import (
    kafka_producer,
)
from app.services.storage_service import (
    storage_service,
)


# --------------------------------------------------
# Existing document processing pipeline
# --------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

DOCUMENT_PROCESSING_SRC = (
    PROJECT_ROOT
    / "document_processing"
    / "src"
)

if str(DOCUMENT_PROCESSING_SRC) not in sys.path:
    sys.path.append(
        str(DOCUMENT_PROCESSING_SRC)
    )

from api_adapter import build_api_result


# --------------------------------------------------
# Worker settings
# --------------------------------------------------

MAX_ATTEMPTS = 3


# --------------------------------------------------
# Kafka consumer
# --------------------------------------------------

consumer = Consumer(
    {
        "bootstrap.servers": (
            settings.KAFKA_BOOTSTRAP_SERVERS
        ),
        "group.id": (
            "court-documents-processing-worker"
        ),
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    }
)


def process_message(
    payload: dict,
) -> None:
    document_id = payload[
        "document_id"
    ]

    object_name = payload[
        "object_name"
    ]

    file_format = payload.get(
        "file_format",
        "",
    )

    db = SessionLocal()
    temp_path = None

    try:
        document = db.get(
            Document,
            document_id,
        )

        if document is None:
            raise RuntimeError(
                f"Document {document_id} not found"
            )

        suffix = (
            f".{file_format}"
            if file_format
            else ""
        )

        print(
            f"[worker] document_id={document_id}: "
            "downloading from MinIO"
        )

        temp_path = (
            storage_service.download_to_temp(
                object_name=object_name,
                suffix=suffix,
            )
        )

        print(
            f"[worker] document_id={document_id}: "
            "starting OCR/LLM processing"
        )

        processing_result = (
            build_api_result(
                temp_path
            )
        )

        document = (
            apply_processing_result(
                db=db,
                document=document,
                result=processing_result,
            )
        )

        print(
            f"[worker] document_id={document_id}: "
            f"finished with status={document.status}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

        if (
            temp_path
            and temp_path.exists()
        ):
            try:
                temp_path.unlink()
            except OSError:
                pass


def mark_document_error(
    document_id: int,
    error: str,
) -> None:
    db = SessionLocal()

    try:
        document = db.get(
            Document,
            document_id,
        )

        if document is None:
            return

        document.status = "error"

        history = DocumentHistory(
            document_id=document_id,
            event_type="processing_error",
            message=(
                "Document moved to DLQ after "
                f"{MAX_ATTEMPTS} attempts: "
                f"{error}"
            ),
        )

        db.add(history)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def handle_processing_error(
    payload: dict,
    error: Exception,
) -> None:
    retry_count = int(
        payload.get(
            "retry_count",
            0,
        )
    )

    attempt_number = (
        retry_count + 1
    )

    document_id = payload.get(
        "document_id"
    )

    print(
        f"[worker] document_id={document_id}: "
        f"attempt {attempt_number}/"
        f"{MAX_ATTEMPTS} failed: {error}"
    )

    if attempt_number < MAX_ATTEMPTS:
        # Небольшая задержка перед повторной попыткой.
        delay_seconds = (
            attempt_number * 2
        )

        print(
            f"[worker] retry in "
            f"{delay_seconds}s"
        )

        time.sleep(
            delay_seconds
        )

        kafka_producer.publish_retry(
            payload
        )

        print(
            f"[worker] document_id={document_id}: "
            "retry published"
        )

        return

    kafka_producer.publish_dlq(
        payload=payload,
        error=str(error),
    )

    if document_id is not None:
        mark_document_error(
            document_id=int(document_id),
            error=str(error),
        )

    print(
        f"[worker] document_id={document_id}: "
        "moved to DLQ"
    )


def main() -> None:
    consumer.subscribe(
        [
            settings.KAFKA_DOCUMENT_TOPIC
        ]
    )

    print(
        "[worker] Waiting for "
        f"{settings.KAFKA_DOCUMENT_TOPIC}..."
    )

    try:
        while True:
            message = consumer.poll(
                1.0
            )

            if message is None:
                continue

            if message.error():
                print(
                    "[worker] Kafka error: "
                    f"{message.error()}"
                )
                continue

            try:
                payload = json.loads(
                    message.value().decode(
                        "utf-8"
                    )
                )

                print(
                    "[worker] Received: "
                    f"{payload}"
                )

                process_message(
                    payload
                )

            except Exception as exc:
                try:
                    handle_processing_error(
                        payload=payload,
                        error=exc,
                    )

                except Exception as retry_exc:
                    print(
                        "[worker] Retry/DLQ "
                        "handling failed: "
                        f"{retry_exc}"
                    )

                    # Если даже retry/DLQ не удалось
                    # записать, offset НЕ коммитим.
                    continue

            # Коммитим исходное сообщение:
            # - после успешной обработки;
            # - после успешной публикации retry;
            # - после успешной публикации в DLQ.
            consumer.commit(
                message=message,
                asynchronous=False,
            )

    except KeyboardInterrupt:
        print(
            "\n[worker] Stopping..."
        )

    finally:
        consumer.close()


if __name__ == "__main__":
    main()