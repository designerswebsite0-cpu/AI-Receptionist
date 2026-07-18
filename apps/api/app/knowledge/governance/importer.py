"""Governance import orchestration: builds an honest reconciliation report
from the RKPR corpus's manifest + register (dry run), and — only when
explicitly executed — writes the corresponding knowledge_sources /
knowledge_media / knowledge_conflicts / knowledge_benchmark_questions rows.

Design note (see IMPLEMENTATION_PLAN.md's governance findings): the
ingestion MANIFEST (00_CONTROL/PHASE3_INGESTION_MANIFEST.csv), not the
register, is the primary ingestion driver here. It has an explicit,
unambiguous row for every single file in the package — including files the
register never mentions at all (media images, control docs, templates) —
via its own `ingest_status`/`target_index` columns. The register is a
secondary enrichment source: when a manifest row can be matched to a
register row (by normalized basename — see governance.matching), its
title/category/dates/approval workflow state enrich the plan; when it
can't, the manifest's own classification still produces a safe, correctly
categorized result on its own.
"""

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository, service, storage, validation
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.extraction.image import extract_image_metadata
from app.knowledge.extraction.registry import extract
from app.knowledge.governance import mapping
from app.knowledge.governance.matching import MatchResult, match_register_to_manifest
from app.knowledge.governance.parsers import (
    BenchmarkQuestionRow,
    ConflictRow,
    ManifestRow,
    RegisterRow,
    parse_benchmark_questions,
    parse_conflict_register,
    parse_manifest,
    parse_source_register,
)
from app.knowledge.indexing import index_source_version
from app.knowledge.models import KnowledgeBenchmarkQuestion, KnowledgeConflict, KnowledgeMedia
from app.knowledge.ocr.tesseract import TesseractOCRProvider
from app.knowledge.schemas import SourceRegisterRequest

_IMAGE_FORMATS = {"png", "jpg"}

# target_index values that are operational/config metadata, not guest- or
# staff-answer content — never become knowledge_sources or knowledge_media
# rows (manifest notes literally say "Operational metadata, not guest
# answer content" / "Incomplete template" / "Historical/version-only").
_SKIP_TARGET_INDEXES = {"control", "governance", "website_source_config", "template", "archive"}

_CONTROL_DIR = "00_CONTROL"
_GOVERNANCE_DIR = "04_GOVERNANCE"


@dataclass
class SourcePlan:
    manifest_row: ManifestRow
    register_row: RegisterRow | None
    match_strategy: str
    action: str  # "create_source" | "create_media" | "skip"
    visibility: str
    source_priority: str
    approval_status: str
    processing_status: str
    ocr_required: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReconciliationReport:
    plans: list[SourcePlan]
    unmatched_register_rows: list[RegisterRow]
    generated_at: str

    @property
    def summary(self) -> dict:
        counts = Counter(plan.action for plan in self.plans)
        return {
            "total_manifest_rows": len(self.plans),
            "create_source": counts.get("create_source", 0),
            "create_media": counts.get("create_media", 0),
            "skip": counts.get("skip", 0),
            "unmatched_register_rows": len(self.unmatched_register_rows),
            "plans_with_warnings": sum(1 for plan in self.plans if plan.warnings),
        }


