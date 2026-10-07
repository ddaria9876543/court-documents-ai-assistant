CREATE DATABASE IF NOT EXISTS court_docs_analytics;


CREATE TABLE IF NOT EXISTS court_docs_analytics.mart_document_processing_daily
(
    date Date,
    documents_received UInt64,
    documents_processed UInt64,
    documents_failed UInt64,
    documents_review UInt64,
    success_rate Nullable(Float64),
    avg_processing_time_ms Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY date;


CREATE TABLE IF NOT EXISTS court_docs_analytics.mart_document_quality
(
    date Date,
    documents_total UInt64,
    documents_with_quality_issues UInt64,
    documents_without_extraction UInt64,
    quality_rate Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY date;


CREATE TABLE IF NOT EXISTS court_docs_analytics.mart_document_types
(
    document_type String,
    documents_count UInt64,
    avg_debt_amount Nullable(Float64),
    review_count UInt64,
    review_rate Nullable(Float64),
    error_count UInt64,
    error_rate Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY document_type;


CREATE TABLE IF NOT EXISTS court_docs_analytics.mart_legal_actions
(
    date Date,
    document_type String,
    documents_total UInt64,
    requires_legal_action UInt64,
    sent_to_lawyer UInt64,
    total_debt_amount Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY (date, document_type);