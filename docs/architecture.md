AI Receptionist Platform Architecture

Unified Chat + Voice System --- Architecture Specification v1.0

Status: Living engineering specification

Current build focus: WhatsApp and web chat

Future-compatible scope: AI voice calls

Target scale: 100--500 conversations per day and 100--500 calls per day

1\. Purpose and architectural position

The AI Receptionist is one multi-tenant platform with several
communication channels. WhatsApp, website chat, and voice calls are not
separate products. They are channel adapters that connect to the same
backend, customer memory, business knowledge, action tools, permissions,
analytics, and audit system.

The current implementation begins with chat, but the shared platform
must be designed so the LiveKit voice agent can later call the same APIs
without restructuring the product.

The architecture is a modular monolith. One FastAPI backend contains
clearly separated domain modules. This keeps the first production
version understandable and deployable while preserving boundaries that
allow high-load modules to be extracted later.

2\. Core architectural principles

One customer identity across every channel.

One Customer 360 profile across chat and calls.

One Knowledge Intelligence Engine shared by chat and calls.

One Business Action Engine for bookings, orders, leads, payments, CRM,
and notifications.

The LLM proposes actions; trusted backend code validates and executes
them.

Tenant isolation is enforced in the API, database, storage, retrieval,
realtime channels, background jobs, and caches.

All important actions are idempotent and auditable.

Managed infrastructure is preferred at the current scale.

Docker packages backend processes; Railway and LiveKit Cloud provide
hosting.

Security and reliability are product features, not later additions.

3\. High-level system

Customer channels:

WhatsApp through Meta WhatsApp Cloud API.

Website chat through a custom embeddable widget.

Voice calls through Twilio or Vobiz, LiveKit Cloud, and a Python LiveKit
Agent.

Shared platform:

FastAPI API and domain services.

Customer 360 Engine.

Knowledge Intelligence Engine.

AI Orchestration Engine.

Business Action Engine.

Conversation Engine.

Analytics Engine.

Supabase PostgreSQL, Auth, Storage, Realtime, pgvector, and Full-Text
Search.

Upstash Redis.

Dramatiq knowledge and background workers.

n8n integrations.

Frontends:

Next.js staff dashboard.

Embeddable web-chat widget.

Both hosted on Vercel.

4\. Six core engines

4.1 Conversation Engine

The Conversation Engine owns the channel-neutral interaction lifecycle.

Responsibilities:

Create and resolve conversations.

Normalize messages and call events.

Save inbound, AI, and human messages.

Track delivery and read statuses.

Manage conversation ownership.

Manage AI and human handoff.

Maintain channel-specific metadata without duplicating business logic.

Broadcast realtime updates to the dashboard.

Provide recent context to the AI Orchestrator.

Conversation states:

AI_ACTIVE --- AI responds automatically.

HUMAN_ACTIVE --- a staff member controls replies and AI sending is
disabled.

AI_ASSIST --- AI drafts suggestions but a human sends them.

WAITING_FOR_CUSTOMER --- no action until the customer replies.

RESOLVED --- conversation is completed.

BLOCKED --- conversation cannot receive automated processing.

All state transitions must be authorized, atomic, timestamped, and
recorded in the audit log.

4.2 Customer 360 Engine

Customer 360 is the cross-channel customer intelligence system. A phone
number, WhatsApp identity, verified email, authenticated web identity,
or CRM identifier can resolve to one customer profile.

The system stores:

Name and contact details.

Preferred language and channel.

Verified preferences and inferred preferences.

Favourite products, services, and orders.

Usual dates, days, and timings.

Booking, order, call, and chat history.

Total spend, average order value, frequency, recency, and value score.

VIP status, churn-risk score, lead score, and tags.

Complaints, sentiment patterns, staff notes, and consent records.

A concise AI-generated customer brief.

Memory has three layers:

Structured verified memory for durable facts.

AI-generated customer brief for compact personalization.

Relevant recent memory for active context.

AI inferences must include source, confidence, and verification state.
An uncertain inference must not silently become a verified fact.

4.3 Knowledge Intelligence Engine

