"""Pure-logic tests for the governance vocabulary mapping and file-matching
strategies — no database or filesystem corpus required, so these run
everywhere. build_reconciliation_report itself was verified by hand
against the real RKPR_RAG_FINAL_DOCS corpus (19 create_source, 50
create_media, 21 skip, 3 legitimately-unmatched register rows) rather than
duplicated here as a golden-file test, since the corpus isn't guaranteed
to exist in every environment running this test suite.
"""

from app.knowledge.governance import mapping
from app.knowledge.governance.matching import match_register_to_manifest
from app.knowledge.governance.parsers import ManifestRow, RegisterRow


def _register_row(**overrides) -> RegisterRow:
    defaults = dict(
        source_id="SRC-999",
        title="Test Source",
        file_path_or_url="02_Rooms_and_Accommodation/RKPR_Resort_Room_Catalogue.pdf",
        source_type="PDF",
        category=None,
        department=None,
        content_owner=None,
        version=None,
        visibility_raw="Guest-visible",
        language=None,
        effective_date=None,
        expiry_date=None,
        approval_status_raw="Approved",
        processing_status_raw="Ready",
        ocr_required_raw="No",
        source_priority_raw="Critical",
        authoritative_raw="Yes",
        image_folder=None,
        notes=None,
    )
    defaults.update(overrides)
    return RegisterRow(**defaults)


def _manifest_row(**overrides) -> ManifestRow:
    defaults = dict(
        relative_path="01_GUEST_KNOWLEDGE/Rooms/RKPR_Resort_Room_Catalogue.pdf",
        extension=".pdf",
        size_bytes=1000,
        sha256="a" * 64,
        ingest_status="YES",
        target_index="guest",
        notes=None,
    )
    defaults.update(overrides)
    return ManifestRow(**defaults)


# --- mapping ------------------------------------------------------------


def test_normalize_visibility_maps_real_register_values():
    assert mapping.normalize_visibility("Guest-visible").value == "guest"
    assert mapping.normalize_visibility("Staff-only").value == "staff"
    assert mapping.normalize_visibility("Restricted").value == "internal"


def test_normalize_priority_maps_supplementary_which_is_outside_the_lists_vocab():
    result = mapping.normalize_priority("Supplementary")
    assert result.value == "low"
    assert result.was_exact is True  # explicitly mapped, not a fallback guess


def test_normalize_priority_unknown_value_falls_back_and_is_flagged():
    result = mapping.normalize_priority("Ultra Mega Critical")
    assert result.value == "normal"
    assert result.was_exact is False


def test_normalize_approval_status_handles_archived_variant():
    assert mapping.normalize_approval_status("Approved (Archived)").value == "approved"
    assert mapping.normalize_approval_status("Draft").value == "pending"
    assert mapping.normalize_approval_status("N/A").value == "pending"


def test_normalize_processing_status_handles_non_vocab_real_values():
    assert mapping.normalize_processing_status("Archived - Historical Reference Only").value == "completed"
    assert mapping.normalize_processing_status("Ready").value == "completed"
    assert mapping.normalize_processing_status(None).value == "pending"


def test_is_archival_signal_detects_archived_substring():
    assert mapping.is_archival_signal("Approved (Archived)", "Ready") is True
    assert mapping.is_archival_signal("Approved", "Ready") is False
    assert mapping.is_archival_signal(None, None) is False


# --- matching -------------------------------------------------------------


def test_exact_basename_match_survives_folder_reorganization():
    register_rows = [_register_row()]
    manifest_rows = [_manifest_row()]

    results = match_register_to_manifest(register_rows, manifest_rows)

    assert len(results) == 1
    assert results[0].strategy == "exact_basename"
    assert results[0].manifest_row is manifest_rows[0]


def test_unresolved_when_no_manifest_file_matches():
    register_rows = [_register_row(file_path_or_url="somewhere/completely_different_file.pdf")]
    manifest_rows = [_manifest_row()]

    results = match_register_to_manifest(register_rows, manifest_rows)

    assert results[0].strategy == "unresolved"
    assert results[0].manifest_row is None


def test_register_row_without_file_path_is_unresolved():
    register_rows = [_register_row(file_path_or_url=None)]
    manifest_rows = [_manifest_row()]

    results = match_register_to_manifest(register_rows, manifest_rows)

    assert results[0].strategy == "unresolved"


def test_fuzzy_match_catches_minor_filename_rename():
    register_rows = [_register_row(file_path_or_url="old_folder/RKPR_Resort_Room_Catalog.pdf")]
    manifest_rows = [_manifest_row()]

    results = match_register_to_manifest(register_rows, manifest_rows)

    assert results[0].strategy == "fuzzy_basename"
    assert results[0].similarity > 0.82
