select
    cast(created_at as date) as date,

    count(*) as documents_received,

    count(*) filter (
        where document_status = 'processed'
    ) as documents_processed,

    count(*) filter (
        where document_status = 'error'
    ) as documents_failed,

    count(*) filter (
        where needs_review = true
    ) as documents_review,

    round(
        100.0
        * count(*) filter (
            where document_status in ('processed', 'sent')
        )
        / nullif(count(*), 0),
        2
    ) as success_rate,

    avg(latest_duration_ms) as avg_processing_time_ms

from {{ ref('int_documents_enriched') }}

group by 1