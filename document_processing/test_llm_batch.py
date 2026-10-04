import csv
import math
import sys
import time
from pathlib import Path
from typing import Any, Optional
import re
import pandas as pd


# ============================================================
# Импорт pipeline
# ============================================================

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

sys.path.insert(
    0,
    str(SRC),
)

from pipeline import process_document_official  # noqa: E402


# ============================================================
# Пути
# ============================================================

DATA_ROOT = Path(
    r"C:\Users\baigina\inter-rao-court-docs\data"
)

RAW_PART1 = (
    DATA_ROOT
    / "raw_part1"
    / "courts_anonymized"
)

RAW_PART2 = (
    DATA_ROOT
    / "raw_part2"
    / "courts_anonymized"
)

RAW_PART3 = (
    DATA_ROOT
    / "raw_part3"
    / "courts_anonymized"
)

OCR_LABELS = (
    RAW_PART1
    / "labels"
    / "ocr.csv"
)

XML_LABELS = (
    RAW_PART1
    / "labels"
    / "xml.csv"
)

OUTPUT_CSV = (
    ROOT
    / "data"
    / "llm_batch_results.csv"
)


# ============================================================
# Тестовый набор
# ============================================================

OCR_FILES = [
    # Судебные приказы — сканы
    "ocr/orders_scan/ocr_001.pdf",
    "ocr/orders_scan/ocr_003.pdf",
    "ocr/orders_scan/ocr_005.pdf",

    # Судебные приказы — электронные
    "ocr/orders_electronic/ocr_007.pdf",
    "ocr/orders_electronic/ocr_009.pdf",

    # Исполнительные листы — сканы
    "ocr/writs_scan/ocr_012.pdf",
    "ocr/writs_scan/ocr_013.pdf",
    "ocr/writs_scan/ocr_015.pdf",
    "ocr/writs_scan/ocr_016.pdf",

    # Исполнительные листы — электронные
    "ocr/writs_electronic/ocr_017.pdf",
    "ocr/writs_electronic/ocr_020.pdf",
    "ocr/writs_electronic/ocr_022.pdf",
]


XML_FILES = [
    "fssp/O_IP_ACT_END_END/fssp_001.xml",
    "fssp/O_IP_ACT_END_END/fssp_002.xml",
    "fssp/O_IP_ACT_END_STOP/fssp_007.xml",
]


# ============================================================
# Поля OCR
# ============================================================

OCR_FIELD_MAP = {
    "document_type": "тип документа",
    "street": "улица",
    "house": "дом",
    "apartment": "кв",

    "full_name": "фио",
    "birth_date": "дата рождения",
    "passport": "паспорт",
    "snils": "снилс",
    "inn": "инн",

    "case_number": "дело_номер",
    "case_date": "дело_дата",

    "debt_period_start": "период_дз_начало",
    "debt_period_end": "период_дз_оконч",

    "principal_debt": "дз_осн",
    "penalty_amount": "дз_пени",
    "state_duty": "дз_пошлина",

    "co_defendants_count": "соответчики_кол-во",
}


# ============================================================
# Поля XML / ФССП
# ============================================================

XML_FIELD_MAP = {
    "street": "street",
    "house": "dom",
    "apartment": "kv",

    "full_name": "DbtrName",

    "case_number": "IdDeloNo",
    "case_date": "IdDeloDate",

    "debt_period_start": "date_start",
    "debt_period_end": "date_end",

    "principal_debt": "rub_deb",
    "penalty_amount": "rub_peni",
    "state_duty": "rub_poshlina",
}


# ============================================================
# Нормализация
# ============================================================

