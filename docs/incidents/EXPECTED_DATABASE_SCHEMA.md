# Expected Database Schema (Recovery Reference)

Derived directly from the current ORM models (`app/**/models.py`) and the
Alembic migration chain (`alembic/versions/0001`–`0023`), which is linear
with no gaps or branches (verified by inspecting every `revision`/
`down_revision` pair). This is the schema `alembic upgrade head` must
reproduce in `public`. Migration provenance is cited per table/column so any
future migration can be traced back to who introduced what and why.

Phase tag legend: **P1** = Phase 1 foundation, **P2** = Phase 2 conversations,
**P2.5** = single-resort refactor, **P3** = Knowledge Intelligence Engine,
**P4** = AI Orchestration (this phase, in progress).

## users (P1, migration 0001; email uniqueness may have shifted since — see note)

Profile mirror of `auth.users`, upserted on first sign-in.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | — | PK, same UUID as `auth.users.id` |
| email | VARCHAR(320) | no | — | UNIQUE |
| full_name | VARCHAR(200) | yes | — | |
| avatar_url | VARCHAR(1000) | yes | — | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | TimestampMixin |

No RLS policy defined in current models (Phase 1's `users_select` policy was
dropped by migration 0008 as part of tenant-system removal and never
re-added — profile rows are read via `app.deps.get_current_user`'s verified
JWT, not row-level policy, per the single-resort auth model).

## audit_logs (P1 migration 0003; restructured by P2.5 migration 0008)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| actor_user_id | UUID | yes | — | FK → users.id, ON DELETE SET NULL, indexed |
| action | VARCHAR(100) | no | — | indexed |
| resource_type | VARCHAR(100) | no | — | |
| resource_id | VARCHAR(100) | yes | — | |
| before_state | JSONB | yes | — | added by 0008 |
| after_state | JSONB | yes | — | added by 0008 |
| event_metadata | JSONB | no | {} | |
| ip_address | INET | yes | — | |
| correlation_id | VARCHAR(64) | yes | — | indexed, added by 0008 |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## resort_settings (P2.5 migration 0007)

Singleton table — at most one row.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| singleton | BOOLEAN | no | true | UNIQUE + CHECK(singleton = true) |
| resort_name | VARCHAR(200) | no | — | |
| legal_name, description, address, city, state, country, postal_code, phone, email, whatsapp | various | yes | — | |
| timezone | VARCHAR(64) | no | UTC | |
| currency | VARCHAR(10) | no | USD | |
| default_language | VARCHAR(10) | no | en | |
| check_in_time, check_out_time | VARCHAR(10) | yes | — | |
| logo_url, primary_brand_color, secondary_brand_color, website_url | various | yes | — | |
| settings_metadata | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## customers (P2 migration 0004; tenant_id dropped by P2.5 migration 0008)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| full_name | VARCHAR(200) | yes | — | |
| preferred_language | VARCHAR(10) | no | en | |
| preferred_channel | VARCHAR(20) | yes | — | |
| lifetime_value | NUMERIC(12,2) | no | 0 | |
| loyalty_reference | VARCHAR(100) | yes | — | |
| preferences | JSONB | no | {} | |
| resort_preferences | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |
| deleted_at | TIMESTAMPTZ | yes | — | SoftDeleteMixin |

RLS (0006, tenant-scoped originally; policy dropped+not replaced by 0008 —
current access control is at the API/service layer, not RLS, post single-
resort refactor for this table).

## customer_contacts (P2 migration 0004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| customer_id | UUID | no | — | FK → customers.id CASCADE, indexed |
| contact_type | VARCHAR(20) | no | — | CHECK IN (phone, email, whatsapp) |
| value | VARCHAR(320) | no | — | |
| is_primary | BOOLEAN | no | false | |
| verified | BOOLEAN | no | false | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

UNIQUE(contact_type, value) — global uniqueness since 0008 (was
tenant-scoped before).

## customer_notes (P2 migration 0004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| customer_id | UUID | no | — | FK → customers.id CASCADE, indexed |
| author_user_id | UUID | yes | — | FK → users.id SET NULL |
| note | VARCHAR(4000) | no | — | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## customer_tags (P2 migration 0004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| customer_id | UUID | no | — | FK → customers.id CASCADE, indexed |
| tag | VARCHAR(50) | no | — | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

