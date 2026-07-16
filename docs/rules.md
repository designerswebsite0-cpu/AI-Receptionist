# rules.md
# AI Receptionist Platform — Engineering & Security Rules (v2)

> Status: Living Engineering Constitution
> Applies To: Entire Platform (Chat + Calls + Customer360 + Knowledge Intelligence Engine)

---

# 1. Core Philosophy

This platform is built on:

- Security First
- Privacy First
- Single-Resort Per Deployment First (Phase 2.5 — reusable template, not shared multi-tenant SaaS)
- API First
- AI First
- Reliability First

Never sacrifice architecture or security for speed.

---

# 2. Zero Trust

Treat every request as untrusted.

Always verify:

- User identity (a verified Supabase session — see §4)
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
- Audit

**Single-resort access model (Phase 2.5 — see docs/product_decisions.md):**
there is no role/permission system. Any authenticated user has full access
to this deployment's one resort. The earlier `owner`/`admin`/`manager`/
`staff`/`read_only` role system, `tenant_members`/`tenant_roles`/
`tenant_permissions` tables, and `require_permission`/
`RBAC_ENFORCEMENT_ENABLED` flag were removed entirely, not switched off —
there is nothing left to flip back on. Do not build dashboard UI that
hides features based on role; there is no role to check.

If role distinctions are ever needed again, they must be reintroduced
deliberately (new tables, new checks) rather than assumed to still exist
in dormant form.

---

# 5. Single-Resort Deployment Rules

Mandatory:

- One deployment serves exactly one resort's data — never share one
  database or one Supabase project across resorts.
- A new resort means a new deployment (new Railway backend, new Vercel
  frontend, new Supabase project), not a new row in a shared table.
- Every table requires only authentication, not per-row ownership — RLS
  policies check `auth.uid() IS NOT NULL`, nothing more.
- The Supabase service-role key must never be exposed to any client.

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
- Authentication tests (unauthenticated requests must be rejected)
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
