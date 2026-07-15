"""Pure data: no FastAPI/SQLAlchemy-engine imports here.

Kept import-light on purpose so both the Alembic seed migration and tests
can depend on it without pulling in the full application wiring.
"""


class Permission:
    TENANT_VIEW = "tenant.view"
    TENANT_MANAGE_SETTINGS = "tenant.manage_settings"
    MEMBERS_VIEW = "members.view"
    MEMBERS_INVITE = "members.invite"
    MEMBERS_REMOVE = "members.remove"
    MEMBERS_UPDATE_ROLE = "members.update_role"
    AUDIT_READ = "audit.read"
    # Phase 2 — Shared Conversation Foundation
    CUSTOMERS_VIEW = "customers.view"
    CUSTOMERS_MANAGE = "customers.manage"
    CONVERSATIONS_VIEW = "conversations.view"
    CONVERSATIONS_MANAGE = "conversations.manage"


ALL_PERMISSIONS = [
    Permission.TENANT_VIEW,
    Permission.TENANT_MANAGE_SETTINGS,
    Permission.MEMBERS_VIEW,
    Permission.MEMBERS_INVITE,
    Permission.MEMBERS_REMOVE,
    Permission.MEMBERS_UPDATE_ROLE,
    Permission.AUDIT_READ,
    Permission.CUSTOMERS_VIEW,
    Permission.CUSTOMERS_MANAGE,
    Permission.CONVERSATIONS_VIEW,
    Permission.CONVERSATIONS_MANAGE,
]

# Permissions introduced after the Phase 1 seed migration (0001). Tracked
# separately so the Phase 2 seed migration (0004) can grant exactly these to
# existing roles without re-inserting rows 0001 already created — see that
# migration's docstring.
PHASE_2_PERMISSIONS = [
    Permission.CUSTOMERS_VIEW,
    Permission.CUSTOMERS_MANAGE,
    Permission.CONVERSATIONS_VIEW,
    Permission.CONVERSATIONS_MANAGE,
]

# System role -> permission seed matrix (rules.md §4's 5 roles). This is the
# single source of truth consumed by the Alembic seed migrations (0001, 0004)
# and by tests; the FastAPI-facing require_permission() dependency in
# app.roles.permissions re-exports these names.
SYSTEM_ROLES: dict[str, list[str]] = {
    "owner": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS,
    "manager": [
        Permission.TENANT_VIEW,
        Permission.MEMBERS_VIEW,
        Permission.MEMBERS_INVITE,
        Permission.AUDIT_READ,
        Permission.CUSTOMERS_VIEW,
        Permission.CUSTOMERS_MANAGE,
        Permission.CONVERSATIONS_VIEW,
        Permission.CONVERSATIONS_MANAGE,
    ],
    "staff": [
        Permission.TENANT_VIEW,
        Permission.MEMBERS_VIEW,
        Permission.CUSTOMERS_VIEW,
        Permission.CUSTOMERS_MANAGE,
        Permission.CONVERSATIONS_VIEW,
        Permission.CONVERSATIONS_MANAGE,
    ],
    "read_only": [
        Permission.TENANT_VIEW,
        Permission.CUSTOMERS_VIEW,
        Permission.CONVERSATIONS_VIEW,
    ],
}
