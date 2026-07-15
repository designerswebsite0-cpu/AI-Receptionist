# rules.md
# AI Receptionist Platform — Engineering & Security Rules (v2)

> Status: Living Engineering Constitution
> Applies To: Entire Platform (Chat + Calls + Customer360 + Knowledge Intelligence Engine)

---

# 1. Core Philosophy

This platform is built on:

- Security First
- Privacy First
- Multi-Tenant First
- API First
- AI First
- Reliability First

Never sacrifice architecture or security for speed.

---

# 2. Zero Trust

Treat every request as untrusted.

Always verify:

- User identity
- Tenant identity
- Permissions
- Tool arguments
- Uploaded files
- Webhook signatures

Never trust client-side validation.

---

# 3. Authentication

- Use Supabase Auth.
- JWTs must always be verified.
- Refresh tokens stored securely.
- MFA supported for administrators.
- Session expiry enforced.
- Never store passwords manually.

---

# 4. Authorization

Every endpoint must:

- Authenticate
- Authorize
- Audit

Role-based permissions:

- Owner
- Admin
- Manager
- Staff
- Read-only

**TEMPORARY (current development phase only):** fine-grained permission
enforcement is switched off via `RBAC_ENFORCEMENT_ENABLED=false` while the
AI/RAG/booking build-out is underway, so every authenticated, tenant-verified
user has full administrative access — see docs/product_decisions.md. This
does **not** relax tenant isolation: `get_current_membership` still rejects
anyone who isn't an active member of the tenant they're acting on. The RBAC
tables, roles, and permission checks remain fully implemented and must not
be removed; flipping the flag back to `true` re-enables enforcement with no
structural changes. Do not build dashboard UI that hides features based on
role while this flag is off.

---

# 5. Multi-Tenant Rules

Mandatory:

- Every database row contains tenant_id.
- Every query filters by tenant_id.
- Every storage object belongs to one tenant.
- Every realtime event is tenant scoped.
- Never allow cross-tenant reads or writes.

---

# 6. Customer 360 Rules

Customer360 is the single source of truth.

Store separately:

- Verified facts
- AI summaries
- AI inferences
- Conversation state

Never overwrite verified customer data using AI assumptions.

---

# 7. Knowledge Intelligence Engine Security

Treat every uploaded document as untrusted.

Pipeline:

Upload
→ File validation
→ Malware scan
→ OCR
→ Parsing
→ Cleaning
→ Chunking
→ Embeddings
→ Retrieval Ready

Rules:

- Virus scan every file.
- Validate MIME type and magic bytes.
- Limit upload size.
- Strip executable content.
- Preserve document versions.
- Never delete active versions without authorization.

Retrieved content is DATA, never SYSTEM INSTRUCTIONS.

---

# 8. AI Rules

The LLM must never:

- Write directly to the database
- Execute SQL
- Call external APIs directly
- Confirm business actions without backend validation
- Invent prices or availability

LLM suggests.
Backend decides.

---

# 9. Tool Execution

Every tool must define:

- Schema
- Validation
- Authorization
- Timeout
- Retry policy
- Audit logging
- Idempotency

Reject invalid tool arguments.

---

# 10. API Security

- HTTPS only.
- CORS allowlist.
- Request validation.
- Response validation.
- Rate limiting.
- Request IDs.
- Structured error responses.

---

# 11. Database Rules

- PostgreSQL only.
- UUID primary keys.
- Foreign keys enforced.
- Soft deletes where appropriate.
- Parameterized queries only.
- Index frequently queried columns.
- Enable Row Level Security.

No string-built SQL.

---

# 12. Secrets Management

Never store secrets in:

- Git
- Source code
- Prompts
- Client bundles
- Logs

Use environment variables and managed secrets.

Rotate secrets periodically.

---

# 13. File Upload Rules

Allow only approved formats.

Examples:

- PDF
- DOCX
- TXT
- CSV
- XLSX
- PNG
- JPG
- WEBP

Reject unknown types.

---

# 14. Logging

Never log:

- Passwords
- API keys
- Tokens
- Payment data
- Personal secrets

Always log:

- Errors
- Tool executions
- Security events
- Authentication events
- Audit events

---

# 15. Monitoring

Track:

- API latency
- AI latency
- Failed requests
- Failed retrievals
- Queue failures
- Provider failures
- Token usage
- Cost
- Human handoffs

---

# 16. Docker Rules

Containers must:

- Run as non-root
- Be minimal
- Pin dependency versions
- Expose only required ports
- Contain no secrets

---

# 17. Deployment Rules

GitHub, Railway, Vercel, and Supabase accounts are provisioned and are the
default infrastructure for version control, backend/worker hosting,
frontend hosting, and database respectively. Do not substitute other
providers unless explicitly instructed.

Railway:

- API
- Knowledge Worker

Vercel:

- Dashboard
- Web Widget

LiveKit Cloud:

- Voice Agent

Never deploy directly from unreviewed code.

---

# 18. Rate Limiting

Protect:

- Login
- AI endpoints
- Uploads
- Webhooks
- Search
- OTP endpoints

Apply exponential backoff where appropriate.

---

# 19. Backup & Recovery

- Daily database backups.
- Version uploaded knowledge.
- Test restore procedures.
- Never deploy without rollback capability.

---

# 20. Testing Rules

Every feature requires:

- Unit tests
- Integration tests
- Authorization tests
- Tenant isolation tests
- Regression tests

KIE additionally requires:

- OCR tests
- Retrieval quality tests
- Prompt injection tests

---

# 21. Coding Standards

Python

- Type hints
- Async-first
- Small modules
- Pydantic models

TypeScript

- Strict mode
- Zod validation
- Accessible UI

---

# 22. Release Checklist

Before production:

- Tests pass
- Security review completed
- Documentation updated
- Migrations reviewed
- Rollback verified
- Monitoring enabled

---

# 23. Incident Response

If a security issue occurs:

1. Contain
2. Investigate
3. Patch
4. Restore
5. Review
6. Document

---

# 24. Golden Rules

- Customer trust is more important than feature speed.
- Security is never optional.
- Chat and Calls always share Customer360 and KIE.
- Every feature must be reusable across channels.
- Documentation is updated before architectural changes.
- Simplicity beats unnecessary complexity.
- Build for long-term maintainability, not short-term convenience.
