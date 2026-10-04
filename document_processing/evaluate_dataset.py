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


# Официальный датасет организаторов
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
# РЕЖИМ ПРОГОНА
# ============================================================

# Сначала обязательно True.
# После smoke-test поменяем на False.
SMOKE_TEST = False

SMOKE_OCR_FILES = {
    "ocr_006.pdf",
    "ocr_013.pdf",
    "ocr_015.pdf",
    "ocr_021.pdf",
}

SMOKE_XML_FILES = set()


# ============================================================
# СОПОСТАВЛЕНИЕ ЭТАЛОНА ОРГАНИЗАТОРОВ
# С НАШИМИ ПОЛЯМИ
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
    # В официальной таблице именно такое название.
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

CRITICAL_OCR_FIELDS = {
    "тип документа",
    "фио",
    "дело_номер",
    "дело_дата",
    "дз_осн",
}

CRITICAL_XML_FIELDS = {
    "IdDeloNo",
    "IdDeloDate",
    "IpNo",
    "DbtrName",
    "rub_deb",
}


# ============================================================
# ЧТЕНИЕ LABELS
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
# ПОИСК ДОКУМЕНТОВ
# ============================================================

def collect_ocr_files() -> dict[str, Path]:

    files: dict[str, Path] = {}

    for root in [
        PART1 / "ocr",
        PART2 / "ocr",
    ]:
        if not root.exists():
            continue

        for path in root.rglob("*.pdf"):
            files[path.name] = path

    return files


def collect_xml_files() -> dict[str, Path]:

    root = PART3 / "fssp"

    if not root.exists():
        return {}

    return {
        path.name: path
        for path in root.rglob("*.xml")
    }


def detect_source_group(
    path: Path,
) -> str:

    if path.suffix.lower() == ".xml":
        return "xml"

    path_text = str(path).lower()

    if "electronic" in path_text:
        return "text_pdf"

    return "scan_pdf"


# ============================================================
# РЕЗУЛЬТАТ PIPELINE
# ============================================================

def unwrap_value(
    value: Any,
) -> Any:

    if isinstance(value, dict):
        if "value" in value:
            return value.get("value")

    return value


def get_prediction(
    result: dict[str, Any],
    aliases: list[str],
) -> Any:

    for alias in aliases:

        if alias in result:
            value = unwrap_value(
                result.get(alias)
            )

            if value is not None:
                return value

        fields = result.get(
            "fields",
            {}
        )

        if isinstance(fields, dict):
            if alias in fields:
                value = unwrap_value(
                    fields.get(alias)
                )

                if value is not None:
                    return value

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

