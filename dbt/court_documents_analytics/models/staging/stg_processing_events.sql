select
    id as event_id,
    document_id,
    attempt,
    event_type,
    status,
    started_at,
    finished_at,
    duration_ms,
    error_type,
    error_message,
    worker_name,
    model_name,
    created_at

from {{ source('court_docs', 'processing_events') }}