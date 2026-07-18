"""Parses the four governance/control inputs into plain dataclasses.
Column positions and header rows below were confirmed by directly
inspecting the live files in RKPR_RAG_FINAL_DOCS/04_GOVERNANCE and
00_CONTROL — not guessed from the register's own "Lists" vocabulary tab,
which (see governance.mapping's docstring) doesn't fully agree with the
data.
"""

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl

_REGISTER_HEADER_ROW = 4
_REGISTER_DATA_START_ROW = 5
_CONFLICT_HEADER_ROW = 4
_CONFLICT_DATA_START_ROW = 5
_QUESTIONS_HEADER_ROW = 1
_QUESTIONS_DATA_START_ROW = 2


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _as_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _rows_as_dicts(path: Path, sheet_name: str, header_row: int, data_start_row: int) -> list[dict]:
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook[sheet_name]
    headers = [cell.value for cell in sheet[header_row]]
    results = []
    for row in sheet.iter_rows(min_row=data_start_row, values_only=True):
        if not row or not row[0]:
            continue
        results.append(dict(zip(headers, row, strict=True)))
    return results


@dataclass
class RegisterRow:
    source_id: str
    title: str
    file_path_or_url: str | None
    source_type: str | None
    category: str | None
    department: str | None
    content_owner: str | None
    version: str | None
    visibility_raw: str | None
    language: str | None
    effective_date: date | None
    expiry_date: date | None
    approval_status_raw: str | None
    processing_status_raw: str | None
    ocr_required_raw: str | None
    source_priority_raw: str | None
    authoritative_raw: str | None
    image_folder: str | None
    notes: str | None
    raw: dict = field(default_factory=dict)


def parse_source_register(path: Path) -> list[RegisterRow]:
    rows = _rows_as_dicts(path, "Source Register", _REGISTER_HEADER_ROW, _REGISTER_DATA_START_ROW)
    parsed = []
    for row in rows:
        parsed.append(
            RegisterRow(
                source_id=_as_str(row.get("Source ID")) or "",
                title=_as_str(row.get("Source Title")) or "",
                file_path_or_url=_as_str(row.get("File Name or URL")),
                source_type=_as_str(row.get("Source Type")),
                category=_as_str(row.get("Category")),
                department=_as_str(row.get("Department")),
                content_owner=_as_str(row.get("Content Owner")),
                version=_as_str(row.get("Version")),
                visibility_raw=_as_str(row.get("Visibility")),
                language=_as_str(row.get("Language")),
                effective_date=_as_date(row.get("Effective Date")),
                expiry_date=_as_date(row.get("Expiry Date")),
                approval_status_raw=_as_str(row.get("Approval Status")),
                processing_status_raw=_as_str(row.get("Processing Status")),
                ocr_required_raw=_as_str(row.get("OCR Required")),
                source_priority_raw=_as_str(row.get("Source Priority")),
                authoritative_raw=_as_str(row.get("Authoritative Source")),
                image_folder=_as_str(row.get("Image Folder")),
                notes=_as_str(row.get("Notes")),
                raw={k: (v.isoformat() if isinstance(v, date | datetime) else v) for k, v in row.items()},
            )
        )
    return parsed


@dataclass
class ConflictRow:
    conflict_id: str
    topic: str | None
    category: str | None
    source_1_label: str | None
    source_1_info: str | None
    source_2_label: str | None
    source_2_info: str | None
    conflict_type: str | None
    correct_information: str | None
    authoritative_source: str | None
    status_raw: str | None
    action_required: str | None
    related_source_ids: list[str]
    notes: str | None


def parse_conflict_register(path: Path) -> list[ConflictRow]:
    rows = _rows_as_dicts(path, "Conflict Register", _CONFLICT_HEADER_ROW, _CONFLICT_DATA_START_ROW)
    parsed = []
    for row in rows:
        related_raw = _as_str(row.get("Related Source IDs")) or ""
        related_ids = [part.strip() for part in related_raw.split(";") if part.strip()]
        parsed.append(
            ConflictRow(
                conflict_id=_as_str(row.get("Conflict ID")) or "",
                topic=_as_str(row.get("Topic")),
                category=_as_str(row.get("Category")),
                source_1_label=_as_str(row.get("Source 1")),
                source_1_info=_as_str(row.get("Information in Source 1")),
                source_2_label=_as_str(row.get("Source 2")),
                source_2_info=_as_str(row.get("Information in Source 2")),
                conflict_type=_as_str(row.get("Conflict Type")),
                correct_information=_as_str(row.get("Correct Information")),
                authoritative_source=_as_str(row.get("Authoritative Source")),
                status_raw=_as_str(row.get("Status")),
                action_required=_as_str(row.get("Action Required")),
                related_source_ids=related_ids,
                notes=_as_str(row.get("Notes")),
            )
        )
    return parsed


@dataclass
class BenchmarkQuestionRow:
    question: str
    expected_answer: str | None
    correct_source_label: str | None
    category: str | None
    audience_raw: str | None
    priority_raw: str | None


def parse_benchmark_questions(path: Path) -> list[BenchmarkQuestionRow]:
    rows = _rows_as_dicts(path, "Guest Questions", _QUESTIONS_HEADER_ROW, _QUESTIONS_DATA_START_ROW)
    parsed = []
    for row in rows:
        parsed.append(
            BenchmarkQuestionRow(
                question=_as_str(row.get("Question")) or "",
                expected_answer=_as_str(row.get("Expected Answer")),
                correct_source_label=_as_str(row.get("Correct Source")),
                category=_as_str(row.get("Category")),
                audience_raw=_as_str(row.get("Guest/Internal")),
                priority_raw=_as_str(row.get("Priority")),
            )
        )
    return parsed


@dataclass
class ManifestRow:
    relative_path: str
    extension: str | None
    size_bytes: int | None
    sha256: str | None
    ingest_status: str | None
    target_index: str | None
    notes: str | None


def parse_manifest(path: Path) -> list[ManifestRow]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if not row.get("relative_path"):
                continue
            size = row.get("size_bytes")
            rows.append(
                ManifestRow(
                    relative_path=row["relative_path"].strip(),
                    extension=_as_str(row.get("extension")),
                    size_bytes=int(size) if size and size.strip().isdigit() else None,
                    sha256=_as_str(row.get("sha256")),
                    ingest_status=_as_str(row.get("ingest_status")),
                    target_index=_as_str(row.get("target_index")),
                    notes=_as_str(row.get("notes")),
                )
            )
        return rows
