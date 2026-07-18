"""Cheap keyword-based query classification — a category label used to
optionally bias retrieval toward matching chunk_types, plus a
`requested_channel`-agnostic label logged on every knowledge_retrieval_logs
row for analytics. Not an LLM call: classification only needs to be
directionally useful here, and a network round trip per query would add
latency to every single retrieval for a heuristic that a keyword match
already answers.
"""

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pricing": ("price", "rate", "cost", "how much", "charge", "fee", "inr", "$"),
    "room": ("room", "suite", "villa", "accommodation", "occupancy", "bed"),
    "dining": ("menu", "restaurant", "food", "dining", "breakfast", "dinner", "lunch", "cuisine"),
    "spa": ("spa", "massage", "wellness", "treatment", "yoga"),
    "policy": ("policy", "check-in", "check in", "check-out", "check out", "cancellation", "refund", "deposit"),
    "transport": ("airport", "transfer", "pickup", "taxi", "shuttle", "vehicle"),
    "events": ("wedding", "meeting", "event", "conference", "banquet"),
    "safety": ("emergency", "safety", "fire", "medical"),
}


def classify_query(text: str) -> str:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "general"
