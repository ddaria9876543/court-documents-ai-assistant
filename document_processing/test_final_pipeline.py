import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

from pipeline import process_document_official


def run_test(file_path: Path) -> dict:
    print("\n" + "=" * 70)
    print(f"ОБРАБОТКА: {file_path.name}")
    print("=" * 70)

    fields = process_document_official(file_path)
    result = fields.model_dump()

    print(fields.model_dump_json(indent=2))
    print("\nSTATUS:", fields.status)

    if fields.warnings:
        print("WARNINGS:")
        for warning in fields.warnings:
            print("-", warning)

    return {
        "file": file_path.name,
        "result": result,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Smoke-тест document processing pipeline"
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="Пути к PDF/XML документам",
    )

    parser.add_argument(
        "--output",
        default="data/final_smoke_test_results.json",
        help="Файл для сохранения результатов",
    )

    args = parser.parse_args()

    results = []

    for path in args.files:
        file_path = Path(path)

        if not file_path.exists():
            print(f"Файл не найден: {file_path}")
            continue

        results.append(
            run_test(file_path)
        )

    output_path = Path(args.output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\n" + "=" * 70)
    print("FINAL SMOKE TEST ЗАВЕРШЁН")
    print("=" * 70)
    print("Результаты сохранены:", output_path)


if __name__ == "__main__":
    main()