The Knowledge Intelligence Engine, or KIE, is the shared RAG system for
both chat and calls. A tenant uploads or connects knowledge once, and
every supported channel uses the same indexed knowledge.

Supported sources:

PDF, DOCX, TXT, and Markdown.

CSV and Excel.

Menus, catalogues, price lists, and images.

Website pages and sitemaps.

Manual FAQ and knowledge entries.

Future connectors such as Google Drive, Notion, Shopify, CRM, and
SharePoint.

Ingestion pipeline:

Verify tenant and permission.

Validate MIME type, extension, file signature, and size.

Malware scan with ClamAV.

Save the original source to private Supabase Storage.

Create a versioned processing job.

Parse with Docling as the primary parser.

Use PyMuPDF, python-docx, openpyxl, pandas, or OCR as controlled
fallbacks.

Crawl approved websites using Trafilatura, Beautiful Soup, and
Playwright when rendering is necessary.

Detect language and document structure.

Clean, deduplicate, and normalize content.

Preserve headings, sections, lists, tables, pages, and source metadata.

Create semantic, token-aware chunks using tiktoken.

Generate embeddings through the configured OpenAI embedding model.

Store chunks and vectors in PostgreSQL and pgvector.

Build PostgreSQL Full-Text Search indexes.

Mark the knowledge version READY only after validation.

Retrieval pipeline:

Resolve tenant and authorized knowledge scope.

Classify the request and identify structured-data needs.

Apply metadata and source filters.

Query structured business data where available.

Run PostgreSQL Full-Text Search for exact terms.

Run pgvector semantic search for meaning.

Merge and deduplicate candidates.

Apply weighted hybrid ranking.

Optionally rerank if evaluation proves it is useful.

Assemble a limited, source-attributed context package.

Return confidence, evidence, and source identifiers to the AI
Orchestrator.

Retrieved documents are untrusted data. Text inside a source cannot
override system instructions, authorize actions, expose secrets, or
change tenant scope.

4.4 AI Orchestration Engine

The AI Orchestrator is the controlled reasoning layer.

docs/functions.md is the Business Tool Layer, not the AI's intelligence.
The AI must never rely solely on function calls; every response follows
this reasoning pipeline before, around, and after any tool call:

1. Understand user intent (detect_guest_intent, classify_multi_intent,
   resolve_follow_up_intent, detect_small_talk, detect_sales_opportunity).
2. Extract entities (extract_guest_entities).
3. Determine conversation state (get_conversation_state /
   update_conversation_state — Greeting, Information Gathering,
   Recommendation, Booking, Payment, Confirmation, Upselling, Support,
   Escalation, Closed).
4. Retrieve relevant knowledge using RAG (Knowledge Intelligence Engine —
   see docs/functions.md §29 RAG Knowledge Domains).
