import os
import urllib.parse
import urllib.request


CLICKHOUSE_URL = os.getenv(
    "CLICKHOUSE_URL",
    "http://127.0.0.1:8123",
)

CLICKHOUSE_USER = os.getenv(
    "CLICKHOUSE_USER",
    "analytics",
)

CLICKHOUSE_PASSWORD = os.getenv(
    "CLICKHOUSE_PASSWORD",
    "analytics_dev",
)

POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "host.docker.internal:55432",
)

POSTGRES_DB = os.getenv(
    "POSTGRES_DB",
    "court_docs",
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
    "postgres",
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "postgres",
)

POSTGRES_SCHEMA = "analytics"
CLICKHOUSE_DATABASE = "court_docs_analytics"


MARTS = [
    "mart_document_processing_daily",
    "mart_document_quality",
    "mart_document_types",
    "mart_legal_actions",
]


def execute_clickhouse_query(
    query: str,
) -> str:
    params = urllib.parse.urlencode(
        {
            "user": CLICKHOUSE_USER,
            "password": CLICKHOUSE_PASSWORD,
            "query": query,
        }
    )

    url = f"{CLICKHOUSE_URL}/?{params}"

    request = urllib.request.Request(
        url=url,
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:
        return response.read().decode(
            "utf-8"
        )


def sync_mart(
    table_name: str,
) -> None:
    print(
        f"[clickhouse] Syncing "
        f"{table_name}..."
    )

    execute_clickhouse_query(
        f"""
        TRUNCATE TABLE
        {CLICKHOUSE_DATABASE}.{table_name}
        """
    )

    execute_clickhouse_query(
        f"""
        INSERT INTO
        {CLICKHOUSE_DATABASE}.{table_name}
        SELECT *
        FROM postgresql(
            '{POSTGRES_HOST}',
            '{POSTGRES_DB}',
            '{table_name}',
            '{POSTGRES_USER}',
            '{POSTGRES_PASSWORD}',
            '{POSTGRES_SCHEMA}'
        )
        """
    )

    result = execute_clickhouse_query(
        f"""
        SELECT count()
        FROM
        {CLICKHOUSE_DATABASE}.{table_name}
        """
    )

    print(
        f"[clickhouse] {table_name}: "
        f"{result.strip()} rows"
    )


def main() -> None:
    for mart in MARTS:
        sync_mart(
            mart
        )

    print(
        "[clickhouse] Sync completed successfully"
    )


if __name__ == "__main__":
    main()