UNIQUE(customer_id, tag).

## conversations (P2 migration 0004; flow_state added P4 migration 0020)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| customer_id | UUID | no | — | FK → customers.id RESTRICT, indexed |
| channel | VARCHAR(20) | no | — | CHECK IN (whatsapp, webchat) |
| status | VARCHAR(30) | no | open | CHECK IN (open, waiting_for_guest, waiting_for_staff, ai_handling, human_handling, escalated, closed, blocked), indexed |
| current_state | VARCHAR(30) | no | greeting | CHECK IN the 11 canonical DIALOGUE_STATES |
| **flow_state** | VARCHAR(50) | yes | — | **P4 addition (0020)** — sub-state refinement within current_state, no CHECK constraint (validated in app code), indexed |
| assigned_agent_id | UUID | yes | — | FK → users.id SET NULL, indexed |
| priority | VARCHAR(20) | no | normal | |
| started_at | TIMESTAMPTZ | no | — | |
| last_message_at | TIMESTAMPTZ | yes | — | |
| closed_at | TIMESTAMPTZ | yes | — | |
| ai_active | BOOLEAN | no | true | |
| human_active | BOOLEAN | no | false | |
| summary | VARCHAR(4000) | yes | — | |
| tags | JSONB | no | [] | |
| conversation_metadata | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## conversation_state_events (P2 migration 0004)