5. Decide whether backend verification is required.
6. Call the appropriate business function if needed (docs/functions.md
   §1–27 — the Business Action Engine's concrete tool catalog).
7. Generate a natural human response (tone adapted via emotional
   intelligence — detect_guest_sentiment, adapt_response_tone,
   identify_vip_guest, detect_urgent_situation).
8. Update guest memory when appropriate (docs/functions.md §30 — shared
   with Customer 360, never a separate memory store).

This pipeline is channel-neutral and business-vertical-neutral: the current
implementation targets a luxury resort (docs/Goal.md), but a future
non-resort tenant only swaps its functions.md/knowledge base, not this
pipeline.

Processing flow:

Resolve tenant, channel, customer, and conversation.

Load tenant settings and prompt version.

Load relevant Customer 360 information.

Retrieve relevant recent conversation context.

Retrieve business knowledge through KIE.

Register only tools permitted for the tenant, user, channel, and
conversation mode.

Build the model request.

Call OpenAI as the primary provider.

Use Groq according to explicit fallback policy.

Validate any tool call using strict schemas.

Authorize and execute tools in backend services.

Feed tool results back to the model.

Run response safety and grounding checks.

Save model, token, latency, retrieval, and tool metadata.

Deliver the final response through the channel adapter.

The LLM never writes directly to the database and never decides
authorization. It cannot claim a booking, payment, order, cancellation,
refund, or message succeeded unless the backend confirms success.

4.5 Business Action Engine

The Business Action Engine contains deterministic services and
integration adapters.

Initial tools:

Check availability.

Create, update, and cancel bookings.

Capture and qualify leads.

Create support tickets.

Create draft orders.

Check order status.

Generate approved payment links.

Add verified customer preferences.

Add internal customer notes.

Notify staff.

Sync to Google Calendar.

Sync to CRM and n8n workflows.

Every tool definition includes:

Typed input and output schema.

Tenant scope.

Required role or service permission.

Business-rule validation.

Idempotency behavior.

Timeout and retry policy.

Human-approval requirement.

Audit event.

Safe customer-facing failure message.

4.6 Analytics Engine

The Analytics Engine records and aggregates:

Conversation and call volume.

Resolution and human-handoff rate.

Booking, order, and lead conversion.

Average response time and AI latency.

STT, LLM, and TTS latency for calls.

Failed messages and failed tools.

Retrieval confidence and knowledge gaps.

Popular questions, services, and products.

Returning and high-value customers.

Staff workload.

Token, provider, storage, and telephony cost per tenant.

AI quality and fallback usage.

Analytics must not bypass tenant isolation or expose sensitive raw
content unnecessarily.

5\. Channel architecture

5.1 Normalized interaction model

Each channel adapter converts its provider-specific event into a
standard internal event containing:

Tenant ID resolved by the server.

Channel.

External event ID.

External customer identity.

Conversation ID.

Message or event type.

Text or structured content.

Attachments.

Timestamp.

Provider metadata.

The rest of the platform operates on this model.

5.2 WhatsApp flow

Customer sends a WhatsApp message.

Meta sends a signed webhook event to FastAPI on Railway.

The webhook signature and phone-number mapping are verified.

The external event ID is checked for idempotency.

Media is validated and downloaded when required.

The normalized event is saved.

Customer 360 and the conversation are resolved.

The AI Orchestrator processes the request unless a human controls the
conversation.

The response is sent through the official WhatsApp Cloud API.

Delivery updates are saved.

Supabase Realtime updates the staff inbox.

The dashboard is the business's team inbox. Staff can take over, assign,
note, reply, and return control to AI. The product does not rely on
unofficial WhatsApp Web automation.

5.3 Website chat flow

A client website loads the Vercel-hosted widget.

The widget obtains a signed tenant- and domain-bound session token.

The customer sends a message to FastAPI.

The backend resolves an anonymous or authenticated identity.

The same Conversation Engine, Customer 360, KIE, and AI Orchestrator are
used.

Responses stream to the widget through Server-Sent Events.

The dashboard receives realtime events.

A temporary identity can later be merged with a verified customer after
consent and verification.

5.4 Voice-call flow

A customer calls a Twilio or Vobiz number.

The telephony provider routes the call by SIP to LiveKit Cloud.

LiveKit creates a room according to an inbound trunk and dispatch rule.

A Dockerized Python LiveKit Agent hosted by LiveKit Cloud joins the
room.

The agent receives the caller identity and calls shared FastAPI APIs.

Customer 360 and KIE provide personalized context and grounded
knowledge.

Speech-to-text, LLM, and text-to-speech providers process the
conversation.

Business actions use the same backend tools as chat.

Call events, transcript, outcome, and consent records are saved.

LiveKit Egress exports the recording to private storage.

The final summary updates Customer 360.

Global voice providers:

Twilio Elastic SIP Trunking.

Deepgram.

OpenAI with Groq fallback.

ElevenLabs or Cartesia.

India voice providers:

Vobiz.

Deepgram for English-heavy traffic.

Sarvam speech recognition for Indian languages and Hinglish.

OpenAI with Groq fallback.

Sarvam Bulbul V3.

6\. Data architecture

Supabase PostgreSQL is the source of truth.

Core domains:

Tenants, tenant settings, and tenant integrations.

Users, staff, roles, and permissions.

Customers, identities, preferences, scores, summaries, notes, and tags.

Conversations, participants, assignments, handoffs, messages,
attachments, and delivery events.

Calls, recordings, transcripts, and call events.

Knowledge sources, versions, documents, chunks, processing jobs,
queries, retrieval results, feedback, and gaps.

Bookings, orders, leads, support tickets, and notifications.

Tool executions, webhook events, idempotency records, usage records,
consent records, and audit logs.

Every tenant-owned record contains tenant_id. Important relationships
use foreign keys, unique constraints, check constraints, and explicit
deletion behavior.

Supabase Storage uses private buckets for:

Tenant assets.

Knowledge originals.

Customer uploads.

Chat attachments.

Voice notes.

Call recordings.

Generated exports.

Only authorized backend code generates short-lived signed URLs.

7\. Realtime architecture

Supabase Realtime powers the staff dashboard for:

New messages.

Message status updates.

Conversation state changes.

Assignments.

Customer-profile changes.

Typing indicators.

Staff presence.

AI-processing status.

Realtime channels are private and tenant-scoped. Raw broad database
subscriptions must not expose data outside the authorized tenant.

8\. Redis, concurrency, and idempotency

Upstash Redis is used for:

Rate limiting.

Webhook deduplication.

Conversation processing locks.

AI response locks.

Staff takeover locks.

Temporary web-chat sessions.

Short-lived retrieval and configuration caches.

Dramatiq broker operations.

Retry counters.

Redis is not the permanent source of truth.

Critical side effects also record durable idempotency state in
PostgreSQL. A retried WhatsApp event, booking request, payment request,
call-completion event, or CRM sync must not create duplicate actions.

9\. Background processing

Dramatiq workers run separately from the FastAPI web process.

Worker responsibilities:

Knowledge parsing, OCR, chunking, and embeddings.

Website ingestion.

Customer-summary regeneration.

Analytics aggregation.

Retryable provider synchronization.

File processing and malware scan orchestration.

Non-immediate notifications.

FastAPI returns quickly after validating and enqueueing long-running
work. Worker jobs carry tenant context, correlation ID, idempotency key,
attempt count, and trace metadata.

n8n is used for external automations such as CRM updates, reminders,
staff notifications, and follow-up workflows. Authorization and critical
business validation remain in FastAPI.

10\. Backend module boundaries

Recommended FastAPI modules:

auth

tenants

users

roles

customers

customer_360

conversations

messages

whatsapp

webchat

calls

knowledge

ai

tools

bookings

orders

leads

support

integrations

notifications

analytics

audit

security

common

Typical internal flow:

Router → Application service → Domain service → Repository or provider
adapter.

Channel routers must not contain business logic. Provider adapters must
not decide tenant permissions. Repositories must not bypass tenant
filters.

11\. Deployment architecture

11.1 Chat backend

FastAPI source code is packaged with Docker and hosted on Railway.

Flow:

Source code → Dockerfile → Railway build → running API container.

Railway provides compute, networking, health checks, logs, restarts,
environment variables, and scaling. Docker is not a second host.

11.2 Knowledge worker

The knowledge worker is a separate Railway service. It may use the same
repository and base image as the API but starts a Dramatiq worker
command instead of Uvicorn.

Separating API and worker processes prevents large OCR or embedding jobs
from blocking chat webhooks.

11.3 Dashboard and widget

The Next.js dashboard and embeddable widget are hosted on Vercel. The
frontend uses public Supabase settings only. Secrets and privileged
operations remain in FastAPI.

11.4 Voice agent

The Python LiveKit Agent has its own Dockerfile and is deployed using
the LiveKit CLI. LiveKit Cloud builds and runs the container and
dispatches agent workers to calls. The agent calls FastAPI for Customer
360, knowledge, business actions, and persistence.

11.5 Managed services

Supabase Cloud hosts PostgreSQL, Auth, Storage, Realtime, pgvector, and
FTS.

Upstash hosts Redis.

Meta hosts WhatsApp Cloud API.

n8n Cloud hosts initial automation workflows.

Sentry provides exceptions and traces.

Better Stack provides logs and uptime monitoring.

Langfuse provides LLM traces and evaluation metadata.

12\. Security architecture

Security is enforced in layers:

TLS for all external and internal traffic.

Supabase Auth for dashboard sessions.

MFA for privileged roles.

Backend role and permission checks.

PostgreSQL Row Level Security.

Tenant-scoped storage and signed URLs.

Tenant-scoped realtime channels.

Webhook signature verification.

Rate limiting and abuse detection.

Strict Pydantic and Zod validation.

File signature, MIME, size, and malware validation.

Secret storage in managed environment variables.

Encryption for provider credentials and sensitive fields.

Audit logs for sensitive reads and writes.

Data-retention and deletion policies.

Consent recording for calls and sensitive processing.

KIE-specific protections:

Retrieved content is never treated as instructions.

Website crawlers block private, loopback, link-local, and
metadata-service addresses.

Redirects and crawl depth are constrained.

Cross-tenant vector search is impossible by query construction and RLS.

Deleted source versions remove or deactivate associated chunks and
embeddings.

Sensitive secrets must not be embedded.

Prompt-injection and retrieval-poisoning tests are mandatory.

13\. Reliability and failure handling

LLM failure:

Apply a bounded retry for safe failures.

Use Groq fallback according to policy.

Do not rerun completed tool actions.

Escalate or send a safe temporary response.

WhatsApp failure:

Save outbound state.

Retry only within provider rules.

Record terminal failure and notify staff for important conversations.

Knowledge failure:

Keep the previous READY version active during reprocessing.

Mark the new job FAILED with a clear reason.

Allow safe reprocessing.

Never expose partially processed knowledge as ready.

Business-tool failure:

Do not claim success.

Return a structured failure to the orchestrator.

Preserve idempotency state.

Escalate when required.

Database failure:

Fail safely.

Avoid false confirmations.

Keep correlation and idempotency information for recovery.

14\. Observability

Every important request carries:

Correlation ID.

Tenant ID.

Customer ID when known.

Conversation or call ID.

Provider event ID.

Model and provider.

Latency.

Tool calls.

Retrieval result identifiers.

Retry count.

Outcome.

Sensitive message content, transcripts, secrets, payment data, and
private notes must not be dumped into logs by default.

Alerts should cover:

API downtime.

Webhook failure rate.

Message-delivery failure.

AI latency and error rate.

Knowledge-worker backlog.

Document-processing failure.

Database saturation.

Redis failure.

Call connection and provider failures.

Abnormal tenant cost or traffic.

15\. Performance and scale

Initial production target:

100--500 conversations per day.

Approximately 3,000--15,000 inbound chat messages per day.

100--500 calls per day.

Horizontal scaling without redesign.

Initial strategy:

One modular FastAPI application with multiple Railway replicas when
required.

Separate Dramatiq workers.

Managed Redis.

LiveKit Cloud agent workers.

Supabase connection pooling and indexes.

Bounded retrieval result sets.

Compact Customer 360 context.

Cached tenant configuration.

Streaming web-chat responses.

Advanced infrastructure such as Kubernetes, Temporal, Kafka,
multi-region databases, or a dedicated vector database is not required
initially. It is introduced only after measured bottlenecks or stronger
reliability requirements justify it.

16\. Scaling evolution

When concurrency grows:

Increase Railway API replicas.

Increase knowledge and background workers.

Add stronger database pooling and query analysis.

Partition high-volume event and message tables if needed.

Add read replicas or analytics storage when justified.

Move large recording archives to Cloudflare R2 if storage and egress
economics require it.

Extract only proven high-load modules.

Add Prometheus and Grafana when operational scale requires deeper
metrics.

Consider Temporal for critical long-running workflows.

Consider Kubernetes only when the number of services and operational
team justify it.

17\. Architecture decision rules

Before adding a feature, answer:

Which core engine owns it?

Can both chat and calls reuse it?

Does it update Customer 360?

Does it require KIE?

Which tenant and permission boundaries apply?

Does it create a side effect requiring idempotency?

Does it require an audit event?

Can it fail without giving a false confirmation?

What tests prove cross-tenant safety?

Can managed infrastructure handle it at the current scale?

18\. Initial implementation sequence

Phase 1 --- Repository, environments, CI, authentication, tenants,
roles, RLS, audit foundation.

Phase 1 implementation notes (added once built, kept in sync with code):

Auth is implemented as a backend proxy to Supabase GoTrue rather than
direct client-side Supabase Auth calls. The dashboard, widget, and future
voice-agent all authenticate through `/api/v1/auth/*` on the FastAPI
backend, so every login/logout is uniformly audited and no client needs
Supabase keys for authentication. JWTs are verified against the project's
published JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), cached
in-process; a Redis-backed shared cache is deferred until Upstash is wired
in Phase 3.

