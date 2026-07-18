# Phase 3 Implementation Plan — Knowledge Intelligence Engine

> Status: written before implementation (Step 2 of the Phase 3 brief), updated if reality diverges during build. Superseded by `PHASE_3_COMPLETION_REPORT.md` for final-state truth.

## 1. Audit findings that shape this plan

**Repo state (Phase 1/2/2.5 complete):** single-resort FastAPI backend (`apps/api/app`), modules follow `models.py` / `repository.py` / `service.py` / `router.py` / `schemas.py` per domain (see `customers/`, `conversations/`). Auth is `app.deps.get_current_user` (authentication only, no roles). Audit via `app.audit.service.record_audit_event`. Migrations are sequential Alembic files in `apps/api/alembic/versions/`, latest is `0009`. No Redis, no Docker, no ClamAV, no Tesseract installed on this dev machine. Real Supabase project connected (see `docs/product_decisions.md`).

**Database:** `pgvector` 0.8.2 is available on the connected Supabase project but not yet enabled (`CREATE EXTENSION` not yet run). `pg_trgm` and `unaccent` are also available — enabling both for fuzzy governance-file matching and better full-text search. **Correction discovered while running migration `0013` against the live DB:** pgvector's HNSW index has a hard 2000-dimension cap regardless of pgvector version — `text-embedding-3-large`'s native 3072 dims do not fit. Resolved by using OpenAI's `dimensions` truncation parameter at 1536 (`EMBEDDING_DIMENSIONS` in `app/knowledge/constants.py`), which keeps most of `-3-large`'s quality edge over `-3-small` while fitting the index. Every embedding API call must pass `dimensions=1536` explicitly, not just size the column that way.

**RAG package location:** `RKPR_RAG_FINAL_DOCS/` at repo root (not a zip — the user already extracted it; confirmed via correction mid-task). Structure matches the brief's `00_CONTROL` / `01_GUEST_KNOWLEDGE` / `02_MEDIA_INDEXABLE` / `03_OCR_TESTS` / `04_GOVERNANCE` / `05_STAFF_ONLY` / `90_ARCHIVE` / `99_TEMPLATES_NOT_FOR_INGESTION` layout exactly. `00_CONTROL/PHASE3_INGESTION_MANIFEST.csv` gives a `sha256` + `ingest_status` + `target_index` for every single file — this is the primary machine-readable ingestion driver, more reliable than folder inference alone.

**Critical governance finding:** `Knowledge_Source_Register.xlsx`'s "File Name or URL" column uses an **older folder layout** (`02_Rooms_and_Accommodation/...`, `GOVERNANCE/...`, `STAFF_ONLY/...`) that does not match the actual package's current folder layout (`01_GUEST_KNOWLEDGE/Rooms/...`, `04_GOVERNANCE/...`, `05_STAFF_ONLY/...`). **Exact path matching will fail on all 24 register rows.** The governance importer must match by, in order: (1) `Source ID` embedded in filename/notes where present, (2) SHA-256 checksum against the ingestion manifest, (3) normalized filename (case/whitespace/punctuation-insensitive basename match), (4) registered title fuzzy-matched against extracted document titles, (5) flagged for manual resolution. This is exactly what the brief's §15 anticipates — confirmed necessary, not hypothetical.

**Register data quality:** the register's own values don't always match its own controlled vocabulary tab (e.g. `Source Priority` values `Supplementary` and `Source Priority` cell content `No - see SRC-006` appear where the "Lists" tab only defines `Critical/High/Normal/Low`). The importer must accept and normalize these via an explicit mapping table, not crash or silently drop rows. Unmappable values are recorded in the reconciliation report, not guessed.

**Website is live** (confirmed via `curl`, unlike at package-creation time): `https://rkpr-website.vercel.app/` returns HTTP 200, `/sitemap.xml` returns HTTP 200. **Two real bugs in the live site the crawler must work around:**
1. `robots.txt`'s `Sitemap:` directive points at `http://localhost:3000/sitemap.xml` (a deployment misconfiguration on their end) — the crawler uses the **configured** `sitemap_url` from `website_crawl_seed.json`, never a scraped `Sitemap:` line.
2. Every `<loc>` in the actual sitemap XML is `http://localhost:3000/<path>` — same root cause. The crawler extracts only the **path** from each `<loc>` and rebases it onto the configured `base_url` (`https://rkpr-website.vercel.app`) before fetching. This is implemented once as a `_rebase_url()` helper, covered by a unit test using exactly this real malformed input.

**No Redis, ClamAV, or Tesseract available locally.** All three get a real interface + a real primary implementation (Redis client, ClamAV clamd-protocol client, pytesseract), each with an honest "unavailable" state that is never silently treated as "safe"/"done" — see §6.

