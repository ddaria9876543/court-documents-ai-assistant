from app.db.session import SessionLocal
from app.dq.checks import run_data_quality_checks


def main():
    db = SessionLocal()

    try:
        results = run_data_quality_checks(
            db
        )

        print()
        print("DATA QUALITY REPORT")
        print("=" * 80)

        failed_checks = 0

        for result in results:
            status = (
                "PASS"
                if result.passed
                else "FAIL"
            )

            print(
                f"{status:4} | "
                f"{result.check_name:40} | "
                f"failed_rows={result.failed_rows}"
            )

            print(
                f"       {result.description}"
            )

            if not result.passed:
                failed_checks += 1

        print("=" * 80)

        print(
            f"Checks total: {len(results)}"
        )

        print(
            f"Checks failed: {failed_checks}"
        )

        if failed_checks:
            raise SystemExit(1)

        print("DATA QUALITY PASSED")

    finally:
        db.close()


if __name__ == "__main__":
    main()