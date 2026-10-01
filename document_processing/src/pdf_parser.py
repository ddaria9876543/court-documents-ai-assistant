from pathlib import Path
import subprocess
import shutil
import tempfile
import os
import re

import cv2
import numpy as np
import pymupdf

from field_extractor import extract_fields


BASE_DIR = Path(__file__).resolve().parent.parent

TESSERACT_PATH = (
    os.environ.get("TESSERACT_PATH")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

TESSDATA_PATH = str(
    BASE_DIR / "models" / "tessdata"
)

OCR_DPI = 300

PSM_PRIMARY = 4
PSM_FALLBACK = 6

HEADER_PSM_MODES = (6, 11)

WEAK_OCR_SCORE = 25.0


DATE_RE = re.compile(
    r"\b\d{1,2}\.\d{2}\.\d{4}\b"
)

CASE_NUMBER_RE = re.compile(
    r"\b\d+-\d+/\d{4}\b"
)

INN_RE = re.compile(
    r"\bИНН\s*[:№]?\s*(?:\d{10}|\d{12})\b",
    re.IGNORECASE
)

MONEY_RE = re.compile(
    r"\d+[.,]\d{2}\s*руб",
    re.IGNORECASE
)

DEBTOR_LINE_RE = re.compile(
    r"[А-ЯЁ][а-яё]+ "
    r"[А-ЯЁ][а-яё]+ "
    r"[А-ЯЁ][а-яё]+,\s*"
    r"\d{2}\.\d{2}\.\d{4}"
)

GARBAGE_CHAR_RE = re.compile(
    r"[|_=~]"
)

OCR_KEYWORDS = (
    "исполнительный лист",
    "взыскатель",
    "должник",
    "взыскать",
    "судебный акт",
)


def render_page(
    page,
    dpi: int = OCR_DPI
) -> np.ndarray:

    pix = page.get_pixmap(
        dpi=dpi,
        alpha=False
    )

    image = np.frombuffer(
        pix.samples,
        dtype=np.uint8
    ).reshape(
        pix.height,
        pix.width,
        pix.n
    )

    return image


def preprocess_image(
    image: np.ndarray
) -> np.ndarray:

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_RGB2GRAY
    )

    return gray


