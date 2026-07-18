"""Vocabulary normalization from the governance register's actual values
to this schema's CHECK-constrained enums.

Every mapping here was built from the *real* values found in
RKPR_RAG_FINAL_DOCS/04_GOVERNANCE/Knowledge_Source_Register.xlsx (24 rows)
and its sibling registers — not from the register's own "Lists" vocabulary
tab, because the two don't fully agree. Concretely: the Lists tab defines
Source Priority as {Critical, High, Normal, Low}, but real rows (SRC-018,
019, 020) use "Supplementary", which appears nowhere in Lists. Similarly
Processing Status real values include "N/A" and "Archived - Historical
Reference Only", neither of which is in the Lists tab's {Not Uploaded,
Queued, Processing, Ready, Failed, OCR Review}. `normalize()` below maps
every value actually observed; anything genuinely new shows up in the
importer's reconciliation report as an unmapped value rather than being
silently guessed.
"""

from dataclasses import dataclass


@dataclass
class NormalizedValue:
    value: str
    was_exact: bool  # False when the mapping required a fallback/best-guess
    original: str


def _lookup(raw: str | None, table: dict[str, str], *, fallback: str) -> NormalizedValue:
    if raw is None or not str(raw).strip():
        return NormalizedValue(value=fallback, was_exact=False, original=str(raw))
    key = str(raw).strip().lower()
    if key in table:
        return NormalizedValue(value=table[key], was_exact=True, original=str(raw))
    return NormalizedValue(value=fallback, was_exact=False, original=str(raw))


_APPROVAL_STATUS_MAP = {
    "draft": "pending",
    "pending": "pending",
    "approved": "approved",
    "rejected": "rejected",
    "approved (archived)": "approved",
    "n/a": "pending",
}

_PROCESSING_STATUS_MAP = {
    "not uploaded": "pending",
    "queued": "pending",
    "processing": "extracting",
    "ready": "completed",
    "failed": "failed",
    "ocr review": "needs_review",
    "n/a": "pending",
    "archived - historical reference only": "completed",
}

_VISIBILITY_MAP = {
    "guest-visible": "guest",
    "staff-only": "staff",
    "restricted": "internal",
}

_PRIORITY_MAP = {
    "critical": "critical",
    "high": "high",
    "normal": "normal",
    "low": "low",
    "supplementary": "low",
}

_CONFLICT_STATUS_MAP = {
    "resolved": "resolved",
    "under review": "open",
    "open": "open",
}

_BENCHMARK_PRIORITY_MAP = {
    "high": "high",
    "medium": "normal",
    "low": "low",
}

_BENCHMARK_AUDIENCE_MAP = {
    "guest": "guest",
    "internal": "internal",
}


def normalize_approval_status(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _APPROVAL_STATUS_MAP, fallback="pending")


def normalize_processing_status(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _PROCESSING_STATUS_MAP, fallback="pending")


def normalize_visibility(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _VISIBILITY_MAP, fallback="staff")


def normalize_priority(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _PRIORITY_MAP, fallback="normal")


def normalize_conflict_status(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _CONFLICT_STATUS_MAP, fallback="open")


def normalize_benchmark_priority(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _BENCHMARK_PRIORITY_MAP, fallback="normal")


def normalize_benchmark_audience(raw: str | None) -> NormalizedValue:
    return _lookup(raw, _BENCHMARK_AUDIENCE_MAP, fallback="guest")


def is_archival_signal(*raw_values: str | None) -> bool:
    """True when any of the given raw register strings signals the source
    is historical/archived (e.g. "Approved (Archived)",
    "Archived - Historical Reference Only") — these don't fit neatly into
    approval_status/processing_status alone and instead drive
    knowledge_sources.status directly (see governance.importer)."""
    return any(value and "archiv" in value.lower() for value in raw_values)