RLS policies are enabled on every tenant-owned table (tenants,
tenant_settings, tenant_members, tenant_roles, tenant_permissions, users,
audit_logs) as defense-in-depth for any direct Postgres access path
(Supabase Realtime, future connectors). The FastAPI backend itself is the
primary authorization gate: it resolves tenant context only from a
URL-supplied tenant_id that has been checked against the caller's own
`tenant_members` row, never trusted blindly, per rules.md §5.

Rate limiting on `/auth/login` is an in-process token bucket in Phase 1
(does not share state across API replicas) — an explicit interim measure
until Upstash Redis lands in Phase 3+.

Phase 2 --- Customer identities, Customer 360, conversations, messages,
and realtime events.

Phase 2 implementation notes (added once built, kept in sync with code):

Realtime events are not implemented yet — Phase 2 built the durable
storage and REST APIs (list/get/search/filter/paginate conversations,
send message, mark read, assign, change status/state) that a Supabase
Realtime layer will subscribe to later; the dashboard inbox UI and
Realtime wiring are follow-on work, not part of this phase's brief.

Every tenant-owned resource added this phase (customers, conversations,
messages, and their child tables) follows the same URL convention Phase 1
established for tenant members: nested under
`/api/v1/tenants/{tenant_id}/...`, with tenant_id resolved from the URL but
verified against the caller's own membership before use
(`app.deps.get_current_membership`) — never trusted blindly. This
supersedes the flat `/api/v1/customers`, `/api/v1/conversations` sketches
in an earlier api.md draft.

