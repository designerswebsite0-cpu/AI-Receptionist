"""Pure data — no engine imports, mirrors app.roles.seed_data's pattern so
Alembic migrations and tests can both depend on this cheaply.

Two independent vocabularies live on a conversation, deliberately kept
distinct (see docs/product_decisions.md 2026-07-16 entry):

- STATUS: the lifecycle/handoff queue state a staff inbox filters by.
- DIALOGUE_STATE: where the AI reasoning pipeline is in the conversation
  (architecture.md §4.4 step 3) — independent of who's currently allowed
  to send (that's STATUS + the ai_active/human_active flags).
"""

CHANNELS = ("whatsapp", "webchat", "voice")

# 7 statuses from the Phase 2 brief, plus BLOCKED retained from the
# original architecture.md §4.1 conversation states for safety-critical
# halting of automated processing — not restated in the Phase 2 brief but
# not superseded by it either (rules.md requires it).
STATUSES = (
    "open",
    "waiting_for_guest",
    "waiting_for_staff",
    "ai_handling",
    "human_handling",
    "escalated",
    "closed",
    "blocked",
)

PRIORITIES = ("low", "normal", "high", "urgent")

# Canonical across docs/functions.md, architecture.md §4.4, and this engine
# — see product_decisions.md for the reconciliation of earlier, slightly
# different state lists.
DIALOGUE_STATES = (
    "greeting",
    "discovering_needs",
    "collecting_information",
    "recommending",
    "booking",
    "waiting",
    "confirmation",
    "upselling",
    "support",
    "escalation",
    "closed",
)

STATE_CHANGED_BY = ("ai", "human", "system")
