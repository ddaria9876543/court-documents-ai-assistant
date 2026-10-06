select
    coalesce(
        document_type,
        'unknown'
    ) as document_type,

    count(*) as documents_count,

    avg(total_amount) as avg_debt_amount,

    count(*) filter (
        where needs_review = true
    ) as review_count,

    round(
        100.0
        * count(*) filter (
            where needs_review = true
        )
        / nullif(count(*), 0),
        2
    ) as review_rate,

    count(*) filter (
        where document_status = 'error'
    ) as error_count,

    round(
        100.0
        * count(*) filter (
            where document_status = 'error'
        )
        / nullif(count(*), 0),
        2
    ) as error_rate

from {{ ref('int_documents_enriched') }}

group by 1