def normalize_address(
    value: Any,
) -> str | None:

    text = normalize_text(value)

    if text is None:
        return None

    # Унифицируем служебные обозначения.
    text = re.sub(
        r"\bулица\b",
        " ",
        text,
    )

    text = re.sub(
        r"\bул\.?\b",
        " ",
        text,
    )

    text = re.sub(
        r"\bгород\b",
        " ",
        text,
    )

    text = re.sub(
        r"\bг\.?\b",
        " ",
        text,
    )

    # 22-я -> 22
    # 22ая -> 22
    text = re.sub(
        r"\b(\d+)[-\s]?(?:я|ая|ый|ой)\b",
        r"\1",
        text,
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

    # Порядок компонентов улицы
    # при сравнении не учитываем.
    parts = sorted(
        text.split()
    )

    return " ".join(parts)
def normalize_house(
    value: Any,
) -> str | None:

    text = normalize_text(value)

    if text is None:
        return None

    text = re.sub(
        r"^\s*д\.?\s*",
        "",
        text,
    )

    text = (
        text
        .replace(" ", "")
        .replace("/", "")
        .replace("\\", "")
        .lower()
    )

    return text or None


def normalize_apartment(
    value: Any,
) -> str | None:

    text = normalize_text(value)

    if text is None:
        return None

    text = re.sub(
        r"^\s*кв\.?\s*",
        "",
        text,
    )

    text = (
        text
        .replace(",", "")
        .replace(".", "")
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text or None
def normalize_person_list(
    value: Any,
) -> list[tuple[str, ...]] | None:

    value = normalize_empty(
        value
    )

    if value is None:
        return None

    text = str(value)

    text = (
        text
        .replace("ё", "е")
        .replace("Ё", "Е")
        .lower()
        .replace(";", ",")
    )

    def normalize_name_word(
        word: str,
    ) -> str:

        word = word.strip()

        endings = [
            "ого",
            "ему",
            "ому",
            "ыми",
            "ими",
            "ой",
            "ей",
            "ая",
            "яя",
            "ия",
            "ии",
            "ых",
            "их",
            "а",
            "я",
            "у",
            "ю",
            "ы",
            "и",
            "е",
        ]

        for ending in endings:
            if (
                word.endswith(ending)
                and len(word) - len(ending) >= 3
            ):
                return word[
                    :-len(ending)
                ]

        return word

    persons = []

    for person in text.split(","):

        person = re.sub(
            r"[^а-яa-z\s-]",
            " ",
            person,
        )

        words = [
            normalize_name_word(word)
            for word in re.split(
                r"\s+",
                person.strip(),
            )
            if word
        ]

        if not words:
            continue

        signature = tuple(
            word[:5]
            for word in words
        )

        persons.append(
            signature
        )

    return sorted(persons) or None
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
        .replace("\xa0", "")
        .replace(" ", "")
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

    # Судебный приказ
    if "приказ" in text:
        return "судебный приказ"

    # Исполнительный лист
    if (
        text == "ил"
        or text.startswith("ил ")
        or "исполнительн" in text
        and "лист" in text
    ):
        return "исполнительный лист"

    # Постановление ФССП
    if (
        "фссп" in text
        or "постановлен" in text
    ):
        return "постановление фссп"

    return text

def normalize_for_field(
    field_name: str,
    value: Any,
) -> Any:

    if field_name == "тип документа":
        return normalize_document_type(
            value
        )

    if field_name in {
        "улица",
        "street",
    }:
        return normalize_address(
            value
        )
    if field_name == "соответчики_фио":
        return normalize_person_list(
            value
        )
    if field_name in {
        "дом",
        "dom",
    }:
        return normalize_house(
            value
        )

    if field_name in {
        "кв",
        "kv",
    }:
        return normalize_apartment(
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

    return expected_n == predicted_n


# ============================================================
# ОЦЕНКА ОДНОГО ДОКУМЕНТА
# ============================================================

def evaluate_document(
    path: Path,
    label_row: dict[str, str],
    field_map: dict[str, list[str]],
) -> dict[str, Any]:

    started = time.time()

    try:
        raw_result = (
            process_document_official(
                str(path)
            )
        )

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
                "Unsupported pipeline result: "
                f"{type(raw_result).__name__}"
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

    return {
        "filename": path.name,
        "source_group":
            detect_source_group(path),
        "elapsed_seconds": elapsed,
        "processing_error":
            processing_error,
        "field_results":
            field_results,
        "raw_result":
            result,
    }


# ============================================================
# МЕТРИКИ
# ============================================================

def build_summary(
    results: list[dict[str, Any]],
    critical_fields: set[str],
) -> dict[str, Any]:

    field_stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
        }
    )

    group_stats = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
            "documents": 0,
        }
    )

    processing_errors = 0
    total_seconds = 0.0

    documents_without_critical_error = 0

    for item in results:

        total_seconds += (
            item["elapsed_seconds"]
        )

        if item["processing_error"]:
            processing_errors += 1

        group = item["source_group"]

        group_stats[group][
            "documents"
        ] += 1

        critical_ok = True

        for field_name, info in (
            item[
                "field_results"
            ].items()
        ):

            field_stats[
                field_name
            ]["total"] += 1

            group_stats[
                group
            ]["total"] += 1

            if info["correct"]:
                field_stats[
                    field_name
                ]["correct"] += 1

                group_stats[
                    group
                ]["correct"] += 1

            elif field_name in critical_fields:
                critical_ok = False

        if critical_ok:
            documents_without_critical_error += 1

    total_correct = 0
    total_fields = 0

    field_accuracy = {}

    for field_name, stats in (
        field_stats.items()
    ):

        correct = stats["correct"]
        total = stats["total"]

        accuracy = (
            correct / total
            if total
            else 0
        )

        field_accuracy[
            field_name
        ] = {
            "correct": correct,
            "total": total,
            "accuracy": round(
                accuracy,
                4,
            ),
        }

        total_correct += correct
        total_fields += total

    source_accuracy = {}

    for group, stats in (
        group_stats.items()
    ):

        accuracy = (
            stats["correct"]
            / stats["total"]
            if stats["total"]
            else 0
        )

        source_accuracy[group] = {
            **stats,
            "accuracy": round(
                accuracy,
                4,
            ),
        }

    overall_accuracy = (
        total_correct / total_fields
        if total_fields
        else 0
    )

    critical_document_accuracy = (
        documents_without_critical_error
        / len(results)
        if results
        else 0
    )

    return {
        "documents": len(results),
        "processing_errors":
            processing_errors,
        "total_seconds":
            round(total_seconds, 2),
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
        "documents_without_critical_error":
            documents_without_critical_error,
        "critical_document_accuracy":
            round(
                critical_document_accuracy,
                4,
            ),
        "field_accuracy":
            field_accuracy,
        "source_accuracy":
            source_accuracy,
    }