A conversation carries two independent pieces of state, not one:
`status` is the lifecycle/queue state a staff inbox filters by (`open`,
`waiting_for_guest`, `waiting_for_staff`, `ai_handling`, `human_handling`,
`escalated`, `closed`, `blocked`); `current_state` is where the AI
reasoning pipeline (§4.4 above) is in the conversation (`greeting` through
`closed`, matching docs/functions.md's Conversation State list). The
original architecture draft's AI_ACTIVE/HUMAN_ACTIVE/AI_ASSIST/
WAITING_FOR_CUSTOMER/RESOLVED/BLOCKED vocabulary is superseded by `status`
plus the independent `ai_active`/`human_active` boolean pair — the flags
capture AI_ASSIST-style overlap (AI drafts, human sends) that a single
enum can't, without needing a ninth status value. `BLOCKED` is the one
value carried over unchanged, since rules.md requires a way to halt
automated processing entirely and the Phase 2 brief didn't restate it.

Message attachments are metadata rows only this phase (a `storage_path`
into a private Supabase Storage bucket the caller populated some other
way) — there is no upload endpoint until Phase 3 wires real Storage
handling for the Knowledge Intelligence Engine.

Phase 3 --- Knowledge Intelligence Engine ingestion, processing worker,
embeddings, hybrid retrieval, and knowledge dashboard.

Phase 4 --- AI Orchestration Engine, prompts, tools, fallback, safety,
and evaluation.

Phase 5 --- Web-chat widget and staff inbox.

Phase 6 --- WhatsApp Cloud API, media, templates, status events,
idempotency, and human takeover.

Phase 7 --- Bookings, leads, CRM, calendar, payments, notifications, and
analytics.

Phase 8 --- LiveKit voice agent, telephony, recordings, transcripts, and
shared Customer 360/KIE integration.

Phase 9 --- Load testing, security review, disaster recovery, billing,
and production hardening.

19\. Final architectural invariant

The platform must always remain one unified receptionist.

A fact learned in chat can personalize a future call. A preference
learned during a call can improve a later WhatsApp interaction. A
business updates knowledge once, and both voice and chat use the same
approved version. Human staff see the complete customer and conversation
history in one secure dashboard.

Any implementation that creates separate customer memories, separate
business knowledge, separate action logic, or disconnected analytics for
chat and calls violates the architecture and must be redesigned.
