from app.services.kafka_service import kafka_producer


def main() -> None:
    kafka_producer.publish_document_processing(
        document_id=9999,
        object_name="originals/python-test.pdf",
        original_filename="python-test.pdf",
        file_format="pdf",
    )

    print("Kafka event published successfully")


if __name__ == "__main__":
    main()