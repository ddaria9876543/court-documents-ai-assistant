from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# ПУТИ
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pipeline import process_document_official


DATA_ROOT = Path(
    r"C:\Users\baigina\inter-rao-court-docs\data"
)

PART1 = (
    DATA_ROOT
    / "raw_part1"
    / "courts_anonymized"
)

PART2 = (
    DATA_ROOT
    / "raw_part2"
    / "courts_anonymized"
)

PART3 = (
    DATA_ROOT
    / "raw_part3"
    / "courts_anonymized"
)

OCR_LABELS = (
    PART1
    / "labels"
    / "ocr.csv"
)

XML_LABELS = (
    PART1
    / "labels"
    / "xml.csv"
)

OUTPUT_DIR = (
    CURRENT_DIR
    / "evaluation_results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# НАСТРОЙКИ ПРОГОНА
# ============================================================

# Сначала запускаем короткий smoke-test.
# Когда убедимся, что всё работает:
# SMOKE_TEST = False

SMOKE_TEST = True

SMOKE_OCR_FILES = set()

SMOKE_XML_FILES = {
    f"fssp_{i:03}.xml"
    for i in range(1, 22)
}

# ============================================================
# МАППИНГ ЭТАЛОННЫХ ПОЛЕЙ -> НАШИХ ПОЛЕЙ
# ============================================================

OCR_FIELD_MAP = {
    "тип документа": [
        "document_type",
    ],
    "улица": [
        "street",
    ],
    "дом": [
        "house",
    ],
    "кв": [
        "apartment",
    ],
    "фамилия": [
        "last_name",
    ],
    "имя": [
        "first_name",
    ],
    "отчетство": [
        "patronymic",
    ],
    "фио": [
        "full_name",
    ],
    "дата рождения": [
        "birth_date",
    ],
    "паспорт": [
        "passport",
    ],
    "снилс": [
        "snils",
    ],
    "инн": [
        "inn",
    ],
    "дело_номер": [
        "case_number",
    ],
    "дело_дата": [
        "case_date",
    ],
    "период_дз_начало": [
        "debt_period_start",
    ],
    "период_дз_оконч": [
        "debt_period_end",
    ],
    "дз_осн": [
        "principal_debt",
    ],
    "дз_пени": [
        "penalty_amount",
    ],
    "дз_пошлина": [
        "state_duty",
        "state_duty_amount",
    ],
    "соответчики_кол-во": [
        "co_defendants_count",
    ],
    "соответчики_фио": [
        "co_defendants_names",
    ],
}


XML_FIELD_MAP = {
    "IdDeloNo": [
        "case_number",
    ],
    "IdDeloDate": [
        "case_date",
    ],
    "IpNo": [
        "enforcement_number",
        "ip_number",
    ],
    "street": [
        "street",
    ],
    "dom": [
        "house",
    ],
    "kv": [
        "apartment",
    ],
    "DbtrName": [
        "full_name",
    ],
    "date_start": [
        "debt_period_start",
    ],
    "date_end": [
        "debt_period_end",
    ],
    "rub_deb": [
        "principal_debt",
    ],
    "rub_peni": [
        "penalty_amount",
    ],
    "rub_poshlina": [
        "state_duty",
        "state_duty_amount",
    ],
    "rub_post": [
        "postal_cost",
        "postal_expenses",
    ],
}


NUMERIC_FIELDS = {
    "дз_осн",
    "дз_пени",
    "дз_пошлина",
    "соответчики_кол-во",
    "rub_deb",
    "rub_peni",
    "rub_poshlina",
    "rub_post",
}


DATE_FIELDS = {
    "дата рождения",
    "дело_дата",
    "период_дз_начало",
    "период_дз_оконч",
    "IdDeloDate",
    "date_start",
    "date_end",
}


DIGITS_ONLY_FIELDS = {
    "снилс",
    "инн",
    "паспорт",
}


# ============================================================
# ЧТЕНИЕ CSV
# ============================================================

def read_csv_rows(
    path: Path,
) -> list[dict[str, str]]:

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        return list(
            csv.DictReader(file)
        )


# ============================================================
# ПОИСК ФАЙЛОВ
# ============================================================

def collect_ocr_files() -> dict[str, Path]:

    files: dict[str, Path] = {}

    for root in [
        PART1 / "ocr",
        PART2 / "ocr",
    ]:
        for path in root.rglob("*.pdf"):
            files[path.name] = path

    return files


def collect_xml_files() -> dict[str, Path]:

    return {
        path.name: path
        for path in (
            PART3 / "fssp"
        ).rglob("*.xml")
    }


# ============================================================
# РАБОТА С РЕЗУЛЬТАТОМ PIPELINE
# ============================================================

def unwrap_value(
    value: Any,
) -> Any:

    if isinstance(value, dict):

        if "value" in value:
            return value.get("value")

    return value


def get_fields(
    result: dict[str, Any],
) -> dict[str, Any]:

    fields = result.get(
        "fields"
    )

    if isinstance(fields, dict):
        return fields

    return result


def get_prediction(
    result: dict[str, Any],
    aliases: list[str],
) -> Any:

    fields = get_fields(result)

    for alias in aliases:

        value = result.get(alias)

        if value is not None:
            return unwrap_value(value)

        value = fields.get(alias)

        if value is not None:
            return unwrap_value(value)

    return None


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize_empty(
    value: Any,
) -> Any:

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.lower() in {
        "nan",
        "none",
        "null",
        "не найдено",
        "не определено",
    }:
        return None

    return value


def normalize_text(
    value: Any,
) -> str | None:

    value = normalize_empty(value)

    if value is None:
        return None

    text = str(value)

    text = (
        text
        .replace("ё", "е")
        .replace("Ё", "Е")
        .lower()
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def normalize_digits(
    value: Any,
) -> str | None:

    value = normalize_empty(value)

    if value is None:
        return None

    digits = re.sub(
        r"\D",
        "",
        str(value),
    )

    return digits or None


def normalize_number(
    value: Any,
) -> float | None:

    value = normalize_empty(value)

    if value is None:
        return None

    text = str(value)

    text = (
        text
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(",", ".")
    )

    text = re.sub(
        r"[^\d.\-]",
        "",
        text,
    )

    try:
        return float(text)

    except ValueError:
        return None


def normalize_date(
    value: Any,
) -> str | None:

    value = normalize_empty(value)

    if value is None:
        return None

    text = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y.%m.%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(
                text,
                fmt,
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            pass

    return normalize_text(text)


def normalize_document_type(
    value: Any,
) -> str | None:

    text = normalize_text(value)

    if text is None:
        return None

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # Исполнительный лист:
    # ИЛ
    # ИЛ эл
    # исполнительный лист
    if (
        text in {
            "ил",
            "ил эл",
            "ил электронный",
            "исполнительный лист",
            "исполнительный лист эл",
            "исполнительный лист электронный",
        }
        or (
            "исполнительн" in text
            and "лист" in text
        )
    ):
        return "исполнительный лист"

    # Судебный приказ:
    # СП
    # СП эл
    # судебный приказ
    if (
        text in {
            "сп",
            "сп эл",
            "сп электронный",
            "судебный приказ",
        }
        or "приказ" in text
    ):
        return "судебный приказ"

    if (
        "фссп" in text
        or (
            "постановлен" in text
            and "пристав" in text
        )
    ):
        return "постановление фссп"

    return text
def normalize_street(
    value: Any,
) -> str | None:
    """
    Убирает только технические различия записи улицы.

    Например:
    "ул. Макетная"
    "Макетная ул."
    "Макетная"

    -> "макетная"
    """

    text = normalize_text(value)

    if text is None:
        return None

    # Убираем обозначение именно улицы.
    # Проспект/переулок/шоссе и т.п. не удаляем,
    # чтобы не скрывать реальные ошибки.
    text = re.sub(
        r"(^|\s)(?:ул\.?|улица)(?=\s|$)",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"[,.]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text or None

def normalize_name_token(
    value: str,
) -> str:
    """
    Нормализует падежные окончания русских ФИО.

    Примеры:
    Макетнов / Макетнова / Макетновой -> макетнов
    Леонтий / Леонтия -> леонти
    Алиса / Алисы -> алис
    Павловна / Павловны -> павловн
    """

    value = normalize_text(value) or ""

    value = re.sub(
        r"[^а-яa-z-]",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Сначала более длинные окончания.
    endings = (
        "ого",
        "его",
        "ому",
        "ему",
        "ыми",
        "ими",
        "ой",
        "ей",
        "ую",
        "юю",
        "ый",
        "ий",
        "ая",
        "яя",
        "ы",
        "и",
        "а",
        "я",
        "у",
        "ю",
        "е",
        "й",
    )

    for ending in endings:

        if (
            value.endswith(ending)
            and len(value) - len(ending) >= 3
        ):
            return value[:-len(ending)]

    return value

def normalize_person_name(
    value: str,
) -> tuple[str, str, str] | None:
    """
    Одно ФИО -> нормализованная тройка.
    """

    text = normalize_text(value)

    if not text:
        return None

    parts = re.findall(
        r"[а-яa-z-]+",
        text,
        flags=re.IGNORECASE,
    )

    if len(parts) < 3:
        return None

    return (
        normalize_name_token(parts[0]),
        normalize_name_token(parts[1]),
        normalize_name_token(parts[2]),
    )


def normalize_co_defendants(
    value: Any,
) -> set[tuple[str, str, str]] | None:
    """
    Сравнивает списки ФИО независимо от:
    - порядка;
    - падежа;
    - разделителя , или ;
    - переносов строк.
    """

    value = normalize_empty(value)

    if value is None:
        return None

    text = normalize_text(value)

    if not text:
        return None

    # Получаем все слова ФИО подряд.
    tokens = re.findall(
        r"[а-яa-z-]+",
        text,
        flags=re.IGNORECASE,
    )

    result: set[
        tuple[str, str, str]
    ] = set()

    # В разметке каждое лицо записано как
    # Фамилия Имя Отчество.
    for index in range(
        0,
        len(tokens) - 2,
        3,
    ):

        person = (
            normalize_name_token(
                tokens[index]
            ),
            normalize_name_token(
                tokens[index + 1]
            ),
            normalize_name_token(
                tokens[index + 2]
            ),
        )

        result.add(person)

    return result or None
def normalize_for_field(
    field_name: str,
    value: Any,
) -> Any:

    if field_name == "тип документа":
        return normalize_document_type(
            value
        )

    if field_name == "улица":
        return normalize_street(
            value
        )

    if field_name == "соответчики_фио":
        return normalize_co_defendants(
            value
        )

    if field_name in NUMERIC_FIELDS:
        return normalize_number(
            value
        )

    if field_name in DATE_FIELDS:
        return normalize_date(
            value
        )

    if field_name in DIGITS_ONLY_FIELDS:
        return normalize_digits(
            value
        )

    return normalize_text(
        value
    )

# ============================================================
# СРАВНЕНИЕ
# ============================================================

def values_equal(
    field_name: str,
    expected: Any,
    predicted: Any,
) -> bool:

    expected_n = normalize_for_field(
        field_name,
        expected,
    )

    predicted_n = normalize_for_field(
        field_name,
        predicted,
    )

    if (
        expected_n is None
        and predicted_n is None
    ):
        return True

    if (
        expected_n is None
        or predicted_n is None
    ):
        return False

    if field_name in NUMERIC_FIELDS:

        return abs(
            float(expected_n)
            - float(predicted_n)
        ) <= 0.01

    if field_name == "соответчики_фио":

        return (
            expected_n
            == predicted_n
        )

    return (
        expected_n
        == predicted_n
    )
# ============================================================
# ОДИН ДОКУМЕНТ
# ============================================================

def evaluate_document(
    path: Path,
    label_row: dict[str, str],
    field_map: dict[str, list[str]],
) -> dict[str, Any]:

    started = time.time()

    try:
        raw_result = process_document_official(
            str(path)
        )

        # Pipeline возвращает Pydantic-модель
        # OfficialExtractedFields.
        # Для evaluation переводим её
        # в обычный dict.
        if hasattr(
            raw_result,
            "model_dump",
        ):
            result = (
                raw_result.model_dump()
            )

        elif isinstance(
            raw_result,
            dict,
        ):
            result = raw_result

        else:
            raise TypeError(
                "Unsupported pipeline result "
                f"type: {type(raw_result).__name__}"
            )

        processing_error = None

    except Exception as exc:

        result = {}

        processing_error = (
            f"{type(exc).__name__}: {exc}"
        )

    elapsed = round(
        time.time() - started,
        2,
    )

    field_results = {}

    for label_field, aliases in (
        field_map.items()
    ):

        expected = label_row.get(
            label_field
        )

        predicted = get_prediction(
            result,
            aliases,
        )

        correct = values_equal(
            label_field,
            expected,
            predicted,
        )

        field_results[
            label_field
        ] = {
            "expected": expected,
            "predicted": predicted,
            "correct": correct,
        }

    fields = get_fields(result)

    return {
        "filename": path.name,
        "path": str(path),
        "elapsed_seconds": elapsed,
        "processing_error":
            processing_error,
        "pipeline_status":
            result.get(
                "status"
            )
            or fields.get(
                "status"
            ),
        "needs_review":
            result.get(
                "needs_review"
            ),
        "missing_fields":
            result.get(
                "missing_fields"
            )
            or fields.get(
                "missing_fields"
            )
            or [],
        "field_results":
            field_results,
        "raw_result":
            result,
    }

# ============================================================
# СОХРАНЕНИЕ JSONL
# ============================================================

def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for row in rows:

            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


# ============================================================
# ERROR CSV
# ============================================================

def write_errors_csv(
    path: Path,
    results: list[dict[str, Any]],
) -> None:

    rows = []

    for item in results:

        if item[
            "processing_error"
        ]:

            rows.append(
                {
                    "filename":
                        item[
                            "filename"
                        ],
                    "field":
                        "__PROCESSING__",
                    "expected":
                        "",
                    "predicted":
                        item[
                            "processing_error"
                        ],
                }
            )

        for field_name, info in (
            item[
                "field_results"
            ].items()
        ):

            if not info["correct"]:

                rows.append(
                    {
                        "filename":
                            item[
                                "filename"
                            ],
                        "field":
                            field_name,
                        "expected":
                            info[
                                "expected"
                            ],
                        "predicted":
                            info[
                                "predicted"
                            ],
                    }
                )

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "filename",
                "field",
                "expected",
                "predicted",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# SUMMARY
# ============================================================

def build_summary(
    results: list[dict[str, Any]],
) -> dict[str, Any]:

    stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
        }
    )

    processing_errors = 0
    needs_review_count = 0

    total_seconds = 0.0

    for item in results:

        total_seconds += (
            item[
                "elapsed_seconds"
            ]
        )

        if item[
            "processing_error"
        ]:
            processing_errors += 1

        if item.get(
            "needs_review"
        ):
            needs_review_count += 1

        for field_name, info in (
            item[
                "field_results"
            ].items()
        ):

            stats[
                field_name
            ][
                "total"
            ] += 1

            if info[
                "correct"
            ]:
                stats[
                    field_name
                ][
                    "correct"
                ] += 1

    field_accuracy = {}

    total_correct = 0
    total_fields = 0

    for field_name, values in (
        stats.items()
    ):

        correct = values[
            "correct"
        ]

        total = values[
            "total"
        ]

        accuracy = (
            correct / total
            if total
            else 0
        )

        field_accuracy[
            field_name
        ] = {
            "correct":
                correct,
            "total":
                total,
            "accuracy":
                round(
                    accuracy,
                    4,
                ),
        }

        total_correct += correct
        total_fields += total

    overall_accuracy = (
        total_correct / total_fields
        if total_fields
        else 0
    )

    return {
        "documents":
            len(results),
        "processing_errors":
            processing_errors,
        "needs_review":
            needs_review_count,
        "total_seconds":
            round(
                total_seconds,
                2,
            ),
        "average_seconds":
            round(
                total_seconds
                / len(results),
                2,
            )
            if results
            else 0,
        "field_checks":
            total_fields,
        "correct_fields":
            total_correct,
        "overall_accuracy":
            round(
                overall_accuracy,
                4,
            ),
        "field_accuracy":
            field_accuracy,
    }


# ============================================================
# ПЕЧАТЬ SUMMARY
# ============================================================

def print_summary(
    title: str,
    summary: dict[str, Any],
) -> None:

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    print(
        f"Документов: "
        f"{summary['documents']}"
    )

    print(
        f"Ошибок обработки: "
        f"{summary['processing_errors']}"
    )

    print(
        f"Needs review: "
        f"{summary['needs_review']}"
    )

    print(
        f"Среднее время: "
        f"{summary['average_seconds']} сек."
    )

    print(
        f"Общая точность полей: "
        f"{summary['overall_accuracy'] * 100:.2f}%"
    )

    print()
    print(
        "Точность по полям:"
    )

    for field_name, stats in (
        summary[
            "field_accuracy"
        ].items()
    ):

        print(
            f"  {field_name:25} "
            f"{stats['correct']:>3}/"
            f"{stats['total']:<3} "
            f"= "
            f"{stats['accuracy'] * 100:6.2f}%"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print(
        "Поиск официального датасета..."
    )

    ocr_files = collect_ocr_files()
    xml_files = collect_xml_files()

    print(
        f"Найдено PDF OCR: "
        f"{len(ocr_files)}"
    )

    print(
        f"Найдено XML: "
        f"{len(xml_files)}"
    )

    ocr_labels = read_csv_rows(
        OCR_LABELS
    )

    xml_labels = read_csv_rows(
        XML_LABELS
    )

    print(
        f"Строк OCR labels: "
        f"{len(ocr_labels)}"
    )

    print(
        f"Строк XML labels: "
        f"{len(xml_labels)}"
    )

    # ========================================================
    # OCR
    # ========================================================

    ocr_results = []

    print()
    print(
        "=" * 70
    )
    print(
        "OCR/PDF"
    )
    print(
        "=" * 70
    )

    for index, row in enumerate(
        ocr_labels,
        start=1,
    ):

        relative_path = row[
            "Файл"
        ].replace(
            "\\",
            "/",
        )

        filename = Path(
            relative_path
        ).name

        if (
            SMOKE_TEST
            and filename
            not in SMOKE_OCR_FILES
        ):
            continue

        path = ocr_files.get(
            filename
        )

        if path is None:

            print(
                f"[MISS] {filename}"
            )

            continue

        print(
            f"[{index:02}] "
            f"{filename}"
        )

        result = evaluate_document(
            path,
            row,
            OCR_FIELD_MAP,
        )

        ocr_results.append(
            result
        )

        incorrect = [
            field_name
            for field_name, info
            in result[
                "field_results"
            ].items()
            if not info[
                "correct"
            ]
        ]

        print(
            f"     time="
            f"{result['elapsed_seconds']}s "
            f"errors="
            f"{len(incorrect)}"
        )

        if incorrect:
            print(
                "     "
                + ", ".join(
                    incorrect
                )
            )

    # ========================================================
    # XML
    # ========================================================

    xml_results = []

    print()
    print(
        "=" * 70
    )
    print(
        "XML ФССП"
    )
    print(
        "=" * 70
    )

    for index, row in enumerate(
        xml_labels,
        start=1,
    ):

        filename = Path(
            row[
                "FileName"
            ]
        ).name

        if (
            SMOKE_TEST
            and filename
            not in SMOKE_XML_FILES
        ):
            continue

        path = xml_files.get(
            filename
        )

        if path is None:

            print(
                f"[MISS] {filename}"
            )

            continue

        print(
            f"[{index:02}] "
            f"{filename}"
        )

        result = evaluate_document(
            path,
            row,
            XML_FIELD_MAP,
        )

        xml_results.append(
            result
        )

        incorrect = [
            field_name
            for field_name, info
            in result[
                "field_results"
            ].items()
            if not info[
                "correct"
            ]
        ]

        print(
            f"     time="
            f"{result['elapsed_seconds']}s "
            f"errors="
            f"{len(incorrect)}"
        )

        if incorrect:
            print(
                "     "
                + ", ".join(
                    incorrect
                )
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    ocr_summary = build_summary(
        ocr_results
    )

    xml_summary = build_summary(
        xml_results
    )

    print_summary(
        "OCR/PDF SUMMARY",
        ocr_summary,
    )

    print_summary(
        "XML SUMMARY",
        xml_summary,
    )

    # ========================================================
    # SAVE
    # ========================================================

    write_jsonl(
        OUTPUT_DIR
        / "ocr_results.jsonl",
        ocr_results,
    )

    write_jsonl(
        OUTPUT_DIR
        / "xml_results.jsonl",
        xml_results,
    )

    write_errors_csv(
        OUTPUT_DIR
        / "ocr_errors.csv",
        ocr_results,
    )

    write_errors_csv(
        OUTPUT_DIR
        / "xml_errors.csv",
        xml_results,
    )

    summary = {
        "smoke_test":
            SMOKE_TEST,
        "ocr":
            ocr_summary,
        "xml":
            xml_summary,
    }

    with (
        OUTPUT_DIR
        / "summary.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "Результаты сохранены:"
    )

    print(
        OUTPUT_DIR
    )


if __name__ == "__main__":
    main()