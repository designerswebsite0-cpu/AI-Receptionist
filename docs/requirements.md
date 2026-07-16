# requirements.md
# AI Receptionist Platform — Engineering Handbook (v2)

> Status: Living Engineering Specification
> Scope: Unified AI Receptionist Platform (Chat + Calls)
> Current Focus: WhatsApp + Web Chat
> Future Compatible: AI Voice Receptionist

---

# 1. Purpose

This document defines the engineering requirements, technology stack, infrastructure, deployment, development workflow and implementation standards for the AI Receptionist platform.

This platform is ONE product.

It consists of:

- AI Chat Receptionist
- AI Call Receptionist
- Customer 360
- Knowledge Intelligence Engine (KIE)
- Business Action Engine
- AI Orchestration Engine
- Analytics Engine

Every subsystem must be reusable across channels.

---

# 2. Engineering Principles

The platform must be:

- Production-ready
- Single-resort per deployment (Phase 2.5 — reusable template, not shared multi-tenant SaaS; see roadmap.md/product_decisions.md)
- API-first
- AI-first
- Security-first
- Modular Monolith
- Event-driven where appropriate
- Cloud-native
- Horizontally scalable
- Fully observable

Never optimize for shortcuts that create technical debt.

---

# 3. Supported Channels

Current:

- WhatsApp
- Website Live Chat

Future:

- AI Voice Calls
- Instagram
- Facebook Messenger
- Telegram
- Email

Every channel must use the same backend APIs and Customer 360.

---

# 4. Core Platform Engines

## Conversation Engine

Responsibilities:

- WhatsApp
- Web Chat
- Voice Calls
- Conversation state
- Human handoff
- Realtime inbox

## Customer 360 Engine

Responsibilities:

- Identity
- Preferences
- Behaviour
- Customer summary
- Value score
- Memory

## Knowledge Intelligence Engine (KIE)

Responsibilities:

- Knowledge ingestion
- OCR
- Chunking
- Embeddings
- Hybrid retrieval
- Confidence scoring
- Knowledge analytics
- Source versioning

Shared by BOTH chat and calls.

## Business Action Engine

Responsibilities:

- Bookings
- Orders
- Leads
- CRM
- Calendar
- Payments
- Notifications

## AI Orchestration Engine

Responsibilities:

- Prompt building
- Context assembly
- Tool orchestration
- Safety
- Fallback
- Response generation

## Analytics Engine

Responsibilities:

- Business analytics
- Customer analytics
- AI analytics
- Usage analytics
- Cost analytics

---

# 5. Technology Stack

## Backend

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- Alembic
- HTTPX

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod

## AI

Primary:

- OpenAI Responses API

Fallback:

- Groq

Embeddings:

- OpenAI text-embedding-3-large

## Database

- Supabase PostgreSQL
- Supabase Auth
- Supabase Realtime
- Supabase Storage
- pgvector
- PostgreSQL Full Text Search

## Redis

- Upstash Redis

## Queue

- Dramatiq

## Knowledge Intelligence Engine

Document Processing

- Docling
- PyMuPDF
- python-docx
- openpyxl
- pandas

Website Processing

- BeautifulSoup
- Trafilatura
- Playwright

OCR

- Tesseract OCR

Utilities

- langdetect
- tiktoken
- ClamAV

## Chat

- WhatsApp Cloud API
- Meta Webhooks
- Custom Web Widget

## Calls (Future)

Global

- Twilio
- LiveKit Cloud
- LiveKit Agents
- Deepgram
- ElevenLabs / Cartesia

India

- Vobiz
- LiveKit Cloud
- LiveKit Agents
- Deepgram
- Sarvam

## Integrations

- Google Calendar
- Resend
- Razorpay
- Stripe
- n8n

## Monitoring

- Sentry
- Better Stack
- Langfuse

---

# 6. Infrastructure

Backend
- Railway

Frontend
- Vercel

Database
- Supabase Cloud

Redis
- Upstash

Workflow Automation
- n8n Cloud

Voice Agent (future)
- LiveKit Cloud

Version Control
- GitHub