def _plan_for_manifest_row(m_row: ManifestRow, match: MatchResult | None) -> SourcePlan:
    reg_row = match.register_row if match else None
    strategy = match.strategy if match else "no_register_entry"
    warnings: list[str] = []
    target = (m_row.target_index or "").strip().lower()

    if target in _SKIP_TARGET_INDEXES:
        return SourcePlan(
            m_row, reg_row, strategy, "skip", "template", "normal", "pending", "pending", warnings=warnings
        )

    if target == "media_metadata":
        return SourcePlan(
            m_row, reg_row, strategy, "create_media", "guest", "normal", "pending", "pending", warnings=warnings
        )

    if target == "ocr_test":
        warnings.append("OCR test fixture (03_OCR_TESTS) — must never reach retrieval_enabled=true")
        return SourcePlan(
            m_row, reg_row, strategy, "create_source", "staff", "low", "pending", "pending",
            ocr_required=True, warnings=warnings,
        )

    if target not in ("guest", "staff"):
        warnings.append(f"Unrecognized target_index '{m_row.target_index}' — excluded pending manual review")
        return SourcePlan(
            m_row, reg_row, strategy, "skip", "template", "normal", "pending", "pending", warnings=warnings
        )

    visibility = "guest" if target == "guest" else "staff"
    priority = "normal"
    approval = "pending"
    processing = "pending"
    ocr_required = False
    action = "create_source"

    if reg_row:
        vis_norm = mapping.normalize_visibility(reg_row.visibility_raw)
        if not vis_norm.was_exact:
            warnings.append(f"Register visibility '{reg_row.visibility_raw}' not in known vocabulary — defaulted")
        visibility = vis_norm.value

        pr_norm = mapping.normalize_priority(reg_row.source_priority_raw)
        if not pr_norm.was_exact:
            warnings.append(f"Register source priority '{reg_row.source_priority_raw}' not in known vocabulary")
        priority = pr_norm.value

        approval = mapping.normalize_approval_status(reg_row.approval_status_raw).value
        processing = mapping.normalize_processing_status(reg_row.processing_status_raw).value
        ocr_required = (reg_row.ocr_required_raw or "").strip().lower() == "yes"

        if mapping.is_archival_signal(reg_row.approval_status_raw, reg_row.processing_status_raw):
            action = "skip"
            warnings.append(
                f"Register marks this source archived/historical "
                f"(approval='{reg_row.approval_status_raw}', processing='{reg_row.processing_status_raw}') "
                "— excluded from active ingestion"
            )
    else:
        warnings.append("No matching register entry — proceeding with manifest-only defaults, needs review")

    if m_row.ingest_status == "NO":
        action = "skip"
        warnings.append(f"Manifest ingest_status is 'NO' for a {target}-targeted file — excluded")

    return SourcePlan(
        m_row, reg_row, strategy, action, visibility, priority, approval, processing,
        ocr_required=ocr_required, warnings=warnings,
    )


def build_reconciliation_report(rkpr_root: Path) -> ReconciliationReport:
    manifest_rows = parse_manifest(rkpr_root / _CONTROL_DIR / "PHASE3_INGESTION_MANIFEST.csv")
    register_rows = parse_source_register(rkpr_root / _GOVERNANCE_DIR / "Knowledge_Source_Register.xlsx")
    matches = match_register_to_manifest(register_rows, manifest_rows)
    matched_by_manifest_path = {
        m.manifest_row.relative_path: m for m in matches if m.manifest_row is not None
    }

    plans = [
        _plan_for_manifest_row(m_row, matched_by_manifest_path.get(m_row.relative_path)) for m_row in manifest_rows
    ]

    matched_register_ids = {m.register_row.source_id for m in matches if m.manifest_row is not None}
    unmatched = [row for row in register_rows if row.source_id not in matched_register_ids]

    return ReconciliationReport(
        plans=plans, unmatched_register_rows=unmatched, generated_at=datetime.now(UTC).isoformat()
    )


@dataclass
class ImportOutcome:
    relative_path: str
    action: str
    result: str  # "created" | "skipped_unchanged" | "excluded" | "error"
    detail: str | None = None


async def import_sources_from_report(
    db: AsyncSession,
    *,
    report: ReconciliationReport,
    rkpr_root: Path,
    actor_user_id,
    embedding_provider: EmbeddingProvider,
) -> list[ImportOutcome]:
    """Idempotent: re-running against an unchanged corpus creates nothing
    new, because each plan's checksum is checked against existing sources
    before any DB write (matches the CLI script's --dry-run/--execute
    contract in the Phase 3 brief). Pass a MockEmbeddingProvider in tests
    and dry runs; a real OpenAIEmbeddingProvider only for an --execute run
    the caller has explicitly authorized (embedding calls cost money)."""
    outcomes = []
    for plan in report.plans:
        if plan.action == "skip":
            outcomes.append(
                ImportOutcome(plan.manifest_row.relative_path, "skip", "excluded", "; ".join(plan.warnings))
            )
            continue

        file_path = rkpr_root / plan.manifest_row.relative_path
        try:
            content = file_path.read_bytes()
        except OSError as exc:
            outcomes.append(ImportOutcome(plan.manifest_row.relative_path, plan.action, "error", str(exc)))
            continue

        checksum = hashlib.sha256(content).hexdigest()

        if plan.action == "create_media":
            outcomes.append(await _import_media(db, plan, content, checksum, actor_user_id))
            continue

        outcomes.append(await _import_source(db, plan, content, checksum, actor_user_id, embedding_provider))

    return outcomes


