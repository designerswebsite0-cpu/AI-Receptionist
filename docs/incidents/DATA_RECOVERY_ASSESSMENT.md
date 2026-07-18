# Data Recovery Assessment

Classification of every data category that could plausibly have existed in
`public` before the incident, per the read-only forensics in
`DATABASE_DESTRUCTION_INCIDENT.md`.

## Potentially Recoverable (survived outside `public`, not lost)

- **Supabase Auth users** — `auth.users` was never touched (a different
  schema; `Base.metadata`/Alembic only target `public`). 1 account intact:
  id, email, created_at, last_sign_in_at all present.
- **Storage buckets/objects** — `storage.buckets` intact (1 bucket,
  `documents`). `storage.objects` count is 0 — there was nothing uploaded
  to recover in the first place.
- **RKPR RAG source documents** — the local corpus files
  (`RKPR_RAG_FINAL_DOCS/`) live on disk in the repo working directory, not
  in the database. Entirely unaffected by this incident.
- **Migration source code, application code, docs** — all in git/on disk,
  confirmed intact via `git status`/`git log` before this incident's
  recovery work began (see incident record's git-state check).

## Regeneratable (schema recovers the container; content must be re-run)

- **Knowledge sources / source versions / chunks / embeddings** — the real
  RKPR corpus import was never successfully completed before this incident
  (it was blocked on `OPENAI_API_KEY`, which only became available *after*
  the incident). There is no real embedded corpus data to have lost here —
  the import will be run fresh, for the first time, once schema recovery
  and Phase 1-3 structural verification are complete and explicitly
  approved.
- **Website crawl records** — re-crawlable from the same source URLs
  whenever the website crawler is next run; nothing irreplaceable was
  stored only in the deleted rows.
- **Knowledge retrieval logs / search feedback / benchmark results** — these
  are observability/evaluation artifacts, regenerated the next time
  retrieval or the benchmark runner is exercised. No historical logs
  existed yet from real usage (the benchmark run itself was part of the
  work still pending `OPENAI_API_KEY`).
- **Governance/seed reference data** — none of this project's migrations
  seed knowledge-domain reference data via fixed rows (the one seed
  migration, 0005, seeds RBAC permission rows for the now-removed tenant
  system, and is itself later undone by migration 0008 — see reconciliation
  note in `EXPECTED_DATABASE_SCHEMA.md`). Nothing here needs regenerating.
- **`resort_settings`** — a single configuration row describing the resort
  (name, address, check-in times, branding). No migration seeds this row;
  it is created via the app once, by a human filling in the dashboard/API.
  This needs to be **re-entered by the user** after schema recovery — it is
  not something I can reconstruct from code or memory, since it is
  deployment-specific business information.

## Permanently Lost (no backup, no export, no surviving source)

- **Any `customers` rows** that existed from earlier manual/session testing
  — full name, contacts, preferences, notes, tags. Gone.
- **Any `conversations` / `messages` / `conversation_state_events` /
  `message_attachments` rows** — any test conversations, message history,
  or dialogue-state audit trail that existed. Gone.
- **Any `audit_logs` rows** — the audit trail of whatever mutations happened
  before the incident. Gone (this is itself a loss of the very
  audit-of-audit-events trail rules.md calls for, but there is nothing to
  recover it from).
- **Any `orchestration_turns` / `service_requests` rows** — Phase 4 was
  still under active development and its tables (0021-0022) had, at most,
  rows from this session's own manual smoke-testing (already-known
  synthetic test data, not real usage) — nothing of lasting value.

**Important distinction** (per your instructions): migrations recover
*schema* — table structure, columns, constraints, indexes, RLS policies —
never historical row content. Nothing in this recovery plan claims to
resurrect deleted rows; the "permanently lost" category above is final
unless you have an export, screenshot, or note of specific values you want
manually re-entered (in which case, tell me what you have and I will help
you re-enter it through the normal application flow — never by fabricating
data).

## What Requires Your Action After Schema Recovery

1. **`resort_settings`** — you'll need to (re-)enter your resort's name,
   address, check-in/out times, etc. through the dashboard or API once the
   schema is rebuilt. I cannot invent this.
2. **Nothing else** — the surviving `auth.users` row means your login
   should keep working once your `users` profile-mirror row is recreated
   (this happens automatically on your next sign-in, per the app's
   verified-JWT upsert flow — I will confirm this behavior rather than
   assume it during Phase 1 verification).
