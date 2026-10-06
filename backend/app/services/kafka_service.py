import json
from typing import Any

from confluent_kafka import Producer

from app.core.config import settings


class KafkaProducerService:
    def __init__(self) -> None:
        self.producer = Producer(
            {
                "bootstrap.servers": (
                    settings.KAFKA_BOOTSTRAP_SERVERS
                ),
                "client.id": "court-documents-backend",
            }
        )

    @staticmethod
    def _delivery_report(err, msg) -> None:
        if err is not None:
            raise RuntimeError(
                f"Kafka delivery failed: {err}"
            )

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
    ) -> None:
        self.producer.produce(
            topic=topic,
            key=key,
            value=json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            callback=self._delivery_report,
        )

        remaining = self.producer.flush(5)

        if remaining != 0:
            raise RuntimeError(
                "Kafka flush timed out: "
                f"{remaining} message(s) not delivered"
            )

    def publish_document_processing(
        self,
        document_id: int,
        object_name: str,
        original_filename: str,
        file_format: str,
    ) -> None:
        payload = {
            "event": "document_uploaded",
            "document_id": document_id,
            "object_name": object_name,
            "original_filename": original_filename,
            "file_format": file_format,
            "retry_count": 0,
        }

        self.publish(
            topic=settings.KAFKA_DOCUMENT_TOPIC,
            payload=payload,
            key=str(document_id),
        )

    def publish_retry(
        self,
        payload: dict[str, Any],
    ) -> None:
        retry_payload = dict(payload)

        retry_payload["retry_count"] = (
            int(
                retry_payload.get(
                    "retry_count",
                    0,
                )
            )
            + 1
        )

        self.publish(
            topic=settings.KAFKA_DOCUMENT_TOPIC,
            payload=retry_payload,
            key=str(
                retry_payload["document_id"]
            ),
        )

    def publish_dlq(
        self,
        payload: dict[str, Any],
        error: str,
    ) -> None:
        dlq_payload = dict(payload)

        dlq_payload["event"] = (
            "document_processing_failed"
        )
        dlq_payload["error"] = error

        self.publish(
            topic=settings.KAFKA_DLQ_TOPIC,
            payload=dlq_payload,
            key=str(
                dlq_payload["document_id"]
            ),
        )


kafka_producer = KafkaProducerService()