async def _import_source(
    db: AsyncSession,
    plan: SourcePlan,
    content: bytes,
    checksum: str,
    actor_user_id,
    embedding_provider: EmbeddingProvider,
) -> ImportOutcome:
    rel_path = plan.manifest_row.relative_path
    existing = await repository.get_source_by_checksum(db, checksum)
    if existing is not None:
        return ImportOutcome(rel_path, plan.action, "skipped_unchanged", f"matches existing source {existing.id}")

    try:
        validation_result = validation.validate_upload(Path(rel_path).name, content)
    except Exception as exc:  # noqa: BLE001 — reconciliation must record, not crash the whole run
        return ImportOutcome(rel_path, plan.action, "error", f"validation failed: {exc}")

    title = plan.register_row.title if plan.register_row else Path(rel_path).stem.replace("_", " ")
    source_id = plan.register_row.source_id if plan.register_row else None
    authoritative = (
        (plan.register_row.authoritative_raw or "").strip().lower() == "yes" if plan.register_row else False
    )
    ocr_required = plan.ocr_required or validation_result.file_format in _IMAGE_FORMATS

    body = SourceRegisterRequest(
        source_id=source_id or None,
        title=title,
        source_type="document",
        category=plan.register_row.category if plan.register_row else None,
        visibility=plan.visibility,
        source_priority=plan.source_priority,
        authoritative=authoritative,
        ocr_required=ocr_required,
        effective_date=plan.register_row.effective_date if plan.register_row else None,
        expiry_date=plan.register_row.expiry_date if plan.register_row else None,
        source_metadata={"manifest_relative_path": rel_path, "match_strategy": plan.match_strategy},
    )

    try:
        source = await service.register_source(db, body=body, actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001
        return ImportOutcome(rel_path, plan.action, "error", f"register_source failed: {exc}")

    storage_path = f"sources/{source.id}/{validation_result.sanitized_filename}"
    await storage.upload_file(storage_path, content)

    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256=checksum, storage_path=storage_path, actor_user_id=actor_user_id
    )

    if validation_result.file_format in _IMAGE_FORMATS:
        ocr_provider = TesseractOCRProvider()
        ocr_result = await ocr_provider.recognize(content)
        if not ocr_result.available:
            # Fail honestly rather than silently mark this source
            # "completed" with no text — see app.knowledge.ocr's module
            # docstring and IMPLEMENTATION_PLAN.md §6.
            version.processing_status = "failed"
            version.error_message = "OCR provider unavailable (tesseract binary not found on this host)"
            source.processing_status = "failed"
            await db.commit()
            return ImportOutcome(rel_path, plan.action, "error", version.error_message)

        try:
            extracted = ExtractedContent(
                raw_text=ocr_result.text,
                extraction_method=f"ocr:{ocr_result.engine}",
                word_count=len(ocr_result.text.split()),
            )
            await index_source_version(
                db, source=source, version=version, extracted=extracted, provider=embedding_provider,
                chunk_type_hint=source.category,
            )
            version.ocr_used = True
            version.ocr_confidence = ocr_result.confidence
            version.processing_status = "completed"
            source.processing_status = "completed"
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            return ImportOutcome(rel_path, plan.action, "error", f"OCR indexing failed: {exc}")

        return ImportOutcome(
            rel_path, plan.action, "created", f"source_id={source.id} version={version.version_number} (OCR)"
        )

    try:
        extracted = extract(validation_result.file_format, content)
        result = await index_source_version(
            db, source=source, version=version, extracted=extracted, provider=embedding_provider,
            chunk_type_hint=source.category,
        )
        version.processing_status = "completed" if not extracted.pages_needing_ocr else "needs_review"
        source.processing_status = version.processing_status
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        return ImportOutcome(rel_path, plan.action, "error", f"extraction/indexing failed: {exc}")

    return ImportOutcome(
        rel_path, plan.action, "created",
        f"source_id={source.id} version={version.version_number} "
        f"chunks_created={result.chunks_created} chunks_embedded={result.chunks_embedded}",
    )


