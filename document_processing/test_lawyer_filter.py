from pathlib import Path

import pymupdf

from src.lawyer_filter import analyze_lawyer_markers


PDF_DIR = Path(
    r"C:\Users\baigina\pomoshchnik-dlya-analiza-dokumentov-iz-sudov-ocr-i-izvlechenie-dannykh"
    r"\document_processing\data\court_markers"
)


def extract_text_from_pdf(pdf_path: Path) -> str:
    document = pymupdf.open(pdf_path)

    pages = []

    for page in document:
        pages.append(page.get_text("text"))

    document.close()

    return "\n".join(pages)


def main():
    pdf_files = sorted(PDF_DIR.glob("Акт_*.pdf"))

    if not pdf_files:
        print(f"PDF не найдены: {PDF_DIR}")
        return

    print(f"Найдено PDF: {len(pdf_files)}")
    print("=" * 100)

    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)

        result = analyze_lawyer_markers(text)

        print(f"\nФАЙЛ: {pdf_path.name}")
        print(f"Требуется юрист: {result['requires_lawyer']}")

        if result["matched_markers"]:
            print("Найденные маркеры:")

            for marker in result["matched_markers"]:
                print(f"  - {marker}")

            print("Совпадения:")

            for match in result["matches"]:
                print(
                    f"  [{match['source']}] "
                    f"{match['marker']}"
                )
                print(
                    f"  Фрагмент: {match['fragment']}"
                )

        else:
            print("Маркеры НЕ найдены")

        print("-" * 100)


if __name__ == "__main__":
    main()