## 2. Database design

New Alembic migrations, numbered `0010` onward (never touching `0001`-`0009`, same rule as Phase 2.5):

- `0010_pgvector_extension.py` — `CREATE EXTENSION IF NOT EXISTS vector`, `pg_trgm`, `unaccent`.
- `0011_knowledge_sources.py` — `knowledge_sources` table + enums as CHECK constraints (matching the project's established pattern from `conversations`/`messages` rather than native Postgres ENUM types, for consistent alter-ability).
- `0012_knowledge_source_versions.py`
- `0013_knowledge_chunks.py` — includes the `embedding vector(3072)` column (dimension from `EMBEDDING_DIMENSIONS` config, baked in at migration-write time since pgvector requires a fixed dimension per column), HNSW index on `embedding`, GIN index on `to_tsvector(content_normalized)`, plus the metadata/filter columns.
- `0014_knowledge_media.py`
- `0015_knowledge_ingestion_jobs.py`
- `0016_knowledge_retrieval_logs_and_feedback.py` — `knowledge_retrieval_logs`, `knowledge_search_feedback`
- `0017_knowledge_governance.py` — `knowledge_conflicts`, `knowledge_benchmark_questions`
- `0018_website_crawl_runs.py`
- `0019_knowledge_rls.py` — authenticated-user RLS on every new table (same `auth.uid() IS NOT NULL` pattern as Phase 2.5; guest-facing retrieval is enforced at the FastAPI query layer via explicit `WHERE` clauses, not via RLS alone, since the retrieval API itself runs under the backend's service-role connection — RLS here is defense-in-depth for direct-Postgres access, consistent with the project's existing security model, documented explicitly so it isn't mistaken for the primary guest/staff boundary).

Table field lists follow the brief's §7 recommendations closely; naming/typing conforms to this repo's conventions (`UUIDPrimaryKeyMixin`, `TimestampMixin`, snake_case, `*_json`/`*_metadata` as JSONB). Enums implemented as `CheckConstraint` string columns:
`source_type`, `visibility`, `source_priority`, `status`, `processing_status`, `chunk_type`, `job_type`/`job_status`.

**Guest-safety enforced at the query level, not just a boolean:** every guest-facing repository query includes `visibility = 'guest' AND retrieval_enabled = true AND status = 'active' AND (expiry_date IS NULL OR expiry_date >= now())` directly in the `WHERE` clause — never a post-filter in Python, never left to the LLM prompt. This is the literal implementation of brief §8's "must never rely solely on LLM prompt instructions."

## 3. Module layout (`apps/api/app/knowledge/`)

```
knowledge/
  __init__.py
  models.py              # all 10 tables
  constants.py            # enums, chunk types, precedence weights
  schemas.py               # request/response Pydantic models
  repository.py            # source/version/chunk/media/job queries incl. guest-safe retrieval query
  service.py                # source lifecycle orchestration (create/update/archive/reprocess)
  storage.py                 # Supabase Storage client (httpx, matches existing GoTrue-proxy pattern)
  validation.py               # MIME/magic-byte/size/filename/ZIP-bomb/page-count checks
  malware.py                   # MalwareScanner interface + ClamAV + Unavailable implementations
  errors.py                     # structured error codes from brief §31
  extraction/
    __init__.py
    base.py                     # Extractor protocol
    pdf.py                        # PyMuPDF, text-density OCR-required detection
    docx.py
    xlsx.py
    csv.py
    html.py                        # website extraction (shared with crawler)
    image.py                        # Pillow metadata only (OCR handled separately)
  ocr/
    __init__.py
    base.py                       # OCRProvider protocol
    tesseract.py                    # pytesseract implementation
  normalization.py                 # whitespace/unicode/header-footer/OCR-artifact cleanup
  chunking/
    __init__.py
    base.py                        # Chunker protocol + deterministic chunk-key hashing
    strategies.py                   # per-chunk_type strategies (room, menu_item, faq, policy, ...)
  embeddings.py                     # OpenAI embedding provider, batching/retry/dedup + Mock provider
  retrieval/
    __init__.py
    query_classification.py
    hybrid.py                       # dense+sparse merge, scoring, filtering
    reranker.py                      # Reranker protocol + heuristic implementation
  governance/
    __init__.py
    importer.py                      # register/conflict/benchmark importers, reconciliation report
    matching.py                       # multi-strategy file matcher
  jobs/
    __init__.py
    queue.py                          # IngestionQueue protocol
    redis_queue.py                     # real Redis implementation
    inline_queue.py                     # DB-tracked synchronous fallback for no-Redis dev (documented tech debt)
    pipeline.py                          # the 13-stage pipeline orchestrator
  website/
    __init__.py
    crawler.py                          # sitemap/robots/crawl/canonicalize/hash
  router.py                              # all Phase 3 API endpoints
  scripts/
    __init__.py
    import_rkpr_knowledge.py              # CLI: --dry-run / --execute, idempotent
```

## 4. Job queue design (Redis-compatible, no Redis required locally)

`IngestionQueue` protocol: `enqueue(job) / claim_next(worker_id) / heartbeat(job_id) / complete(job_id) / fail(job_id, error) / get_progress(job_id)`. `RedisIngestionQueue` implements it with Redis lists + a lock key per job (used automatically when `REDIS_URL` is set). `InlineIngestionQueue` implements the identical interface but executes the job body immediately inside the enqueuing request via `asyncio.create_task` — **every stage still writes its real row to `knowledge_ingestion_jobs`**, so the dashboard's job/progress view is identical either way; the only difference is horizontal scalability and true out-of-process durability. Selected automatically by `get_settings().redis_url` being set or not, logged clearly at startup. This is the same documented-interim pattern already established for rate limiting in Phase 1 (`app/rate_limit.py`) — consistent with the codebase's existing approach to "real interface now, real Redis backing when infra lands."

## 5. Malware scanning — fail-closed, never silently "safe"

`MalwareScanner` protocol: `scan_file(path) -> ScanResult(status: CLEAN|INFECTED|UNAVAILABLE, engine, scanned_at)`. `ClamAVScanner` speaks the `clamd` `INSTREAM` protocol over `CLAMAV_HOST:CLAMAV_PORT`. When ClamAV isn't reachable: if `APP_ENV=production` and `CLAMAV_REQUIRED_IN_PRODUCTION=true` (default), the scan result is `UNAVAILABLE` and the pipeline **fails the job** rather than proceeding — brief §10's fail-closed requirement, implemented literally. In development, `UNAVAILABLE` is allowed to proceed but the source is stamped `malware_scan_status=unscanned_dev_only` in its metadata, visible in the dashboard, never silently reported as clean.

## 6. OCR — used only when needed, low confidence blocks activation

PDF/image OCR-required detection: PyMuPDF's per-page `get_text()` character count vs. page area, blank-page ratio, and an explicit `ocr_required` override from governance data. `TesseractOCRProvider` wraps `pytesseract`; if the `tesseract` binary isn't on `PATH` (confirmed true on this dev machine), `scan()` returns a structured `OCRUnavailable` result — the pipeline stage records `processing_status=failed`, `error_code=OCR_FAILED`, and does **not** silently mark the source ready. The two files in `03_OCR_TESTS/` get a dedicated integration test asserting: text is extracted (proving OCR works end-to-end when the binary is present) AND `retrieval_enabled` stays `false` regardless (proving governance tagging isn't bypassable by a successful OCR run) — brief §12's two explicit requirements as two explicit assertions.

## 7. Retrieval scoring

```
final_score = dense_score * DENSE_WEIGHT
            + sparse_score * SPARSE_WEIGHT
            + priority_boost[source_priority]   # critical > high > normal > low
            + (0.15 if authoritative else 0)
            + (0.10 if exact entity/category match else 0)
            + (0.05 if query terms in section_title else 0)
```
No freshness boost exists at all (brief §19: "do not give old or archived content a freshness boost") — archived/expired sources are excluded by the `WHERE` clause before scoring even runs, not down-weighted.

## 8. What is explicitly NOT built this phase

Per brief §38: no WhatsApp, no voice, no final conversational answer-generation agent (a minimal, clearly-labeled `test-query` composer is built only for the search playground/benchmark runner, not a customer-facing chat endpoint). No tenant/RBAC re-introduction. No Temporal.

## 9. Risks

- **pgvector HNSW build time** against 3072-dim vectors for ~thousands of chunks could be slow on Supabase's shared compute — will build the index `CONCURRENTLY`-equivalent where possible and report actual timing in the completion report rather than assuming.
- **OpenAI embedding cost/rate limits** during the real RKPR import — batched, retried, and the dry-run reports a cost estimate before `--execute` is ever run against the live corpus.
- **Register data quality** (§1 above) means the governance importer's reconciliation report is load-bearing, not optional — Step 13's dry run must be inspected by a human (me, then reported to the user) before execute.
- **No local Redis/ClamAV/Tesseract** means those three subsystems are verified via unit tests against the protocol/interface plus explicit "unavailable" behavior tests, not full live integration tests, on this dev machine. Documented as a known verification gap in the completion report, not hidden.
