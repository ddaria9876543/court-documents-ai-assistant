select
    id as document_id,
    status,
    document_type,
    case_number,
    summary,
    debtor,
    amount,
    needs_review,
    review_reason,
    requires_legal_action,
    legal_action_reason,
    evidence_fragment,
    extracted_data,
    created_at,
    updated_at

from {{ source('court_docs', 'documents') }}