Append-only audit trail of dialogue-state transitions.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| conversation_id | UUID | no | — | FK → conversations.id CASCADE, indexed |
| from_state | VARCHAR(30) | yes | — | |
| to_state | VARCHAR(30) | no | — | |
| changed_by | VARCHAR(20) | no | — | CHECK IN (ai, human, system) |
| event_metadata | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## messages (P2 migration 0004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| conversation_id | UUID | no | — | FK → conversations.id CASCADE, indexed |
| direction | VARCHAR(10) | no | — | CHECK IN (inbound, outbound) |
| sender_type | VARCHAR(20) | no | — | CHECK IN (customer, ai, human, system) |
| sender_user_id | UUID | yes | — | FK → users.id SET NULL |
| content_type | VARCHAR(20) | no | text | CHECK IN (text, image, document, audio, video) |
| content_text | VARCHAR(8000) | yes | — | |
| delivery_status | VARCHAR(20) | no | pending | CHECK IN (pending, sent, delivered, failed) |
| read_at | TIMESTAMPTZ | yes | — | |
| external_message_id | VARCHAR(200) | yes | — | indexed, idempotency key |
| message_metadata | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## message_attachments (P2 migration 0004)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| message_id | UUID | no | — | FK → messages.id CASCADE, indexed |
| attachment_type | VARCHAR(20) | no | — | CHECK IN (image, document, audio, video) |
| storage_path | VARCHAR(1000) | no | — | private Storage object path, never public URL |
| file_name | VARCHAR(300) | yes | — | |
| mime_type | VARCHAR(100) | yes | — | |
| size_bytes | BIGINT | yes | — | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## knowledge_sources (P3 migration 0011)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| source_id | VARCHAR(50) | yes | — | UNIQUE, external identifier |
| title | VARCHAR(300) | no | — | |
| description | VARCHAR(4000) | yes | — | |
| source_type | VARCHAR(20) | no | — | CHECK constraint |
| category / subcategory | VARCHAR(100) | yes | — | |
| language | VARCHAR(10) | no | en | |
| storage_path, original_filename, file_format, mime_type | various | yes | — | |
| file_size_bytes | BIGINT | yes | — | |
| checksum_sha256 | VARCHAR(64) | yes | — | indexed |
| source_url | VARCHAR(1000) | yes | — | |
| visibility | VARCHAR(20) | no | — | CHECK constraint, indexed |
| source_priority | VARCHAR(20) | no | normal | CHECK constraint |
| authoritative | BOOLEAN | no | false | |
| retrieval_enabled | BOOLEAN | no | false | |
| status | VARCHAR(20) | no | draft | CHECK constraint, indexed |
| processing_status | VARCHAR(20) | no | pending | |
| ocr_required | BOOLEAN | no | false | |
| malware_scan_status | VARCHAR(30) | no | pending | |
| approval_status | VARCHAR(20) | no | pending | CHECK constraint |
| approved_by | UUID | yes | — | FK → users.id SET NULL |
| approved_at | TIMESTAMPTZ | yes | — | |
| effective_date / expiry_date | DATE | yes | — | |
| tags | JSONB | no | [] | |
| source_metadata | JSONB | no | {} | |
| created_by | UUID | yes | — | FK → users.id SET NULL |
| current_version_id | UUID | yes | — | FK → knowledge_source_versions.id SET NULL, **use_alter=True** (circular with knowledge_source_versions), constraint name `knowledge_sources_current_version_id_fkey` (matches Postgres' own default-assigned name from migration 0012) |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

RLS added by migration 0019.

## knowledge_source_versions (P3 migration 0012)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| source_id | UUID | no | — | FK → knowledge_sources.id CASCADE, indexed |
| version_number | INTEGER | no | — | UNIQUE with source_id |
| storage_path | VARCHAR(1000) | yes | — | |
| checksum_sha256 | VARCHAR(64) | no | — | |
| raw_text / normalized_text | TEXT | yes | — | |
| page_count / word_count | INTEGER | yes | — | |
| extraction_method | VARCHAR(50) | yes | — | |
| ocr_used | BOOLEAN | no | false | |
| ocr_confidence | NUMERIC(5,2) | yes | — | |
| processing_status | VARCHAR(20) | no | pending | CHECK constraint |
| error_message | VARCHAR(4000) | yes | — | |
| is_current | BOOLEAN | no | true | |
| created_by | UUID | yes | — | FK → users.id SET NULL |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

RLS added by migration 0019.

## knowledge_chunks (P3 migration 0013)

No TimestampMixin's `onupdate` — plain created_at/updated_at columns.
Contains the pgvector embedding column.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| source_id | UUID | no | — | FK → knowledge_sources.id CASCADE, indexed |
| version_id | UUID | no | — | FK → knowledge_source_versions.id CASCADE, indexed |
| chunk_key | VARCHAR(128) | no | — | UNIQUE with source_id |
| chunk_type | VARCHAR(30) | no | generic | CHECK constraint, indexed |
| chunk_index | INTEGER | no | — | |
| content_raw / content_normalized | TEXT | no | — | |
| content_hash | VARCHAR(64) | no | — | |
| section_title | VARCHAR(300) | yes | — | |
| heading_path | VARCHAR(500) | yes | — | |
| page_number | INTEGER | yes | — | |
| token_count | INTEGER | yes | — | |
| **embedding** | **vector(EMBEDDING_DIMENSIONS)** | yes | — | pgvector column — requires the `vector` extension (confirmed present, v0.8.2) |
| embedding_model | VARCHAR(100) | yes | — | |
| entity_metadata | JSONB | no | {} | |
| visibility | VARCHAR(20) | no | — | CHECK constraint |
| source_priority | VARCHAR(20) | no | normal | CHECK constraint |
| authoritative | BOOLEAN | no | false | |
| retrieval_enabled | BOOLEAN | no | false | |
| effective_date / expiry_date | DATE | yes | — | |
| status | VARCHAR(20) | no | active | CHECK constraint |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

RLS added by migration 0019 — this is defense-in-depth only; the real
guest-safety boundary is query-level filtering in
`app.knowledge.retrieval.service.search`, not RLS alone.

## knowledge_media (P3 migration 0014)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| source_id | UUID | yes | — | FK → knowledge_sources.id SET NULL, indexed |
| storage_path | VARCHAR(1000) | no | — | |
| original_filename, checksum_sha256, mime_type | various | yes | — | |
| width_px / height_px | INTEGER | yes | — | |
| file_size_bytes | BIGINT | yes | — | |
| category | VARCHAR(100) | yes | — | indexed |
| linked_entity | VARCHAR(200) | yes | — | |
| alt_text | VARCHAR(500) | yes | — | |
| caption | VARCHAR(1000) | yes | — | |
| caption_is_inferred | BOOLEAN | no | false | |
| rights_status | VARCHAR(30) | no | unknown | CHECK constraint |
| visibility | VARCHAR(20) | no | guest | CHECK constraint |
| retrieval_enabled | BOOLEAN | no | false | |
| media_metadata | JSONB | no | {} | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## knowledge_ingestion_jobs (P3 migration 0015)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| job_type | VARCHAR(30) | no | — | CHECK constraint |
| job_status | VARCHAR(20) | no | queued | CHECK constraint, indexed |
| source_id | UUID | yes | — | FK → knowledge_sources.id SET NULL, indexed |
| payload | JSONB | no | {} | |
| progress_current | INTEGER | no | 0 | |
| progress_total | INTEGER | yes | — | |
| result_summary | JSONB | yes | — | |
| error_message | VARCHAR(4000) | yes | — | |
| started_at / completed_at | TIMESTAMPTZ | yes | — | |
| worker_id | VARCHAR(100) | yes | — | |
| created_by | UUID | yes | — | FK → users.id SET NULL |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## knowledge_retrieval_logs (P3 migration 0016)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| query_text | VARCHAR(2000) | no | — | |
| query_classification | VARCHAR(50) | yes | — | |
| filters_applied | JSONB | no | {} | |
| results_returned | JSONB | no | [] | |
| result_count | INTEGER | no | 0 | |
| latency_ms | INTEGER | yes | — | |
| requested_channel | VARCHAR(30) | yes | — | |
| conversation_id | UUID | yes | — | FK → conversations.id SET NULL, indexed |
| requested_by | UUID | yes | — | FK → users.id SET NULL |
| created_at | TIMESTAMPTZ | no | now() | indexed (no updated_at — logs are immutable) |

## knowledge_search_feedback (P3 migration 0016)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| retrieval_log_id | UUID | no | — | FK → knowledge_retrieval_logs.id CASCADE, indexed |
| chunk_id | UUID | yes | — | FK → knowledge_chunks.id CASCADE, indexed |
| rating | VARCHAR(20) | no | — | CHECK constraint |
| notes | VARCHAR(2000) | yes | — | |
| created_by | UUID | yes | — | FK → users.id SET NULL |
| created_at | TIMESTAMPTZ | no | now() | (no updated_at) |

## knowledge_conflicts (P3 migration 0017)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| conflict_key | VARCHAR(50) | yes | — | UNIQUE |
| description | VARCHAR(4000) | no | — | |
| source_a_id / source_b_id | UUID | yes | — | FK → knowledge_sources.id SET NULL |
| resolution_status | VARCHAR(20) | no | open | CHECK constraint, indexed |
| resolution_notes | VARCHAR(4000) | yes | — | |
| resolved_source_id | UUID | yes | — | FK → knowledge_sources.id SET NULL |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## knowledge_benchmark_questions (P3 migration — bundled with governance, 0017)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| question | VARCHAR(2000) | no | — | |
| expected_answer | VARCHAR(4000) | yes | — | |
| expected_source_id | UUID | yes | — | FK → knowledge_sources.id SET NULL |
| category | VARCHAR(100) | yes | — | |
| audience | VARCHAR(20) | no | guest | CHECK constraint, indexed |
| priority | VARCHAR(20) | no | normal | CHECK constraint |
| last_run_result | JSONB | yes | — | |
| last_run_at | TIMESTAMPTZ | yes | — | |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

## website_crawl_runs (P3 migration 0018)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| source_id | UUID | no | — | FK → knowledge_sources.id CASCADE, indexed |
| run_status | VARCHAR(20) | no | running | CHECK constraint, indexed |
| pages_discovered / pages_crawled / pages_changed / pages_failed | INTEGER | no | 0 | |
| started_at | TIMESTAMPTZ | no | now() | |
| completed_at | TIMESTAMPTZ | yes | — | |
| error_message | VARCHAR(4000) | yes | — | |
| crawl_summary | JSONB | no | [] | |

(no updated_at — a crawl run is append-only once started)

## orchestration_turns (P4 migration 0021)

One row per pipeline run — operational decision trace, never chain-of-thought.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| conversation_id | UUID | no | — | FK → conversations.id CASCADE, indexed |
| message_id | UUID | yes | — | FK → messages.id SET NULL |
| response_message_id | UUID | yes | — | FK → messages.id SET NULL |
| detected_intent | VARCHAR(50) | yes | — | |
| intent_confidence | FLOAT | yes | — | |
| secondary_intents | JSONB | no | [] | |
| extracted_entities | JSONB | no | {} | |
| missing_entities | JSONB | no | [] | |
| flow_state | VARCHAR(50) | yes | — | |
| retrieval_query | VARCHAR(2000) | yes | — | |
| citations | JSONB | no | [] | |
| tool_name | VARCHAR(50) | yes | — | |
| tool_input | JSONB | no | {} | |
| tool_output | JSONB | yes | — | |
| tool_status | VARCHAR(20) | yes | — | |
| handoff_required | BOOLEAN | no | false | |
| handoff_reason | VARCHAR(50) | yes | — | |
| handoff_priority | VARCHAR(20) | yes | — | |
| handoff_department | VARCHAR(50) | yes | — | |
| validation_result | JSONB | no | {} | |
| provider_used | VARCHAR(30) | yes | — | |
| model_used | VARCHAR(100) | yes | — | |
| latency_ms | INTEGER | yes | — | |
| token_usage | JSONB | no | {} | |
| error_code | VARCHAR(50) | yes | — | |
| error_message | VARCHAR(2000) | yes | — | |
| created_at | TIMESTAMPTZ | no | — | indexed (no updated_at — a turn is immutable) |

RLS added by migration 0023.

## service_requests (P4 migration 0022)

Generic "safe enquiry, not a fake completed operation" record — every
`create_*_enquiry` tool writes here, one table not one per domain.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID | no | uuid4() | PK |
| conversation_id | UUID | no | — | FK → conversations.id CASCADE, indexed |
| customer_id | UUID | no | — | FK → customers.id RESTRICT, indexed |
| request_type | VARCHAR(30) | no | — | CHECK IN (booking_enquiry, dining_enquiry, spa_enquiry, activity_enquiry, transfer_enquiry, service_request, complaint) |
| details | JSONB | no | {} | |
| status | VARCHAR(20) | no | open | CHECK IN (open, in_progress, resolved, cancelled) |
| created_by | VARCHAR(10) | no | — | CHECK IN (ai, human) |
| assigned_agent_id | UUID | yes | — | FK → users.id SET NULL |
| created_at / updated_at | TIMESTAMPTZ | no | now() | |

RLS added by migration 0023.

## Reconciliation Notes

- **Single-resort architecture**: no `tenant_id` column exists anywhere in
  the current model set — confirmed by reading every `models.py` file
  directly, not assumed. Migration 0008 is the point where the last
  `tenant_id` columns and the entire tenant system (`tenants`,
  `tenant_settings`, `tenant_roles`, `tenant_permissions`, `tenant_members`)
  were removed. These tables must **not** exist in the final rebuilt schema.
- **Auth/profile linkage**: `users.id` is the same UUID as `auth.users.id`
  (upserted on first sign-in) — the one surviving `auth.users` row
  (`3328d09c-...`, `testmail@abc.com`) will need a corresponding `users` row
  recreated on that user's next successful login/token verification (the
  app does this automatically per `app/deps.py`'s verified-JWT flow — no
  manual seed needed, confirm this after schema rebuild rather than assume).
- **Phase 4 tables already in the migration chain**: `orchestration_turns`
  and `service_requests` (migrations 0021–0022) plus `conversations.flow_state`
  (migration 0020) are already part of head (0023) and will be recreated by
  the same replay — no separate action needed for them.
- **use_alter circular FK**: `knowledge_sources.current_version_id` ↔
  `knowledge_source_versions.source_id` is the one circular dependency in
  the schema; the ORM model now declares `use_alter=True` with a name
  matching Postgres' own default-assigned constraint name, so this does not
  block `create_all`/`drop_all` tooling. The **migrations themselves**
  (0011 creates `knowledge_sources` without `current_version_id`; 0012 adds
  it via a separate `op.add_column`) already handle this correctly via
  ordering, independent of the ORM annotation — the annotation only matters
  for `Base.metadata`-driven tooling (tests, not the live schema).
