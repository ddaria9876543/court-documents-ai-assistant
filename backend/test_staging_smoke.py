import hashlib
import uuid

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.stg_document_extraction import StgDocumentExtraction
from app.services.document_service import (
    apply_processing_result,
    create_document,
)


def main():
    db = SessionLocal()

    try:
        unique_value = str(uuid.uuid4())

        file_hash = hashlib.sha256(
            unique_value.encode("utf-8")
        ).hexdigest()

        # ========================================
        # 1. Создаем тестовый документ
        # ========================================

        document = create_document(
            db=db,
            filename="de_staging_smoke_test.pdf",
            original_filename="de_staging_smoke_test.pdf",
            file_path="/tmp/de_staging_smoke_test.pdf",
            file_format="pdf",
            file_size=12345,
            file_hash=file_hash,
        )

        print(
            f"Created document_id={document.id}"
        )

        # ========================================
        # 2. Первая попытка обработки
        # ========================================

        result_1 = {
            "document_type": "исполнительный лист",
            "case_number": "2-TEST/2026",
            "case_date": "2026-10-06",

            "full_name": "Тестов Тест Тестович",
            "birth_date": "1990-01-01",
            "inn": "123456789012",
            "snils": "12345678901",

            "street": "Тестовая",
            "house": "10",
            "apartment": "20",

            "principal_debt": "15000.50",
            "penalty_amount": "1000.25",
            "state_duty": "500.00",
            "postal_cost": "100.00",

            "status": "ok",
            "warnings": [],
            "missing_fields": [],

            "requires_legal_action": False,

            "model_name": "qwen3:4b",
            "processor_version": "de-smoke-test-v1",
        }

        apply_processing_result(
            db=db,
            document=document,
            result=result_1,
        )

        # ========================================
        # 3. Вторая попытка обработки
        # ========================================

        result_2 = {
            "document_type": "исполнительный лист",
            "case_number": "2-TEST/2026",
            "case_date": "2026-10-06",

            "full_name": "Тестов Тест Тестович",
            "birth_date": "1990-01-01",
            "inn": "123456789012",
            "snils": "12345678901",

            "street": "Тестовая",
            "house": "10",
            "apartment": "20",

            "principal_debt": "15500.75",
            "penalty_amount": "1100.25",
            "state_duty": "500.00",
            "postal_cost": "100.00",

            "status": "ok",
            "warnings": [],
            "missing_fields": [],

            "requires_legal_action": True,
            "legal_action_reason": "Smoke test",
            "evidence_fragment": "Test evidence",

            "model_name": "qwen3:4b",
            "processor_version": "de-smoke-test-v1",
        }

        apply_processing_result(
            db=db,
            document=document,
            result=result_2,
        )

        # ========================================
        # 4. Читаем staging из PostgreSQL
        # ========================================

        rows = db.scalars(
            select(
                StgDocumentExtraction
            )
            .where(
                StgDocumentExtraction.document_id
                == document.id
            )
            .order_by(
                StgDocumentExtraction.attempt
            )
        ).all()

        print()
        print("STAGING RESULTS")
        print("=" * 60)

        for row in rows:
            print(
                f"document_id={row.document_id} | "
                f"attempt={row.attempt} | "
                f"case_number={row.case_number} | "
                f"principal_debt={row.principal_debt} | "
                f"status={row.processing_status} | "
                f"model={row.model_name}"
            )

        # ========================================
        # 5. Проверки
        # ========================================

        assert len(rows) == 2
        assert rows[0].attempt == 1
        assert rows[1].attempt == 2

        assert rows[0].principal_debt == 15000.50
        assert rows[1].principal_debt == 15500.75

        assert rows[0].model_name == "qwen3:4b"
        assert rows[1].model_name == "qwen3:4b"

        print()
        print("SMOKE TEST PASSED")
        print(
            f"document_id={document.id}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()