**Status:** GitHub, Railway, Vercel, and Supabase accounts are provisioned
and are the default infrastructure for all deployment, hosting, database,
and CI/CD work from this point forward. Do not substitute alternative
providers unless explicitly instructed.

**Single-resort deployment model (Phase 2.5):** each resort gets its own
Railway backend, Vercel frontend, and Supabase project/database — this
list of providers is the template every deployment reuses, not one shared
installation. Deploying a second resort means repeating this stack with a
fresh Supabase project and fresh environment variables, never adding a
second tenant to an existing one.

---

# 7. Docker Strategy

Docker is packaging, not hosting.

Services:

1. FastAPI API
2. Knowledge Worker
3. Voice Agent

Each service has its own Docker image.

---

# 8. Repository Structure

apps/
- api
- dashboard
- widget
- voice-agent

packages/
- shared-config
- shared-types
- shared-ui

docs/
- Goal.md
- requirements.md
- architecture.md
- knowledge.md
- database.md
- api.md
- functions.md
- CLAUDE.md
- rules.md
- roadmap.md
- product_decisions.md

---

# 9. Knowledge Intelligence Engine Requirements

Supported Sources

- PDF
- DOCX
- TXT
- Markdown
- CSV
- Excel
- Website
- FAQ
- Manual Knowledge
- Images

Pipeline

Upload
→ Malware Scan
→ OCR (if required)
→ Extraction
→ Cleaning
→ Chunking
→ Metadata
→ Embeddings
→ Full Text Index
→ Ready

Requirements

- Versioning
- Metadata
- Hybrid Retrieval
- Confidence scoring
- Analytics
- Source citations

---

# 10. Customer 360 Requirements

Must support:

- Identity resolution
- Preferences
- Behaviour
- Favourite products
- Favourite services
- Preferred timings
- Call history
- Chat history
- AI summary
- Staff notes
- Customer scoring
- Tags
- Cross-channel memory

---

# 11. AI Orchestration Requirements

Pipeline

Resolve Customer
→ Load Customer 360
→ Retrieve Knowledge
→ Build Context
→ LLM
→ Tool Validation
→ Tool Execution
→ Final Response

The LLM never writes directly to the database.

---

# 12. Security Requirements

Reference rules.md.

Mandatory:

- RLS (authenticated-user policies; single-resort per deployment, so no cross-tenant isolation concern — see rules.md)
- Webhook validation
- Rate limiting
- Audit logs
- Secret management
- Prompt injection protection
- Retrieval protection
- Idempotency

---

# 13. Environment Variable Groups

Backend

Database

AI

Knowledge Engine

WhatsApp

Voice

Redis

Monitoring

Payments

Security

Deployment

Only browser-safe values may be exposed through NEXT_PUBLIC variables.

---

# 14. Development Workflow

1. Design
2. Database
3. API
4. Backend
5. Frontend
6. Tests
7. Documentation
8. Deployment
9. Monitoring

Documentation is updated before implementation.

---

# 15. Testing Requirements

Backend

Frontend

Knowledge Engine

Customer 360

WhatsApp

Voice

Security

Load

Regression

---

# 16. CI/CD

GitHub
→ Lint
→ Tests
→ Build
→ Deploy Railway
→ Deploy Vercel

---

# 17. Feature Dependency Matrix

Chatbot
→ Customer360
→ KIE
→ AI
→ Conversations

Voice Agent
→ Customer360
→ KIE
→ AI

Dashboard
→ API
→ Realtime
→ Auth

Bookings
→ Business Action Engine

Knowledge Engine
→ Storage
→ Queue
→ Embeddings

---

# 18. External Service Inventory

OpenAI
- LLM
- Embeddings

Supabase
- Database
- Storage
- Auth
- Realtime

Railway
- Backend

Vercel
- Frontend

LiveKit
- Voice

Meta
- WhatsApp

Upstash
- Redis

n8n
- Automation

---

# 19. Performance Targets

Current

100–500 calls/day

100–500 conversations/day

Design for horizontal scaling without architectural changes.

---

# 20. Future Expansion

Instagram

Messenger

Telegram

Email

White-label SaaS

Enterprise SSO

Advanced AI analytics

Voice outbound campaigns

The architecture must support future expansion without redesigning the platform.