def run_tesseract(
    image: np.ndarray,
    psm: int
) -> str:

    with tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False
    ) as temp_file:

        image_path = temp_file.name

    try:
        cv2.imwrite(
            image_path,
            image
        )

        command = [
            TESSERACT_PATH,
            image_path,
            "stdout",
            "-l",
            "rus",
            "--tessdata-dir",
            TESSDATA_PATH,
            "--dpi",
            str(OCR_DPI),
            "--psm",
            str(psm)
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            stderr = (
                result.stderr or ""
            ).strip()

            raise RuntimeError(
                "Tesseract завершился с ошибкой "
                f"(returncode={result.returncode}, "
                f"psm={psm}): {stderr}"
            )

        return result.stdout.strip()

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def crop_header_region(
    image: np.ndarray
) -> np.ndarray:
    """
    Берём верхнюю часть первой страницы.

    В исполнительных листах номер дела может находиться
    выше подписи 'Дело №', поэтому не пытаемся искать
    координаты самой подписи.
    """

    height, width = image.shape[:2]

    header_height = int(
        height * 0.35
    )

    header = image[
        0:header_height,
        0:width
    ]

    # Увеличиваем только локальную область.
    # Это помогает Tesseract различать цифры и дефисы.
    header = cv2.resize(
        header,
        None,
        fx=1.5,
        fy=1.5,
        interpolation=cv2.INTER_CUBIC
    )

    return header


def find_case_number(
    text: str
) -> str | None:

    match = CASE_NUMBER_RE.search(
        text
    )

    if not match:
        return None

    return match.group(0)


def recover_case_number_from_header(
    image: np.ndarray
) -> dict:
    """
    Дополнительный OCR шапки первой страницы.

    Выполняется только если основной OCR не смог
    извлечь номер дела.
    """

    header = crop_header_region(
        image
    )

    attempts = []

    for psm in HEADER_PSM_MODES:

        print(
            f"  OCR шапки PSM {psm}"
        )

        text = run_tesseract(
            header,
            psm
        )

        case_number = find_case_number(
            text
        )

        attempts.append(
            {
                "psm": psm,
                "text": text,
                "case_number": case_number,
            }
        )

        # Как только получили нормальный номер,
        # дальнейшие режимы не нужны.
        if case_number:
            return {
                "case_number": case_number,
                "psm": psm,
                "text": text,
                "attempts": attempts,
            }

    return {
        "case_number": None,
        "psm": None,
        "text": "",
        "attempts": attempts,
    }


def score_ocr_result(
    text: str
) -> float:

    if not text or not text.strip():
        return -100.0

    score = 0.0
    lower = text.lower()

    cyrillic_count = len(
        re.findall(
            r"[А-Яа-яЁё]",
            text
        )
    )

    digit_count = len(
        re.findall(
            r"\d",
            text
        )
    )

    if cyrillic_count >= 20:
        score += 15.0
    elif cyrillic_count >= 5:
        score += 5.0

    if digit_count >= 4:
        score += 8.0
    elif digit_count >= 1:
        score += 3.0

    score += (
        12.0
        * len(DATE_RE.findall(text))
    )

    score += (
        20.0
        * len(CASE_NUMBER_RE.findall(text))
    )

    score += (
        15.0
        * len(INN_RE.findall(text))
    )

    score += (
        8.0
        * len(MONEY_RE.findall(text))
    )

    score += (
        12.0
        * len(DEBTOR_LINE_RE.findall(text))
    )

    score += (
        10.0
        * sum(
            1
            for keyword in OCR_KEYWORDS
            if keyword in lower
        )
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if lines:
        short_ratio = (
            sum(
                1
                for line in lines
                if len(line) <= 2
            )
            / len(lines)
        )

        score -= (
            25.0
            * short_ratio
        )

    compact_chars = [
        char
        for char in text
        if not char.isspace()
    ]

    if compact_chars:
        garbage_ratio = (
            len(
                GARBAGE_CHAR_RE.findall(text)
            )
            / len(compact_chars)
        )

        score -= (
            40.0
            * garbage_ratio
        )

        letter_count = sum(
            1
            for char in compact_chars
            if char.isalpha()
        )

        non_letter_ratio = (
            1.0
            - (
                letter_count
                / len(compact_chars)
            )
        )

        if non_letter_ratio > 0.55:
            score -= 20.0
        elif non_letter_ratio > 0.4:
            score -= 10.0

    tokens = re.findall(
        r"\S+",
        text
    )

    if tokens:
        single_ratio = (
            sum(
                1
                for token in tokens
                if len(token) == 1
            )
            / len(tokens)
        )

        score -= (
            15.0
            * single_ratio
        )

    return score


def score_extracted_fields(
    fields: dict
) -> float:

    score = 0.0

    if fields.get("document_type"):
        score += 15.0

    if fields.get("case_number"):
        score += 20.0

    if fields.get("effective_date"):
        score += 15.0

    if fields.get("creditor"):
        score += 20.0

    if fields.get("creditor_inn"):
        score += 20.0

    debtors = (
        fields.get("debtors")
        or []
    )

    score += (
        25.0
        * len(debtors)
    )

    if fields.get("debt_amount"):
        score += 15.0

    if fields.get("penalty_amount"):
        score += 15.0

    if fields.get("state_duty"):
        score += 15.0

    return score


def should_run_fallback(
    text: str,
    ocr_score: float,
    fields: dict
) -> bool:

    if ocr_score < WEAK_OCR_SCORE:
        return True

    lower = text.lower()

    if (
        "взыскатель" in lower
        or "должник" in lower
    ):
        return True

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if lines:
        short_ratio = (
            sum(
                1
                for line in lines
                if len(line) <= 2
            )
            / len(lines)
        )

        if short_ratio > 0.4:
            return True

    compact_chars = [
        char
        for char in text
        if not char.isspace()
    ]

    if compact_chars:
        garbage_ratio = (
            len(
                GARBAGE_CHAR_RE.findall(text)
            )
            / len(compact_chars)
        )

        if garbage_ratio > 0.08:
            return True

    if (
        "исполнительный лист" in lower
        and not fields.get("case_number")
    ):
        return True

    return False


def choose_best_result(
    text_primary: str,
    text_fallback: str,
    ocr_score_primary: float,
    ocr_score_fallback: float,
) -> tuple:

    fields_primary = extract_fields(
        text_primary
    )

    fields_fallback = extract_fields(
        text_fallback
    )

    field_score_primary = (
        score_extracted_fields(
            fields_primary
        )
    )

    field_score_fallback = (
        score_extracted_fields(
            fields_fallback
        )
    )

    if (
        field_score_fallback
        > field_score_primary
    ):
        return (
            PSM_FALLBACK,
            text_fallback,
            ocr_score_fallback,
            field_score_fallback,
            fields_fallback
        )

    if (
        field_score_primary
        > field_score_fallback
    ):
        return (
            PSM_PRIMARY,
            text_primary,
            ocr_score_primary,
            field_score_primary,
            fields_primary
        )

    if (
        ocr_score_fallback
        > ocr_score_primary
    ):
        return (
            PSM_FALLBACK,
            text_fallback,
            ocr_score_fallback,
            field_score_fallback,
            fields_fallback
        )

    return (
        PSM_PRIMARY,
        text_primary,
        ocr_score_primary,
        field_score_primary,
        fields_primary
    )


def ocr_pdf(
    pdf_path: str
) -> list[dict]:

    document = pymupdf.open(
        pdf_path
    )

    useful_pages = [
        1,
        3,
        5,
        7
    ]

    result = []

    for page_number in useful_pages:

        print(
            f"Обработка страницы "
            f"{page_number}"
        )

        page = document[
            page_number - 1
        ]

        image = render_page(
            page
        )

        image = preprocess_image(
            image
        )

        print(
            f"  OCR PSM "
            f"{PSM_PRIMARY}"
        )

        text_primary = run_tesseract(
            image,
            PSM_PRIMARY
        )

        ocr_score_primary = (
            score_ocr_result(
                text_primary
            )
        )

        fields_primary = (
            extract_fields(
                text_primary
            )
        )

        field_score_primary = (
            score_extracted_fields(
                fields_primary
            )
        )

        chosen_psm = PSM_PRIMARY
        chosen_text = text_primary
        chosen_ocr_score = (
            ocr_score_primary
        )
        chosen_field_score = (
            field_score_primary
        )

        ocr_score_fallback = None
        field_score_fallback = None

        run_fallback = (
            should_run_fallback(
                text_primary,
                ocr_score_primary,
                fields_primary
            )
        )

        if run_fallback:

            print(
                f"  OCR PSM "
                f"{PSM_FALLBACK} "
                f"(fallback)"
            )

            text_fallback = (
                run_tesseract(
                    image,
                    PSM_FALLBACK
                )
            )

            ocr_score_fallback = (
                score_ocr_result(
                    text_fallback
                )
            )

            fields_fallback = (
                extract_fields(
                    text_fallback
                )
            )

            field_score_fallback = (
                score_extracted_fields(
                    fields_fallback
                )
            )

            (
                chosen_psm,
                chosen_text,
                chosen_ocr_score,
                chosen_field_score,
                _
            ) = choose_best_result(
                text_primary,
                text_fallback,
                ocr_score_primary,
                ocr_score_fallback
            )

        recovered_case_number = None
        header_ocr_psm = None
        header_ocr_attempts = []

        # Зонный OCR делаем только на первой странице
        # и только если обычный OCR не нашёл номер дела.
        if page_number == 1:

            chosen_fields = extract_fields(
                chosen_text
            )

            if not chosen_fields.get(
                "case_number"
            ):

                print(
                    "  Номер дела не найден — "
                    "запускаю OCR шапки"
                )

                header_result = (
                    recover_case_number_from_header(
                        image
                    )
                )

                recovered_case_number = (
                    header_result[
                        "case_number"
                    ]
                )

                header_ocr_psm = (
                    header_result[
                        "psm"
                    ]
                )

                header_ocr_attempts = (
                    header_result[
                        "attempts"
                    ]
                )

                if recovered_case_number:

                    print(
                        "  Номер дела восстановлен: "
                        f"{recovered_case_number}"
                    )

                    # Добавляем только найденный номер,
                    # а не весь дополнительный OCR-текст.
                    chosen_text = (
                        recovered_case_number
                        + "\n"
                        + chosen_text
                    )

                else:
                    print(
                        "  Номер дела в шапке "
                        "тоже не найден"
                    )

        result.append(
            {
                "page": page_number,
                "psm": chosen_psm,
                "text": chosen_text,

                "ocr_score":
                    chosen_ocr_score,

                "field_score":
                    chosen_field_score,

                "ocr_score_psm4":
                    ocr_score_primary,

                "ocr_score_psm6":
                    ocr_score_fallback,

                "field_score_psm4":
                    field_score_primary,

                "field_score_psm6":
                    field_score_fallback,

                "recovered_case_number":
                    recovered_case_number,

                "header_ocr_psm":
                    header_ocr_psm,

                "header_ocr_attempts":
                    header_ocr_attempts,
            }
        )

    document.close()

    return result


def build_report(
    pdf_path: Path,
    pages: list[dict]
) -> str:

    report_lines = []

    for page in pages:

        report_lines.extend(
            [
                "=" * 60,
                f"PAGE {page['page']}",
                "=" * 60,

                (
                    "OCR score PSM 4: "
                    f"{page['ocr_score_psm4']:.2f}"
                ),

                (
                    "field score PSM 4: "
                    f"{page['field_score_psm4']:.2f}"
                ),
            ]
        )

        if (
            page["ocr_score_psm6"]
            is None
        ):
            report_lines.append(
                "PSM 6: не запускался"
            )

        else:
            report_lines.extend(
                [
                    (
                        "OCR score PSM 6: "
                        f"{page['ocr_score_psm6']:.2f}"
                    ),

                    (
                        "field score PSM 6: "
                        f"{page['field_score_psm6']:.2f}"
                    ),
                ]
            )

        report_lines.extend(
            [
                f"выбран PSM: {page['psm']}",

                (
                    "OCR score выбранного: "
                    f"{page['ocr_score']:.2f}"
                ),

                (
                    "field score выбранного: "
                    f"{page['field_score']:.2f}"
                ),
            ]
        )

        if page["page"] == 1:

            recovered = page[
                "recovered_case_number"
            ]

            if recovered:
                report_lines.append(
                    "номер дела восстановлен "
                    f"из шапки: {recovered}"
                )

                report_lines.append(
                    "PSM зонного OCR: "
                    f"{page['header_ocr_psm']}"
                )

            elif page[
                "header_ocr_attempts"
            ]:
                report_lines.append(
                    "зонный OCR запускался, "
                    "номер дела не найден"
                )

        report_lines.extend(
            [
                "",
                page["text"],
                "",
            ]
        )

    full_text = "\n".join(
        page["text"]
        for page in pages
    )

    fields = extract_fields(
        full_text
    )

    report_lines.extend(
        [
            "=" * 60,
            "ИЗВЛЕЧЕННЫЕ ПОЛЯ",
            "=" * 60,
        ]
    )

    for key, value in fields.items():
        report_lines.append(
            f"{key}: {value}"
        )

    return (
        "\n".join(
            report_lines
        ).rstrip()
        + "\n"
    )


if __name__ == "__main__":

    input_folder = Path(
        r".\data\raw_part2\courts_anonymized"
    )

    pdf_files = sorted(
        input_folder.rglob(
            "ocr_0*.pdf"
        )
    )

    for pdf_path in pdf_files:

        print(
            "\n"
            + "#" * 70
        )

        print(
            f"ОБРАБОТКА: "
            f"{pdf_path.name}"
        )

        print(
            "#" * 70
        )

        pages = ocr_pdf(
            str(pdf_path)
        )

        report = build_report(
            pdf_path,
            pages
        )

        output_path = Path(
            f"ocr_comparison_{pdf_path.stem}.txt"
        )

        output_path.write_text(
            report,
            encoding="utf-8"
        )

        print(
            "Диагностика сохранена: "
            f"{output_path}"
        )