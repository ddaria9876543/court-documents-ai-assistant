FROM apache/airflow:2.10.5-python3.11

USER root

RUN python -m venv /opt/dq-venv \
    && /opt/dq-venv/bin/pip install --no-cache-dir \
        "sqlalchemy>=2.0,<3.0" \
        "psycopg2-binary>=2.9" \
        "pydantic>=2.0" \
        "pydantic-settings>=2.0"

USER airflow

RUN pip install --no-cache-dir \
    dbt-postgres==1.9.0