# Database Changes (Phase X)

Three new migrations, `0025` → `0027`, taking the schema from head `0024`
(Phase 5's `webchat_sessions`) to head `0027`. All three follow the
established single-resort RLS pattern (`auth.uid() IS NOT NULL` policies,
defense-in-depth only — the backend's `service_role` connection is the real
authorization gate).

## `0025_users_staff_fields.py` — Staff Management

Adds three columns to the existing `users` table:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `role` | `varchar(50)` | `'Administrator'` | Display-only label, never RBAC-enforcing |
| `status` | `varchar(20)` | `'active'` | `active`/`inactive` roster visibility — does not block login |
| `last_login_at` | `timestamptz` | `NULL` | Set by `/auth/login` on every successful sign-in |

A `CHECK` constraint (`ck_users_status`) enforces `status IN ('active', 'inactive')`.
No RLS change needed — `users` already had RLS from migration 0009.

## `0026_notifications.py` — Notifications

New table `notifications`:

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | PK |
| `notification_type` | `varchar(50)` | `CHECK` constrained to the 4 known types |
| `title` | `varchar(300)` | |
| `body` | `varchar(2000)` | nullable |
| `resource_type` / `resource_id` | `varchar(50)` / `varchar(64)` | nullable, mirrors `audit_logs`' convention |
| `read_at` / `read_by_user_id` | `timestamptz` / `uuid` FK → `users` | both nullable; no per-recipient row — a resort-wide shared feed |
| `created_at` | `timestamptz` | indexed |

Indexes on `notification_type` and `created_at`. RLS: standard
select/modify-if-authenticated policy pair.

## `0027_customer_feedback.py` — Customer Feedback

New table `customer_feedback`:

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | PK |
| `category` | `varchar(30)` | `CHECK IN ('website_chat', 'general')` |
| `rating` | `varchar(10)` | `CHECK IN ('up', 'down')` — mirrors webchat's real vocabulary |
| `comment` | `varchar(2000)` | nullable |
| `conversation_id` | `uuid` FK → `conversations`, `ON DELETE SET NULL` | nullable |
| `customer_id` | `uuid` FK → `customers`, `ON DELETE SET NULL` | nullable |
| `turn_id` | `uuid` FK → `orchestration_turns`, `ON DELETE SET NULL` | nullable |
| `status` | `varchar(20)` | `CHECK IN ('new', 'reviewed', 'actioned', 'dismissed')`, default `'new'` |
| `assigned_agent_id` | `uuid` FK → `users`, `ON DELETE SET NULL` | nullable |
| `created_at` | `timestamptz` | indexed |

Indexes on `category`, `rating`, `conversation_id`, `customer_id`, `status`,
`created_at`. RLS: standard select/modify-if-authenticated policy pair.

## Not migrated

- **General Settings** (Stage 8): no migration — the new AI-behavior fields
  (business hours, supported languages, chat availability, hand-off hours,
  fallback message, AI display name, emergency contact) all live inside the
  pre-existing `resort_settings.settings_metadata` JSONB column.
- **Audit Logs read endpoint** (Stage 8): no migration — reads the
  pre-existing `audit_logs` table.
- **Analytics** (Stage 9): no migration — pure aggregation over existing
  tables.
- **Booking Management** (Stage 5): no migration — reuses the pre-existing
  `service_requests` table (migration 0022) and its `details` JSONB.

## Applying

```
cd apps/api
python -m uv run alembic upgrade head
```

All three migrations were applied against the real Supabase project during
this phase and verified with a direct
`information_schema.columns`/`\d` check after each one.
