import os
from datetime import datetime, timedelta

from airflow import DAG

try:
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:
    from airflow.operators.bash import BashOperator


PROJECT_ROOT = os.getenv(
    "PROJECT_ROOT",
    "/opt/project",
)

DBT_PROJECT_DIR = os.path.join(
    PROJECT_ROOT,
    "dbt",
    "court_documents_analytics",
)


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="document_analytics_pipeline",
    description=(
        "DQ checks, dbt transformations "
        "and ClickHouse mart synchronization"
    ),
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=[
        "court-documents",
        "data-quality",
        "dbt",
        "clickhouse",
    ],
) as dag:

    run_python_dq = BashOperator(
        task_id="run_python_dq",
        bash_command=(
            f"cd {PROJECT_ROOT}/backend "
            "&& /opt/dq-venv/bin/python run_dq_checks.py"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} "
            "&& dbt build"
        ),
    )

    sync_clickhouse = BashOperator(
        task_id="sync_clickhouse",
        bash_command=(
            f"cd {PROJECT_ROOT} "
            "&& /opt/dq-venv/bin/python "
            "clickhouse/sync_marts.py"
        ),
        env={
            "CLICKHOUSE_URL": (
                "http://host.docker.internal:8123"
            ),
            "CLICKHOUSE_USER": "analytics",
            "CLICKHOUSE_PASSWORD": "analytics_dev",
            "POSTGRES_HOST": (
                "host.docker.internal:55432"
            ),
            "POSTGRES_DB": "court_docs",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "postgres",
        },
    )

    run_python_dq >> dbt_build >> sync_clickhouse