def is_empty(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip()

    return (
        text == ""
        or text.lower() == "nan"
        or text.lower() == "none"
    )


def normalize_text(
    value: Any,
) -> Optional[str]:
    if is_empty(value):
        return None

    return " ".join(
        str(value)
        .strip()
        .split()
    )


def normalize_number(
    value: Any,
) -> Optional[str]:
    if is_empty(value):
        return None

    text = (
        str(value)
        .strip()
        .replace(" ", "")
        .replace(",", ".")
    )

    try:
        number = float(text)

        return (
            f"{number:.2f}"
            .rstrip("0")
            .rstrip(".")
        )

    except ValueError:
        return text


def normalize_inn(
    value,
):
    if is_empty(value):
        return None

    # Если pandas прочитал значение как число,
    # сначала убираем только техническую .0.
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    text = str(value).strip()

    # Например: "862152469440.0"
    if re.fullmatch(
        r"\d+\.0",
        text,
    ):
        text = text[:-2]

    # Scientific notation.
    if "e" in text.lower():
        try:
            return str(
                int(float(text))
            )
        except ValueError:
            pass

    digits = "".join(
        char
        for char in text
        if char.isdigit()
    )

    return digits or None

def normalize_document_type(
    value: Any,
) -> Optional[str]:
    if is_empty(value):
        return None

    text = str(value).strip().lower()

    mapping = {
        "приказ": "судебный приказ",
        "приказ эл": "судебный приказ",

        "ил": "исполнительный лист",
        "ил эл": "исполнительный лист",

        "постановление фссп": "постановление фссп",
    }

    return mapping.get(
        text,
        text,
    )


def normalize_value(
    field: str,
    value: Any,
) -> Optional[str]:

    if field in {
        "principal_debt",
        "penalty_amount",
        "state_duty",
    }:
        return normalize_number(value)

    if field == "inn":
        return normalize_inn(value)

    if field == "document_type":
        return normalize_document_type(value)

    if field == "co_defendants_count":
        if is_empty(value):
            return None

        try:
            return str(
                int(
                    float(value)
                )
            )
        except ValueError:
            return normalize_text(value)

    return normalize_text(value)


# ============================================================
# Поиск файлов
# ============================================================

def resolve_ocr_file(
    relative_path: str,
) -> Optional[Path]:

    path1 = (
        RAW_PART1
        / relative_path
    )

    if path1.exists():
        return path1

    path2 = (
        RAW_PART2
        / relative_path
    )

    if path2.exists():
        return path2

    return None


def resolve_xml_file(
    relative_path: str,
) -> Optional[Path]:

    path = (
        RAW_PART3
        / relative_path
    )

    if path.exists():
        return path

    return None


# ============================================================
# Получение результата pipeline
# ============================================================

def result_to_dict(
    result: Any,
) -> dict:

    if hasattr(
        result,
        "model_dump",
    ):
        return result.model_dump()

    if isinstance(
        result,
        dict,
    ):
        return result

    raise TypeError(
        f"Неизвестный тип результата: "
        f"{type(result).__name__}"
    )


# ============================================================
# Сравнение
# ============================================================

def compare_field(
    field: str,
    expected: Any,
    predicted: Any,
) -> tuple[
    Optional[str],
    Optional[str],
    bool,
]:

    expected_norm = normalize_value(
        field,
        expected,
    )

    predicted_norm = normalize_value(
        field,
        predicted,
    )

    correct = (
        expected_norm
        == predicted_norm
    )

    return (
        expected_norm,
        predicted_norm,
        correct,
    )


# ============================================================
# Обработка OCR
# ============================================================

def test_ocr_document(
    relative_path: str,
    labels: pd.DataFrame,
) -> list[dict]:

    filename = Path(
        relative_path
    ).name

    print()
    print("=" * 70)
    print(
        f"OCR: {filename}"
    )
    print("=" * 70)

    file_path = resolve_ocr_file(
        relative_path
    )

    if file_path is None:
        print(
            f"Файл не найден: "
            f"{relative_path}"
        )

        return []

    label_rows = labels[
        labels["Файл"]
        == relative_path
    ]

    if label_rows.empty:
        print(
            f"Нет эталона: "
            f"{relative_path}"
        )

        return []

    expected_row = (
        label_rows
        .iloc[0]
    )

    started = time.perf_counter()

    try:
        result = (
            process_document_official(
                str(file_path)
            )
        )

        predicted = result_to_dict(
            result
        )

        error = None

    except Exception as exc:

        elapsed = (
            time.perf_counter()
            - started
        )

        print(
            f"ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return [
            {
                "file": filename,
                "source": "ocr",
                "field": "__pipeline__",
                "expected": None,
                "predicted": None,
                "correct": False,
                "seconds": round(
                    elapsed,
                    2,
                ),
                "error": (
                    type(exc).__name__
                ),
            }
        ]

    elapsed = (
        time.perf_counter()
        - started
    )

    rows = []

    for (
        predicted_field,
        label_field,
    ) in OCR_FIELD_MAP.items():

        expected = (
            expected_row[
                label_field
            ]
        )

        predicted_value = (
            predicted.get(
                predicted_field
            )
        )

        (
            expected_norm,
            predicted_norm,
            correct,
        ) = compare_field(
            predicted_field,
            expected,
            predicted_value,
        )

        rows.append(
            {
                "file": filename,
                "source": "ocr",
                "field": predicted_field,
                "expected": expected_norm,
                "predicted": predicted_norm,
                "correct": correct,
                "seconds": round(
                    elapsed,
                    2,
                ),
                "error": error,
            }
        )

    document_correct = sum(
        row["correct"]
        for row in rows
    )

    print(
        f"Поля: {document_correct}/"
        f"{len(rows)}"
    )

    return rows


# ============================================================
# Обработка XML
# ============================================================

def test_xml_document(
    relative_path: str,
    labels: pd.DataFrame,
) -> list[dict]:

    filename = Path(
        relative_path
    ).name

    print()
    print("=" * 70)
    print(
        f"XML: {filename}"
    )
    print("=" * 70)

    file_path = resolve_xml_file(
        relative_path
    )

    if file_path is None:
        print(
            f"Файл не найден: "
            f"{relative_path}"
        )

        return []

    label_rows = labels[
        labels["FileName"]
        == relative_path
    ]

    if label_rows.empty:
        print(
            f"Нет эталона: "
            f"{relative_path}"
        )

        return []

    expected_row = (
        label_rows
        .iloc[0]
    )

    started = time.perf_counter()

    try:
        result = (
            process_document_official(
                str(file_path)
            )
        )

        predicted = result_to_dict(
            result
        )

        error = None

    except Exception as exc:

        elapsed = (
            time.perf_counter()
            - started
        )

        print(
            f"ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return [
            {
                "file": filename,
                "source": "xml",
                "field": "__pipeline__",
                "expected": None,
                "predicted": None,
                "correct": False,
                "seconds": round(
                    elapsed,
                    2,
                ),
                "error": (
                    type(exc).__name__
                ),
            }
        ]

    elapsed = (
        time.perf_counter()
        - started
    )

    rows = []

    for (
        predicted_field,
        label_field,
    ) in XML_FIELD_MAP.items():

        expected = (
            expected_row[
                label_field
            ]
        )

        predicted_value = (
            predicted.get(
                predicted_field
            )
        )

        (
            expected_norm,
            predicted_norm,
            correct,
        ) = compare_field(
            predicted_field,
            expected,
            predicted_value,
        )

        rows.append(
            {
                "file": filename,
                "source": "xml",
                "field": predicted_field,
                "expected": expected_norm,
                "predicted": predicted_norm,
                "correct": correct,
                "seconds": round(
                    elapsed,
                    2,
                ),
                "error": error,
            }
        )

    document_correct = sum(
        row["correct"]
        for row in rows
    )

    print(
        f"Поля: {document_correct}/"
        f"{len(rows)}"
    )

    return rows


# ============================================================
# Итоговый отчёт
# ============================================================

def print_summary(
    rows: list[dict],
) -> None:

    comparable_rows = [
        row
        for row in rows
        if row["field"]
        != "__pipeline__"
    ]

    if not comparable_rows:
        print(
            "Нет результатов для сравнения."
        )

        return

    print()
    print("=" * 70)
    print(
        "ИТОГ ПО ПОЛЯМ"
    )
    print("=" * 70)

    fields = sorted(
        {
            row["field"]
            for row in comparable_rows
        }
    )

    for field in fields:

        field_rows = [
            row
            for row in comparable_rows
            if row["field"] == field
        ]

        correct = sum(
            row["correct"]
            for row in field_rows
        )

        total = len(
            field_rows
        )

        accuracy = (
            correct / total * 100
            if total
            else 0
        )

        print(
            f"{field:24} "
            f"{correct:>2}/{total:<2} "
            f"{accuracy:6.1f}%"
        )

    correct_total = sum(
        row["correct"]
        for row in comparable_rows
    )

    total = len(
        comparable_rows
    )

    print()
    print(
        f"ВСЕ ПОЛЯ: "
        f"{correct_total}/{total} "
        f"({correct_total / total * 100:.1f}%)"
    )


def save_results(
    rows: list[dict],
) -> None:

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "file",
        "source",
        "field",
        "expected",
        "predicted",
        "correct",
        "seconds",
        "error",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    print()
    print(
        f"Результаты сохранены: "
        f"{OUTPUT_CSV}"
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print(
        "Загрузка официальной разметки..."
    )

    ocr_labels = pd.read_csv(
        OCR_LABELS
    )

    xml_labels = pd.read_csv(
        XML_LABELS
    )

    all_rows = []

    print()
    print(
        f"OCR документов: "
        f"{len(OCR_FILES)}"
    )

    print(
        f"XML документов: "
        f"{len(XML_FILES)}"
    )

    for relative_path in OCR_FILES:
        rows = test_ocr_document(
            relative_path,
            ocr_labels,
        )

        all_rows.extend(
            rows
        )

    for relative_path in XML_FILES:
        rows = test_xml_document(
            relative_path,
            xml_labels,
        )

        all_rows.extend(
            rows
        )

    save_results(
        all_rows
    )

    print_summary(
        all_rows
    )


if __name__ == "__main__":
    main()