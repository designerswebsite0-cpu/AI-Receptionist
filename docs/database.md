# database.md
# AI Receptionist Platform Database Specification (v1)

> Status: Living Database Specification
> Database: PostgreSQL (Supabase)
> Architecture: Multi-Tenant SaaS
> Shared By: Chat + Calls + Customer360 + Knowledge Intelligence Engine (KIE)

---

# 1. Database Philosophy

The database is the single source of truth for the platform.

Design Principles:

- Multi-tenant
- UUID primary keys
- Row Level Security (RLS)
- Highly normalized
- Audit friendly
- AI friendly
- Future proof
- Soft deletes where appropriate

---

# 2. Core Database Domains

- Tenant
- Authentication
- Customer360
- Conversations
- Messages
- Voice
- Knowledge Intelligence Engine
- Business Actions
- Analytics
- AI
- Audit
- System

---

# 3. Tenant Module

Tables

- tenants
- tenant_settings
- tenant_members
- tenant_roles
- tenant_permissions

Every table references tenant_id.

---

# 4. Customer360 Module

Tables

- customers
- customer_preferences
- customer_behaviour
- customer_addresses
- customer_notes
- customer_tags
- customer_scores
- customer_favourite_products
- customer_favourite_services
- customer_booking_history
- customer_order_history
- customer_ai_summary
- customer_timelines

Shared across Chat and Calls.

---

# 5. Conversation Module

Tables

- conversations
- conversation_participants
- conversation_states
- messages
- message_attachments
- conversation_labels
- conversation_assignments
- conversation_events
- conversation_ai_context

Supports:

- WhatsApp
- Web Chat
- Voice

---

# 6. Voice Module

Tables

- calls
- call_recordings
- call_transcripts
- call_events
- call_metrics

Future LiveKit integration.

---

# 7. Knowledge Intelligence Engine

Tables

- knowledge_sources
- knowledge_source_versions
- knowledge_documents
- knowledge_chunks
- knowledge_embeddings
- knowledge_entities
- knowledge_keywords
- knowledge_tags
- knowledge_jobs
- knowledge_job_logs
- knowledge_feedback
- knowledge_search_logs
- knowledge_missing_answers
- knowledge_retrieval_logs
- knowledge_citations

Shared by BOTH chat and calls.

---

# 8. Business Action Module

Tables

- bookings
- booking_events
- orders
- order_items
- payments
- payment_events
- leads
- notifications
- calendar_events
- crm_sync_logs

---

# 9. Analytics Module

Tables

- analytics_events
- business_metrics
- customer_metrics
- conversation_metrics
- ai_metrics
- knowledge_metrics
- token_usage
- provider_usage
- cost_tracking

---

# 10. AI Module

Tables

- ai_requests
- ai_responses
- tool_calls
- tool_results
- prompt_versions
- system_prompts
- model_usage
- fallback_logs

---

# 11. Audit Module

Tables

- audit_logs
- login_logs
- security_events
- permission_changes
- api_logs
- webhook_logs

---

# 12. Storage Buckets

- documents
- recordings
- attachments
- avatars
- exports
- temporary

---

# 13. Relationships

Tenant
→ Customer360
→ Conversations
→ Messages
→ Business Actions
→ Analytics

Knowledge
→ Documents
→ Chunks
→ Embeddings
→ Retrieval
→ AI

---

# 14. Indexing

Index:

- tenant_id
- customer_id
- conversation_id
- email
- phone_number
- created_at
- updated_at
- booking_date
- knowledge_source_id
- pgvector embeddings
- PostgreSQL FTS

---

# 15. Security

- Enable RLS on every table
- Tenant isolation mandatory
- Parameterized queries only
- Foreign keys enforced
- Audit critical actions
- Soft deletes for critical entities

---

# 16. Background Jobs

Track:

- OCR
- Document parsing
- Embedding generation
- Knowledge indexing
- Notifications
- AI retries
- Analytics aggregation

---

# 17. Data Retention

Configurable per tenant:

- Chat history
- Call history
- Knowledge versions
- Audit logs
- Analytics retention

---

# 18. Performance

- UUID keys
- Indexed foreign keys
- Pagination
- Batch operations
- Connection pooling
- Optimized vector search
- Avoid N+1 queries

---

# 19. Future Expansion

- Instagram
- Messenger
- Telegram
- Email
- CRM integrations
- ERP integrations
- White-label SaaS
- Enterprise SSO

---

# Database Principles

Every table must be:

✓ Tenant aware
✓ Secure
✓ Auditable
✓ Indexed
✓ Scalable
✓ Customer360 compatible
✓ KIE compatible
✓ Future proof