# ============================================================
# СОХРАНЕНИЕ
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
                        item["filename"],
                    "source_group":
                        item[
                            "source_group"
                        ],
                    "field":
                        "__PROCESSING__",
                    "expected": "",
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
                        "source_group":
                            item[
                                "source_group"
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
                "source_group",
                "field",
                "expected",
                "predicted",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)


def write_field_metrics_csv(
    path: Path,
    ocr_summary: dict[str, Any],
    xml_summary: dict[str, Any],
) -> None:

    rows = []

    for dataset_name, summary in [
        ("OCR/PDF", ocr_summary),
        ("XML", xml_summary),
    ]:
        for field_name, stats in (
            summary[
                "field_accuracy"
            ].items()
        ):
            rows.append(
                {
                    "dataset":
                        dataset_name,
                    "field":
                        field_name,
                    "correct":
                        stats["correct"],
                    "total":
                        stats["total"],
                    "accuracy_percent":
                        round(
                            stats[
                                "accuracy"
                            ] * 100,
                            2,
                        ),
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
                "dataset",
                "field",
                "correct",
                "total",
                "accuracy_percent",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# ПЕЧАТЬ
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
        f"Среднее время: "
        f"{summary['average_seconds']} сек."
    )

    print(
        f"Общая точность полей: "
        f"{summary['overall_accuracy'] * 100:.2f}%"
    )

    print(
        "Документов без критической ошибки: "
        f"{summary['documents_without_critical_error']}/"
        f"{summary['documents']} "
        f"("
        f"{summary['critical_document_accuracy'] * 100:.2f}%"
        f")"
    )

    print()
    print("По типу источника:")

    for group, stats in (
        summary[
            "source_accuracy"
        ].items()
    ):
        print(
            f"  {group:15} "
            f"{stats['accuracy'] * 100:6.2f}% "
            f"({stats['documents']} документов)"
        )

    print()
    print("Точность по полям:")

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

    if not OCR_LABELS.exists():
        raise FileNotFoundError(
            f"Не найден OCR labels: "
            f"{OCR_LABELS}"
        )

    if not XML_LABELS.exists():
        raise FileNotFoundError(
            f"Не найден XML labels: "
            f"{XML_LABELS}"
        )

    ocr_files = collect_ocr_files()
    xml_files = collect_xml_files()

    ocr_labels = read_csv_rows(
        OCR_LABELS
    )

    xml_labels = read_csv_rows(
        XML_LABELS
    )

    print(
        f"Найдено PDF: "
        f"{len(ocr_files)}"
    )

    print(
        f"Найдено XML: "
        f"{len(xml_files)}"
    )

    print(
        f"OCR labels: "
        f"{len(ocr_labels)}"
    )

    print(
        f"XML labels: "
        f"{len(xml_labels)}"
    )

    # ========================================================
    # PDF
    # ========================================================

    ocr_results = []

    print()
    print("=" * 70)
    print("OCR/PDF")
    print("=" * 70)

    for index, row in enumerate(
        ocr_labels,
        start=1,
    ):

        filename = Path(
            row["Файл"].replace(
                "\\",
                "/",
            )
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
            if not info["correct"]
        ]

        print(
            f"     "
            f"time={result['elapsed_seconds']}s "
            f"errors={len(incorrect)}"
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
    print("=" * 70)
    print("XML ФССП")
    print("=" * 70)

    for index, row in enumerate(
        xml_labels,
        start=1,
    ):

        filename = Path(
            row["FileName"]
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
            if not info["correct"]
        ]

        print(
            f"     "
            f"time={result['elapsed_seconds']}s "
            f"errors={len(incorrect)}"
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
        ocr_results,
        CRITICAL_OCR_FIELDS,
    )

    xml_summary = build_summary(
        xml_results,
        CRITICAL_XML_FIELDS,
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

    write_field_metrics_csv(
        OUTPUT_DIR
        / "field_metrics.csv",
        ocr_summary,
        xml_summary,
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
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        "Результаты сохранены в:"
    )

    print(
        OUTPUT_DIR
    )


if __name__ == "__main__":
    main()