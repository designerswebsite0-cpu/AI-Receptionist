"""Pure data — no engine imports, mirrors app.conversations.constants' pattern
so Alembic migrations and application code both depend on this cheaply.

Governance vocabulary (VISIBILITY, SOURCE_PRIORITY) comes from
RKPR_RAG_FINAL_DOCS/04_GOVERNANCE/Knowledge_Source_Register.xlsx's "Lists"
sheet. The register's own data doesn't always match its controlled
vocabulary exactly (e.g. prose like "Supplementary" appears in free-text
notes, not the priority column itself) — the governance importer
(app.knowledge.governance) normalizes and reports unmappable values rather
than the schema accepting extra values to paper over that.
"""

# text-embedding-3-large's native size is 3072, but pgvector's HNSW index
# has a hard 2000-dimension cap (discovered when 0013's migration failed
# against the live DB: "column cannot have more than 2000 dimensions for
# hnsw index"). OpenAI's embeddings API supports a `dimensions` parameter
# that truncates via Matryoshka representation learning with a small,
# well-documented quality cost — 1536 keeps most of text-embedding-3-large's
# quality advantage over text-embedding-3-small while fitting the index.
# app.knowledge.embeddings must pass dimensions=EMBEDDING_DIMENSIONS on
# every API call, not just rely on this constant for the column width.
EMBEDDING_DIMENSIONS = 1536

# --- knowledge_sources ------------------------------------------------------

SOURCE_TYPES = ("document", "website", "media", "dataset")

# guest: guest-facing retrieval eligible (subject to retrieval_enabled/status)
# staff: internal/staff-only, never guest-visible
# internal: operational/procedural, staff-only (kept distinct from `staff`
#   for dashboard filtering per the register's own Visibility column)
# archive: superseded content, retained for history, never retrieval_enabled
# template: packaging placeholders explicitly excluded from ingestion
VISIBILITY = ("guest", "staff", "internal", "archive", "template")

SOURCE_PRIORITY = ("critical", "high", "normal", "low")

SOURCE_STATUSES = ("draft", "active", "superseded", "archived", "rejected")

PROCESSING_STATUSES = (
    "pending",
    "extracting",
    "chunking",
    "embedding",
    "completed",
    "failed",
    "needs_review",
)

APPROVAL_STATUSES = ("pending", "approved", "rejected")

MALWARE_SCAN_STATUSES = ("pending", "clean", "infected", "unavailable", "unscanned_dev_only")

# --- knowledge_chunks --------------------------------------------------------

CHUNK_TYPES = (
    "room",
    "room_rate",
    "menu_item",
    "spa_treatment",
    "policy",
    "faq",
    "offer",
    "transfer_rate",
    "attraction",
    "payment_rule",
    "safety_rule",
    "directory_timing",
    "website_page",
    "media",
    "staff_procedure",
    "generic",
)

CHUNK_STATUSES = ("active", "superseded", "archived")

# --- knowledge_media ----------------------------------------------------------

MEDIA_RIGHTS_STATUSES = ("owned", "licensed", "unknown", "context_inferred")

# --- knowledge_ingestion_jobs -------------------------------------------------

JOB_TYPES = (
    "upload",
    "reprocess",
    "website_crawl",
    "governance_import",
    "embedding_backfill",
    "benchmark_run",
)

JOB_STATUSES = ("queued", "running", "completed", "failed", "cancelled")

# --- knowledge_search_feedback -------------------------------------------------

FEEDBACK_RATINGS = ("helpful", "not_helpful", "incorrect", "outdated")

# --- knowledge_conflicts --------------------------------------------------------

CONFLICT_RESOLUTION_STATUSES = ("open", "resolved", "wont_fix")

# --- knowledge_benchmark_questions -----------------------------------------------

BENCHMARK_AUDIENCES = ("guest", "internal")

# --- website_crawl_runs -----------------------------------------------------------

CRAWL_RUN_STATUSES = ("running", "completed", "failed")
