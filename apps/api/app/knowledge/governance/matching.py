"""Multi-strategy matching of register rows to actual on-disk files.

Grounded in what was actually found inspecting the live corpus, not
theoretical strategies: the Knowledge_Source_Register's "File Name or
URL" column uses the pre-reorganization folder layout (e.g.
"02_Rooms_and_Accommodation/RKPR_Resort_Room_Catalogue.pdf") while the
actual package layout is different (e.g.
"01_GUEST_KNOWLEDGE/Rooms/RKPR_Resort_Room_Catalogue.pdf") — but basenames
are preserved across the reorg. The manifest itself never references
Source IDs at all (confirmed: zero "SRC-" matches in
PHASE3_INGESTION_MANIFEST.csv), so "Source ID embedded in filename" isn't
a viable strategy for documents in this corpus; normalized-basename
matching against the manifest is the primary, reliable strategy, with a
fuzzy fallback for the few filenames that were also renamed.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.knowledge.governance.parsers import ManifestRow, RegisterRow

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_FUZZY_THRESHOLD = 0.82


def _normalize_basename(path: str) -> str:
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return _NORMALIZE_RE.sub("", stem.lower())


@dataclass
class MatchResult:
    register_row: RegisterRow
    manifest_row: ManifestRow | None
    strategy: str  # "exact_basename" | "exact_basename_ambiguous" | "fuzzy_basename" | "unresolved"
    similarity: float | None = None


def match_register_to_manifest(
    register_rows: list[RegisterRow], manifest_rows: list[ManifestRow]
) -> list[MatchResult]:
    by_normalized_basename: dict[str, list[ManifestRow]] = {}
    for row in manifest_rows:
        key = _normalize_basename(row.relative_path)
        by_normalized_basename.setdefault(key, []).append(row)

    results = []
    for reg_row in register_rows:
        if not reg_row.file_path_or_url:
            results.append(MatchResult(reg_row, None, "unresolved"))
            continue

        key = _normalize_basename(reg_row.file_path_or_url)
        candidates = by_normalized_basename.get(key)

        if candidates and len(candidates) == 1:
            results.append(MatchResult(reg_row, candidates[0], "exact_basename"))
            continue

        if candidates and len(candidates) > 1:
            # Ambiguous exact basename match (rare — e.g. the same filename
            # appears in both an active and an archived folder). Break the
            # tie using title similarity against the full relative path
            # rather than guessing the first one silently.
            best = max(
                candidates,
                key=lambda m: SequenceMatcher(None, reg_row.title.lower(), m.relative_path.lower()).ratio(),
            )
            results.append(MatchResult(reg_row, best, "exact_basename_ambiguous"))
            continue

        best_row: ManifestRow | None = None
        best_score = 0.0
        for m_row in manifest_rows:
            score = SequenceMatcher(None, key, _normalize_basename(m_row.relative_path)).ratio()
            if score > best_score:
                best_score, best_row = score, m_row

        if best_row is not None and best_score >= _FUZZY_THRESHOLD:
            results.append(MatchResult(reg_row, best_row, "fuzzy_basename", similarity=best_score))
        else:
            results.append(MatchResult(reg_row, None, "unresolved", similarity=best_score if best_row else None))

    return results
