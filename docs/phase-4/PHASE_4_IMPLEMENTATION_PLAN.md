# Phase 4 Implementation Plan — AI Orchestration & Conversational Intelligence Engine

> Status: written before implementation (per the Phase 4 brief's own process), reconciled directly against the repository — not assumed. Superseded by `PHASE_4_COMPLETION_REPORT.md` for final-state truth.

## 1. Reconciliation report (Step 1)

### What already exists and must be reused, not duplicated

- **`app/conversations/state_machine.py`** — its own docstring says: *"validating which transitions make business sense belongs to the Phase 4 AI Orchestration Engine... not to this storage/audit layer."* This is a direct, pre-existing hook for Phase 4. `transition_state()` (permissive, durable, audited via `ConversationStateEvent`) stays exactly as-is; Phase 4 adds a **validation layer on top**, not a parallel state store.
- **`conversations.current_state`** (`DIALOGUE_STATES`, 11 values: greeting, discovering_needs, collecting_information, recommending, booking, waiting, confirmation, upselling, support, escalation, closed) is documented as canonical in three places at once: `docs/functions.md` §28, `docs/architecture.md` §4.4, and `docs/database.md` §5. **This list is not being replaced.** The Phase 4 brief's much more granular state list (collecting stay details, comparing rooms, awaiting availability verification, restaurant-order collection, etc.) is real and useful, but it is a *finer-grained flow* **within** one of the 11 canonical states, not a competing top-level state machine — see §3 below for how this is reconciled.
- **`conversations.status`** (8 values incl. `escalated`) + `ai_active`/`human_active` booleans + `assigned_agent_id` already model the AI/human handoff *lifecycle*. Phase 4's handoff engine decides *when* to flip these, using `conversations.service.change_status`/`assign_conversation` (already implemented) — it does not need its own status column.
- **`ConversationStateEvent`** (`conversation_state_events` table) already stores `from_state`/`to_state`/`changed_by`/`event_metadata` (JSONB) for every transition. This is reused as the handoff-event record: transitioning to `escalation` with a rich `event_metadata` payload (reason, priority, department, summary, outstanding action) satisfies the brief's handoff-engine output requirements without a new table.
- **`app.messages`** already has `sender_type IN ('customer','ai','human','system')` and `content_type`/`delivery_status` — the AI's final response is just a `Message` row with `sender_type='ai'`, using the existing `messages.service`. No new message table.
- **`app.audit.service.record_audit_event`** — every orchestration decision that mutates state (tool execution, handoff, governance-relevant action) is audited through this, exactly like every other domain.
- **`app.knowledge.retrieval.service.search`** (Phase 3) is the stable retrieval interface: `search(db, *, query_text, embedding_provider, reranker, guest_only, limit, chunk_type, conversation_id, requested_channel, requested_by) -> SearchResponse`. Phase 4's context assembler calls this directly — it does not get its own retrieval path. `requested_channel`/`conversation_id` params already exist specifically so Phase 4 could log which conversation triggered a given retrieval.
- **`app.knowledge.embeddings.EmbeddingProvider`** / **`MockEmbeddingProvider`** is the established pattern for provider abstractions in this codebase (real implementation + deterministic mock, chosen explicitly by the caller, never auto-detected). Phase 4's `LLMProvider` abstraction follows the identical shape.
- **`docs/architecture.md` §4.4** already specifies an 8-step orchestration pipeline and, critically, names the provider policy explicitly: *"Call OpenAI as the primary provider. Use Groq according to explicit fallback policy."* — confirmed by `.env.example` already reserving `GROQ_API_KEY`. Phase 4's provider abstraction is OpenAI-primary/Groq-fallback, not a generic N-provider framework.
- **`docs/functions.md` §28** gives the exact function-name vocabulary already treated as authoritative by `CLAUDE.md`: `detect_guest_intent`, `classify_multi_intent`, `resolve_follow_up_intent`, `detect_small_talk`, `detect_sales_opportunity`, `extract_guest_entities`, `get_conversation_state`/`update_conversation_state`, `generate_personalized_recommendation`, `suggest_best_next_action`, `detect_missing_information`, `validate_booking_flow`, `detect_guest_sentiment`, `adapt_response_tone`, `identify_vip_guest`, `detect_urgent_situation`, `detect_upsell_opportunity`, `evaluate_handoff_requirement`, `summarize_conversation_for_staff`. Phase 4's module/function names follow this vocabulary directly rather than inventing parallel terminology.
- **Single-resort model unchanged**: `app.deps.get_current_user` remains the only auth check for every new endpoint. No `tenant_id`, no role checks, anywhere in Phase 4 code.

### Conflicts found and how they're resolved

1. **Granular flow states vs. canonical `DIALOGUE_STATES`.** Resolved by adding a new `flow_state` string column on `conversations` (nullable, no CHECK constraint — it's an orchestration-owned refinement of the current canonical `current_state`, not a governed enum) plus a validated-transition table describing which `flow_state` values are reachable from which `current_state`. `current_state`/`DIALOGUE_STATES` stay exactly as documented.
2. **No AI/orchestration module exists at all yet** (`app/conversations`, `app/messages`, `app/customers`, `app/knowledge` are the only domain modules) — Phase 4 is genuinely greenfield here, confirmed by directory listing, not assumed.
3. **No LLM provider code exists yet** (`app/knowledge/embeddings.py` is an *embedding* provider, unrelated). `openai_model`/`groq_api_key`/`groq_model` need to be added to `Settings` — `.env.example` already reserves the names, `config.py` does not yet read them.
4. **RBAC/tenant scaffolding**: confirmed absent — `app/roles`, `app/tenants` were fully removed in Phase 2.5 (migration `0008`). Nothing to reconcile; Phase 4 must simply not reintroduce them.

## 2. New database tables (2, not 10+)

Deliberately minimal — most of what the brief's step 2 domain model needs already has a home in existing tables (see §1). Two new tables cover what's genuinely new:

### `orchestration_turns`
One row per AI processing pass through the pipeline — the operationally-useful decision trace the brief asks for (explicitly **not** chain-of-thought):

```
id, conversation_id FK, message_id FK (the inbound guest message this turn responds to, nullable),
response_message_id FK (the outbound AI message, nullable until generated),
detected_intent, intent_confidence, secondary_intents JSONB (multi-intent),
extracted_entities JSONB, missing_entities JSONB,
flow_state, retrieval_query, citations JSONB (chunk_id + source_title + score, from CitationOut),
tool_name, tool_input JSONB, tool_output JSONB, tool_status,
handoff_required, handoff_reason, handoff_priority, handoff_department,
validation_result JSONB (flags raised, auto-fixed, blocked),
provider_used, model_used, latency_ms, token_usage JSONB, cost_estimate,
error_code, error_message, created_at
```

Guest-safety equivalent for this domain: `citations` and `retrieval_query` only ever reference chunks that were themselves already guest-filtered by `retrieval.service.search` — this table never needs its own visibility filter, it just records what the (already-safe) retrieval call returned.

### `service_requests`
The generic **"safe enquiry record, not a fake completed operation"** the brief requires for every `create_*_enquiry` tool (booking, dining, spa, activity, transfer, etc.) — one table, not one per domain, because Phase 7 (Business Action Engine) is where real per-domain integrations land; Phase 4 only needs to prove a request was captured and routed to staff, honestly:

```
id, conversation_id FK, customer_id FK, request_type (booking_enquiry | dining_enquiry |
  spa_enquiry | activity_enquiry | transfer_enquiry | service_request | complaint),
details JSONB, status (open | in_progress | resolved | cancelled),
created_by (ai | human), assigned_agent_id FK nullable, created_at, updated_at
```

Both tables get RLS via the same `auth.uid() IS NOT NULL` policy as every other table (migration pattern from `0019`), plus the same `UUIDPrimaryKeyMixin`/`TimestampMixin` conventions.

## 3. Module layout (`apps/api/app/orchestration/`)

```
orchestration/
  __init__.py
  constants.py                    # intent taxonomy, flow states, handoff reason codes
  domain.py                       # dataclasses: DetectedIntent, ExtractedEntities, RetrievedContext,
                                   # ToolDecision, HandoffDecision, SafetyDecision, OrchestrationResult
  models.py                       # OrchestrationTurn, ServiceRequest ORM models
  schemas.py                      # API request/response Pydantic models
  repository.py / service.py      # persistence + orchestration_turns/service_requests CRUD
  intent/
    classifier.py                 # detect_guest_intent, classify_multi_intent, detect_small_talk
    entities.py                   # extract_guest_entities — deterministic (dates/numbers/contacts)
                                   # + LLM-assisted (semantic fields)
  flow/
    states.py                     # flow_state taxonomy + allowed transitions per DIALOGUE_STATE
    engine.py                     # update_conversation_state (validated), missing-info detection
  context/
    assembler.py                  # token-budgeted context assembly (calls knowledge.retrieval.service)
    fixtures.py                   # representative mock retrieval fixtures shaped like real CitationOut output
  prompts/
    builder.py                    # modular prompt assembly, versioned
    templates/                    # identity, grounding, safety, citation, handoff rule blocks
  llm/
    base.py                       # LLMProvider protocol, LLMResult
    openai_provider.py             # primary
    groq_provider.py                # fallback
    mock_provider.py                 # deterministic, test-only
  tools/
    registry.py                       # typed tool definitions + permission metadata
    validation.py                      # deterministic validation of LLM-proposed tool calls
    handlers/                           # one handler per tool category, writing to service_requests
  handoff/
    engine.py                             # evaluate_handoff_requirement (deterministic policy)
  guardrails/
    validator.py                           # response validation pipeline (Step 10)
  pipeline.py                               # top-level orchestrate() — the channel-neutral entry point
  memory.py                                  # controlled memory read/write over Customer 360
  router.py                                   # API endpoints
```

## 4. Config additions (`app/config.py`)

```python
openai_model: str = "gpt-4o-mini"          # matches .env.example's OPENAI_MODEL placeholder name
groq_api_key: str | None = None
groq_model: str = "llama-3.3-70b-versatile"
orchestration_max_context_tokens: int = 4000
```

## 5. API design (Step 13)

All under `/api/v1/orchestration`, all requiring `get_current_user`:

- `POST /messages/{conversation_id}/process` — run the full pipeline for the latest guest message
- `POST /messages/{conversation_id}/preview` — run the pipeline without persisting the AI's message (staff dry-run)
- `GET  /conversations/{id}/state` — current `current_state`/`flow_state`/intent/entities
- `GET  /conversations/{id}/turns` — orchestration_turns history (the decision trace)
- `GET  /turns/{id}/citations`
- `GET  /turns/{id}/tool-executions`
- `POST /conversations/{id}/handoff` — force handoff
- `POST /conversations/{id}/release` — release back to AI
- `POST /turns/{id}/retry`
- `GET  /health/providers` — LLM/embedding provider reachability, never secrets

## 6. Worker design

No new background-job infrastructure is required this phase: orchestration runs synchronously within the request/response cycle of `POST /messages/{id}/process` (same pattern as Phase 3's synchronous upload-and-index endpoint). If WhatsApp webhook-driven processing (Phase 6) later needs async execution, it can reuse `app.knowledge.jobs`' Redis-vs-inline pattern — not built speculatively now.

## 7. Testing plan (Step 15)

Mirrors Phase 3's discipline exactly: pure-logic unit tests (intent classification, entity parsing, flow-state transitions, prompt builder, guardrail rules) run everywhere; DB-backed integration tests (pipeline end-to-end, handoff persistence, service_requests creation) use the same `db_session` fixture and skip locally/run in CI; a dedicated security test file (prompt-injection-in-retrieved-content, tool-permission bypass attempts, cross-conversation data leakage). `MockLLMProvider` + `MockEmbeddingProvider` throughout — no real API calls in the automated suite, matching the Phase 3 brief's rule carried forward.

### Real-data validation checklist (cannot be honestly executed until `OPENAI_API_KEY` is added and the RKPR corpus is embedded)

Tracked as a standing checklist in `PHASE_4_COMPLETION_REPORT.md`, not silently deferred: common guest questions, room comparison, occupancy, private-pool questions, meal plans, restaurant menu/pricing, allergens/dietary, spa/activity pricing, airport transfers, cancellation/payment policy, check-in/out, accessibility, offers, conflicting/superseded info, no-answer questions, multi-intent messages, follow-ups, ambiguous messages, incorrect guest assumptions, citation relevance, prompt-injection-in-retrieved-content, hallucination spot-checks, handoff-decision spot-checks.

## 8. Risks

- **Flow-state proliferation**: the brief's ~24 granular states risk becoming an unvalidated free-for-all if not constrained. Mitigated by keeping `flow_state` transitions validated in code (§3), not a DB enum, but still enforced — never LLM-settable without going through `flow.engine`.
- **Tool scope creep into fake operations**: mitigated by the `service_requests` generic-record design (§2) — no tool this phase claims a booking, payment, or refund succeeded.
- **Provider cost during testing**: `MockLLMProvider` is the default everywhere except an explicit, human-approved smoke test — mirrors how Phase 3's embedding costs were handled (asked before spending, not assumed).
- **Context assembler quality is fundamentally unvalidatable without real embeddings** — explicitly tracked as provisional, not silently treated as done (see §7's real-data checklist).