async def _import_media(
    db: AsyncSession, plan: SourcePlan, content: bytes, checksum: str, actor_user_id
) -> ImportOutcome:
    rel_path = plan.manifest_row.relative_path
    existing = await repository.get_source_by_checksum(db, checksum)
    if existing is not None:
        return ImportOutcome(rel_path, plan.action, "skipped_unchanged", "already imported")

    try:
        validation_result = validation.validate_upload(Path(rel_path).name, content)
        extracted = extract_image_metadata(content)
    except Exception as exc:  # noqa: BLE001
        return ImportOutcome(rel_path, plan.action, "error", f"validation/extraction failed: {exc}")

    storage_path = f"media/{checksum}/{validation_result.sanitized_filename}"
    await storage.upload_file(storage_path, content)

    media = KnowledgeMedia(
        storage_path=storage_path,
        original_filename=Path(rel_path).name,
        checksum_sha256=checksum,
        mime_type=f"image/{validation_result.file_format}",
        width_px=extracted.metadata.get("width"),
        height_px=extracted.metadata.get("height"),
        file_size_bytes=validation_result.size_bytes,
        visibility="guest",
        retrieval_enabled=False,
        media_metadata={"manifest_relative_path": rel_path},
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return ImportOutcome(rel_path, plan.action, "created", f"media_id={media.id}")


async def import_conflicts(
    db: AsyncSession, *, conflict_rows: list[ConflictRow], actor_user_id
) -> list[ImportOutcome]:
    outcomes = []
    for row in conflict_rows:
        existing = await repository.get_conflict_by_key(db, row.conflict_id)
        if existing is not None:
            outcomes.append(ImportOutcome(row.conflict_id, "conflict", "skipped_unchanged", "already imported"))
            continue

        description_parts = [row.topic or "", f"Source 1 ({row.source_1_label}): {row.source_1_info}"]
        if row.source_2_label:
            description_parts.append(f"Source 2 ({row.source_2_label}): {row.source_2_info}")
        description = " | ".join(part for part in description_parts if part)

        resolution_notes_parts = [row.correct_information, row.action_required, row.notes]
        resolution_notes = " | ".join(part for part in resolution_notes_parts if part) or None

        source_ids = row.related_source_ids
        source_a = await repository.get_source_by_external_id(db, source_ids[0]) if len(source_ids) > 0 else None
        source_b = await repository.get_source_by_external_id(db, source_ids[1]) if len(source_ids) > 1 else None

        conflict = KnowledgeConflict(
            conflict_key=row.conflict_id,
            description=description or row.conflict_id,
            source_a_id=source_a.id if source_a else None,
            source_b_id=source_b.id if source_b else None,
            resolution_status=mapping.normalize_conflict_status(row.status_raw).value,
            resolution_notes=resolution_notes,
        )
        db.add(conflict)
        await db.commit()
        await db.refresh(conflict)
        outcomes.append(ImportOutcome(row.conflict_id, "conflict", "created", f"conflict_id={conflict.id}"))
    return outcomes


async def import_benchmark_questions(
    db: AsyncSession, *, question_rows: list[BenchmarkQuestionRow], actor_user_id
) -> list[ImportOutcome]:
    outcomes = []
    for row in question_rows:
        existing = await repository.get_benchmark_question_by_text(db, row.question)
        if existing is not None:
            outcomes.append(ImportOutcome(row.question[:60], "benchmark", "skipped_unchanged", "already imported"))
            continue

        question = KnowledgeBenchmarkQuestion(
            question=row.question,
            expected_answer=row.expected_answer,
            category=row.category,
            audience=mapping.normalize_benchmark_audience(row.audience_raw).value,
            priority=mapping.normalize_benchmark_priority(row.priority_raw).value,
        )
        db.add(question)
        await db.commit()
        await db.refresh(question)
        outcomes.append(ImportOutcome(row.question[:60], "benchmark", "created", f"question_id={question.id}"))
    return outcomes


def load_conflict_rows(rkpr_root: Path) -> list[ConflictRow]:
    return parse_conflict_register(rkpr_root / _GOVERNANCE_DIR / "Conflicting_Information_Register.xlsx")


def load_benchmark_question_rows(rkpr_root: Path) -> list[BenchmarkQuestionRow]:
    return parse_benchmark_questions(rkpr_root / _GOVERNANCE_DIR / "Common_Guest_Questions_Dataset.xlsx")
