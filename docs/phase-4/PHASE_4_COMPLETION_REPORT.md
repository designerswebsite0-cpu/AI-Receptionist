# Phase 4 Completion Report — AI Orchestration & Conversational Intelligence Engine

> Status: as of 2026-07-18. Supersedes `PHASE_4_IMPLEMENTATION_PLAN.md` as
> the source of truth for what actually exists — the plan predicted the
> design; this reports what was built, tested, and verified against real
> systems (including a real database-destruction incident and recovery in
> the middle of this phase — see `docs/incidents/`).

## 1. Summary

Phase 4 built the full AI Orchestration & Conversational Intelligence
Engine on top of Phases 1-3: intent classification, entity extraction, a
validated conversation flow-state machine, token-budgeted context
assembly, a modular injection-resistant prompt architecture, an
OpenAI-primary/Groq-fallback LLM provider abstraction with a circuit
breaker, a typed permission-controlled tool registry, a deterministic
human-handoff policy engine, a pre-send response-guardrail pipeline, the
top-level channel-neutral `orchestrate()` pipeline wiring all of it
together, a controlled Customer 360 memory layer, 8 authenticated API
endpoints, and dashboard support (a conversation list + detail view
showing the AI's live decision trace, with staff handoff/release
controls). 2 new database tables (`orchestration_turns`, `service_requests`)
plus one column (`conversations.flow_state`), migrations `0020`-`0023`.

**Everything was also validated against the real, activated RKPR corpus
with real OpenAI embeddings and a real `gpt-4o-mini` LLM** — not just
mocks — including a curated 13-message real-data validation checklist run
(and a second, smaller confirmation run after a real bug fix). This real
run found and fixed a genuine, structural bug (see §4, item 12) that no
amount of mock-based testing could have caught, since mocks don't enforce
OpenAI's actual message-format contract.

## 2. A Real Incident Happened Mid-Phase

Partway through Phase 4 testing, a test fixture bug (combined with an
orphaned background process) caused a real `DROP TABLE`-equivalent
operation against the live Supabase project's `public` schema, destroying
every application table. This is fully documented, root-caused, and
remediated in `docs/incidents/`:

- `DATABASE_DESTRUCTION_INCIDENT.md` — what happened, root cause, timeline.
- `EXPECTED_DATABASE_SCHEMA.md` — the recovery reference schema inventory.
- `DATA_RECOVERY_ASSESSMENT.md` — what was/wasn't recoverable (nothing was;
  no backup existed — this remains a real, open risk, not silently fixed).
- `DATABASE_RECOVERY_REPORT.md` — the isolated-recovery proof (migrations
  0001-0023 replayed twice from clean state, byte-for-byte identical
  schemas) and the live recovery execution.
- `DATABASE_SAFETY_CONTROLS.md` — the permanent fix: tests now run in a
  randomized, per-session schema sandbox that structurally cannot reach
  `public`, proven by 5 passing automated safety tests
  (`tests/test_database_safety.py`).

Phase 1-3 were structurally re-verified after recovery (144+ tests
passing) before Phase 4 work resumed. The real RKPR corpus import and
retrieval benchmark — previously blocked on `OPENAI_API_KEY` — were also
completed during this recovery window (**49/50, 98% pass rate** against
real embeddings); see `docs/phase-3/PHASE_3_COMPLETION_REPORT.md` §7.

## 3. What Was Built, By Step

1. **Reconciliation + implementation plan** — `docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md`.
2. **Orchestration domain model** — `app/orchestration/domain.py`: plain
   dataclasses (`DetectedIntent`, `ExtractedEntities`, `MissingInformation`,
   `RetrievedContext`, `ToolDecision`, `HandoffDecision`, `ValidationResult`,
   `ProviderUsage`, `OrchestrationResult`) — never chain-of-thought, only
   operationally useful decision summaries.
3. **Intent classification + entity extraction** —
   `app/orchestration/intent/{classifier,entities}.py`: deterministic
   keyword scoring first (fast, free, fully testable without a provider),
   LLM escalation only when confidence is low (classifier) or always for
   semantic fields (entities) and a provider is supplied.
4. **Conversation flow state machine** — `app/orchestration/flow/{states,engine}.py`:
   `flow_state` refines *within* one of the canonical 11 `DIALOGUE_STATES`
   (never replaces them), with validated transitions — never LLM-settable
   without going through this engine.
5. **Context assembler** — `app/orchestration/context/assembler.py`:
   token-budgeted, source-attributed; `critical`-priority citations are
   never dropped for budget reasons.
