select
    cast(created_at as date) as date,

    coalesce(
        document_type,
        'unknown'
    ) as document_type,

    count(*) as documents_total,

    count(*) filter (
        where requires_legal_action = true
    ) as requires_legal_action,

    count(*) filter (
        where document_status = 'sent'
    ) as sent_to_lawyer,

    sum(
        case
            when requires_legal_action = true
            then total_amount
            else 0
        end
    ) as total_debt_amount

from {{ ref('int_documents_enriched') }}

group by
    1,
    2