select
    cast(created_at as date) as date,

    count(*) as documents_total,

    count(*) filter (
        where needs_review = true
    ) as documents_with_quality_issues,

    count(*) filter (
        where processing_status is null
    ) as documents_without_extraction,

    round(
        100.0
        * count(*) filter (
            where needs_review = false
        )
        / nullif(count(*), 0),
        2
    ) as quality_rate

from {{ ref('int_documents_enriched') }}

group by 1