6. **Prompt architecture** — `app/orchestration/prompts/{templates,builder}.py`:
   modular rule blocks; retrieved knowledge and the guest's own message are
   always delimited and labeled untrusted, structurally separate from
   system rules (prompt-injection isolation, verified by a smoke test).
7. **LLM provider abstraction** — `app/orchestration/llm/*`: OpenAI
   primary, Groq fallback (OpenAI-compatible wire protocol reused, no
   second SDK), a circuit breaker (`FallbackLLMProvider`), a deterministic
   `MockLLMProvider` for tests.
8. **Tool registry + routing** — `app/orchestration/tools/*`: typed tool
   definitions with permission metadata; the backend validates every
   proposed call before anything executes (`docs/CLAUDE.md` "the backend
   always validates tool requests"); every `create_*_enquiry` tool writes
   a `service_requests` row, never a fake completed booking/payment/refund.
9. **Human handoff engine** — `app/orchestration/handoff/engine.py`:
   deterministic policy covering every mandatory scenario (payment,
   refund, safety, emergency, explicit request, repeated failures) —
   never left to the LLM's own judgment.
10. **Response validation + guardrails** — `app/orchestration/guardrails/validator.py`:
    deterministic pattern checks (unauthorized booking/payment claims,
    system-prompt leaks, unsupported price/availability claims, missing
    follow-up questions, excessive verbosity) run on every response before
    it becomes a `Message` row.
11. **Orchestration pipeline** — `app/orchestration/pipeline.py`:
    `orchestrate()`, the single channel-neutral entry point wiring steps
    2-10 together; idempotent replay (a redelivered `message_id` short-
    circuits without re-invoking the LLM or re-executing any tool);
    "handoff lockout" (suppresses AI replies once a human has actively
    taken over).
12. **Memory strategy** — `app/orchestration/memory.py`: rules.md §6's
    "verified facts, AI inferences, AI summaries, conversation state
    stored separately" — AI-inferred guest preferences are written into a
    namespaced `customers.resort_preferences["ai_inferred"]` sub-key,
    never into verified fields or `CustomerNote`, and only for a fixed,
    curated vocabulary of durable preferences (never stay-specific
    transactional details like check-in dates).
13. **API layer** — `app/orchestration/router.py`: 8 endpoints under
    `/api/v1/orchestration` (see `docs/api.md`).
14. **Dashboard support** — `apps/dashboard/src/app/conversations/*`: a
    conversation list + detail page showing the message thread, the AI's
    live decision trace (intent, confidence, tool calls, handoff status
    per turn), and staff handoff/release controls. (Phase 2 had never
    built any conversation/inbox dashboard UI at all — only its backend
    API — so this also closes that pre-existing gap.)
15. **Tests + real-data validation** — see §5-6.
16. **Documentation** — this report + `docs/database.md` §10,
    `docs/api.md`'s AI Orchestration section, `docs/roadmap.md`.

## 4. Real Bugs Found and Fixed

These were discovered by actually running the code — against a real
database, real embeddings, and the real OpenAI API — not by inspection
alone:

1. **`Conversation.flow_state` was never mapped on the ORM model** —
   migration `0020` added the column, but nobody added the corresponding
   `Mapped[str | None]` field, so every read/write of it would have
   silently failed. Fixed in `app/conversations/models.py`.
2. **Real bug in `is_small_talk()`** — prefix-matching false positive:
   "Hello, I need help with a booking" was misclassified as small talk.
   Fixed with punctuation-stripped normalization + a length cap.
3. **Real bug: `_CHILDREN_PATTERN` regex** — didn't match singular "1
   child", only "children"/"kids". Fixed.
4. **Real bug: `greeting` dialogue state couldn't reach specific-intent
   targets directly** — forced every first message through an artificial
   two-hop `discovering_needs` detour, even an already-specific "book a
   villa for 2 adults" request. Fixed by inheriting `discovering_needs`'s
   full reachable set.
5. **`AppError` import path typo** in `llm/fallback.py`.
6. **Missing explicit model imports causing `NoReferencedTableError`/
   `PendingRollbackError`** — hit **five separate times** across this
   session (`tests/conftest.py`, `app/scripts/import_rkpr_knowledge.py`,
   `app/scripts/run_benchmark.py`, plus two throwaway governance/debug
   scripts) whenever a script's own import chain didn't happen to touch
   `app.users.models` (or similar) before running a query joining through
   a foreign key to it — even though the real table exists in the live
   database. Fixed in each permanent script by mirroring `alembic/env.py`'s
   own explicit import list. **Not yet centralized** — see §7.
7. **`Base.metadata.drop_all()`/`create_all()` against the shared live
   database** — the root cause of the mid-phase incident (§2). Permanently
   fixed via the schema-sandbox approach in `DATABASE_SAFETY_CONTROLS.md`.
8. **Circular FK between `knowledge_sources`/`knowledge_source_versions`**
   blocked test-tooling `drop_all()` (`CircularDependencyError`) — fixed
   with `use_alter=True` on the ORM annotation (metadata-only; no live
   migration needed, since the actual DB schema already handles this via
   ordered `ALTER TABLE`).
9. **`app.knowledge.indexing.index_source_version` passed a source's
   free-text `category` label (e.g. "Dining") directly as `chunk_type`** —
   but `knowledge_chunks.chunk_type` has a `CHECK` constraint against a
   small fixed vocabulary that real category labels never match. Every
   real document import failed until fixed (validated against
   `CHUNK_TYPES`, falling back to `"generic"`).
10. **6 Phase 3 test files used mismatched pgvector dimensions**
    (`MockEmbeddingProvider(dimensions=16|32|64)`) before persisting real
    chunks — `knowledge_chunks.embedding` is a fixed `vector(1536)` column.
    Fixed by removing the mismatched overrides.
11. **Known limitation, not fixed**: FAQ-vs-generic chunking classification
    uses a whole-document threshold (`_FAQ_MIN_PAIRS_TO_DETECT = 3`); a
    document shrinking from 3 to 2 Q&A pairs flips classification entirely,
    breaking incremental chunk-diffing. Doesn't block one-time imports;
    documented tech debt.
12. **Structural bug: the tool-call round-trip never carried OpenAI's
    required `tool_calls`/`tool_call_id` correlation** — `LLMMessage` and
    `LLMToolCall` only had `role`/`content` and `tool_name`/`arguments`;
    replaying an assistant's tool proposal back to the API as a plain-text
    message, followed by a `role: "tool"` message with no `tool_call_id`,
    is rejected outright by the real OpenAI API ("messages with role
    'tool' must be a response to a preceeding message with 'tool_calls'").
    **3 of the first 13 real-data validation messages failed this way**
    (room comparison, cancellation policy, and a hallucination probe all
    fell through to the generic "I ran into an issue" fallback). Mocks
    never enforce OpenAI's real message-format contract, so this was
    invisible to the entire mock-based test suite. Fixed by adding
    `call_id` to `LLMToolCall` and `tool_calls`/`tool_call_id` to
    `LLMMessage`, threading the real id through both providers via a new
    shared `to_openai_wire_format()` helper, and updating the pipeline's
    follow-up round-trip to replay the exact proposed call. **Re-verified
    against the real API afterward — all 3 previously-failing scenarios
    now succeed correctly** (see §6).
13. **`search_resort_knowledge` was registered as an LLM-callable tool but
    never actually implemented** — its own registry docstring says it's
    "executed in the pipeline, not tools.handlers" (since it needs the
    embedding provider/reranker), but `pipeline.py` never special-cased it,
    so every real call fell through to `tools.handlers.execute_tool`'s
    deliberate `ValueError` for this exact tool name. This is what
    surfaced bug #12 above. Fixed by implementing
    `_search_resort_knowledge()` in `pipeline.py`, calling the real
    retrieval service with the same guest-safety filtering as the initial
    context assembly.
14. **`ConversationOut` never exposed `flow_state`** — a real, independent
    gap discovered while building the dashboard's conversation views;
    fixed in `app/conversations/schemas.py`.
15. **`.env`'s `REDIS_URL` was doubled** (`REDIS_URL=REDIS_URL="rediss://..."`)
    from a copy-paste artifact — caught immediately when validating real
    Redis connectivity, fixed before proceeding.

## 5. Real-Data Validation Checklist

Per the implementation plan's §7, tracked here rather than silently
deferred. Executed as two real runs against the real, activated RKPR
corpus with real `text-embedding-3-large` retrieval and real `gpt-4o-mini`
generation (user-approved, ~$0.03 total actual cost across both runs):

| Category | Status | Notes |
|---|---|---|
| Common guest question (check-in/out times) | ✅ Passed | Correct, well-cited |
| Room comparison | ✅ Passed (after fix #12) | Detailed, cited, correctly flags draft-pricing caveats |
| Occupancy, private-pool | ✅ Passed | Correct room names & occupancy limits |
| Meal plans, restaurant menu/pricing | ✅ Passed | Correct real prices from the rate card |
| Allergens/dietary | ✅ Passed | Helpful, asks appropriate follow-ups |
| Spa/activity pricing | ✅ Passed | Correct real price (INR 11,800) |
| Airport transfers | ✅ Passed | Asks the right follow-up questions |
| Cancellation/payment policy | ✅ Passed (after fix #12) | Cites specific sections, doesn't overclaim |
| Multi-intent messages | ✅ Passed | Both sub-questions (check-in + pool) answered correctly in one response |
| Ambiguous messages (no dates given) | ✅ Passed | Correctly asks for missing check-in date/nights |
| Incorrect guest assumptions/follow-ups | ✅ Passed | Graceful, apologetic, offers appropriate next steps |
| Hallucination spot-check (fictional casino) | ✅ Passed (after fix #12) | Correctly declines to claim it exists |
| Prompt-injection-in-guest-message | ✅ Passed | Did not reveal system prompt or follow the injected instruction |
| Handoff-decision spot-check (refund request) | ✅ Passed | Correctly triggered mandatory handoff, correct reason code, no fake promises |
| Citation relevance | ✅ Passed | Citations consistently matched the actual answer content across all scenarios |
| Conflicting/superseded info | ⚠️ Not directly exercised | The corpus's `Official Rate Card 2026` explicitly self-documents which of its own sections are draft vs. verified — the model correctly surfaced this distinction unprompted (room_comparison response), but no test specifically targeted two sources actively disagreeing |
| No-answer questions | ✅ Covered by hallucination probe | See above |

Two real production bugs (§4 items 12-13) were found and fixed via this
checklist; both were re-verified against the real API afterward.

## 6. Definition of Done — Status

| Item | Status |
|---|---|
| Orchestration domain model | ✅ Built, tested |
| Intent classification + entity extraction | ✅ Built, tested (mock + real) |
| Conversation flow state machine | ✅ Built, tested, 1 real bug found+fixed |
| Context assembler | ✅ Built, tested, validated against real embeddings |
| Prompt architecture (incl. injection isolation) | ✅ Built, tested (mock + real prompt-injection probe) |
| LLM provider abstraction (OpenAI + Groq + circuit breaker) | ✅ Built, tested; real OpenAI path exercised, Groq fallback tested only via mocks (no Groq API key in this environment) |
| Tool registry + routing | ✅ Built, tested, 1 structural real bug found+fixed |
| Human handoff engine | ✅ Built, tested (mock + real refund scenario) |
| Response validation + guardrails | ✅ Built, tested |
| Orchestration pipeline (`orchestrate()`) | ✅ Built, tested, 2 real bugs found+fixed, re-verified against real API |
| Memory strategy | ✅ Built, tested |
| API layer | ✅ Built; 8/10 planned endpoints (preview/retry deferred, see `docs/api.md`) |
| Dashboard support | ✅ Built; lint/typecheck/build pass; not clicked through live (no test login credentials, same limitation as Phase 3) |
| Security (prompt injection, tool permission bypass) | ✅ Tested (mock unit tests + real prompt-injection probe) |
| Real-data validation checklist | ✅ Executed for real — see §5 |
| Documentation | ✅ This report + updated database.md/api.md/roadmap.md |
| Single-resort architecture unchanged | ✅ No `tenant_id`, no role checks introduced anywhere in Phase 4 code |
| Fake booking/payment/refund confirmations | ✅ Correctly never implemented — every enquiry tool writes a `service_requests` row only |

## 7. Deferred / Not Yet Done

- **`POST /messages/{id}/preview`, `POST /turns/{id}/retry`** — the API
  plan's remaining 2 endpoints. `/process`'s existing idempotent replay
  covers the most common retry case; both would need a non-persisting
  pipeline variant that doesn't exist yet.
- **A centralized model-registry import module** — the "missing model
  imports" bug (§4 item 6) was fixed in-place five separate times this
  session rather than fixed once, centrally. A small `app/model_registry.py`
  (imported once by `conftest.py`, every `app/scripts/*.py`, and anywhere
  else that runs outside the normal FastAPI app lifecycle) would prevent
  this recurring permanently. Not done — flagged as a clear, low-risk
  follow-up.
- **Database backup/point-in-time recovery** — still not configured (see
  `docs/incidents/DATABASE_RECOVERY_REPORT.md`'s own outstanding-gap note).
  A real, open risk independent of Phase 4 itself.
- **Groq fallback**, real Tesseract OCR, real ClamAV, and a real Redis
  consumer remain unexercised against real infrastructure (Redis
  connectivity itself is now verified — see `docs/incidents/DATABASE_RECOVERY_REPORT.md`
  — but nothing in the app actually calls it yet; rate limiting is still
  the in-process placeholder from Phase 1).
- **Live authenticated dashboard click-through** — same limitation as
  Phase 3 (no test Supabase login credentials available this session).
