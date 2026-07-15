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


ALL_PERMISSIONS = [
    Permission.TENANT_VIEW,
    Permission.TENANT_MANAGE_SETTINGS,
    Permission.MEMBERS_VIEW,
    Permission.MEMBERS_INVITE,
    Permission.MEMBERS_REMOVE,
    Permission.MEMBERS_UPDATE_ROLE,
    Permission.AUDIT_READ,
]

# System role -> permission seed matrix (rules.md §4's 5 roles). This is the
# single source of truth consumed by the Alembic seed migration (0001) and
# by tests; the FastAPI-facing require_permission() dependency in
# app.roles.permissions re-exports these names.
SYSTEM_ROLES: dict[str, list[str]] = {
    "owner": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS,
    "manager": [
        Permission.TENANT_VIEW,
        Permission.MEMBERS_VIEW,
        Permission.MEMBERS_INVITE,
        Permission.AUDIT_READ,
    ],
    "staff": [Permission.TENANT_VIEW, Permission.MEMBERS_VIEW],
    "read_only": [Permission.TENANT_VIEW],
}
