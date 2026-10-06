with latest_extraction as (

    select
        *,
        row_number() over (
            partition by document_id
            order by attempt desc
        ) as rn

    from {{ ref('stg_document_extractions') }}

),

latest_event as (

    select
        *,
        row_number() over (
            partition by document_id
            order by attempt desc, created_at desc
        ) as rn

    from {{ ref('stg_processing_events') }}

)

select
    d.document_id,
    d.status as document_status,
    d.document_type,
    d.case_number,
    d.debtor,
    d.amount,

    d.needs_review,
    d.review_reason,

    d.requires_legal_action,
    d.legal_action_reason,

    e.attempt as latest_attempt,
    e.case_date,
    e.debt_period_start,
    e.debt_period_end,

    e.full_name,
    e.birth_date,
    e.inn,
    e.snils,

    e.principal_debt,
    e.penalty_amount,
    e.state_duty,
    e.postal_cost,

    (
        coalesce(e.principal_debt, 0)
        + coalesce(e.penalty_amount, 0)
        + coalesce(e.state_duty, 0)
        + coalesce(e.postal_cost, 0)
    ) as total_amount,

    e.processing_status,
    e.missing_fields,
    e.warnings,

    e.model_name,
    e.processor_version,

    pe.event_type as latest_event_type,
    pe.status as latest_event_status,
    pe.duration_ms as latest_duration_ms,

    d.created_at,
    d.updated_at,
    e.processed_at

from {{ ref('stg_documents') }} d

left join latest_extraction e
    on d.document_id = e.document_id
    and e.rn = 1

left join latest_event pe
    on d.document_id = pe.document_id
    and pe.rn = 1