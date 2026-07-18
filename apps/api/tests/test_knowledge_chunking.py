"""Pure-logic tests for app.knowledge.chunking — no database required."""

import pytest

from app.knowledge.chunking.base import Chunk
from app.knowledge.chunking.strategies import (
    chunk_faq_text,
    chunk_generic_text,
    chunk_source,
    chunk_table,
    count_tokens,
)


def test_chunk_key_is_deterministic_for_identical_content():
    text = "Check-in is 2 PM."
    chunk_a = Chunk(chunk_type="policy", chunk_index=0, content_raw=text, content_normalized=text)
    chunk_b = Chunk(chunk_type="policy", chunk_index=0, content_raw=text, content_normalized=text)
    assert chunk_a.chunk_key == chunk_b.chunk_key


def test_chunk_key_changes_when_content_changes():
    chunk_a = Chunk(chunk_type="policy", chunk_index=0, content_raw="x", content_normalized="Check-in is 2 PM.")
    chunk_b = Chunk(chunk_type="policy", chunk_index=0, content_raw="x", content_normalized="Check-in is 3 PM.")
    assert chunk_a.chunk_key != chunk_b.chunk_key


def test_chunk_faq_text_extracts_every_pair():
    text = (
        "Q: What time is check-in? A: Check-in begins at 2:00 PM.\n\n"
        "Q: What time is check-out? A: Check-out is by 11:00 AM.\n\n"
        "Q: Is Wi-Fi complimentary? A: Yes, in all rooms and public areas."
    )
    chunks = chunk_faq_text(text)
    assert len(chunks) == 3
    assert chunks[0].entity_metadata["question"] == "What time is check-in?"
    assert chunks[0].entity_metadata["answer"] == "Check-in begins at 2:00 PM."
    assert all(c.chunk_type == "faq" for c in chunks)


def test_chunk_source_mixed_document_preserves_non_faq_content():
    # Regression test for a real bug found against
    # RKPR_Resort_Restaurant_Menu_Full_2026.pdf: a document with an FAQ
    # appendix must not have its other content silently discarded.
    text = (
        "SECTION 1: STARTERS\n\nGarlic Bread — INR 350\nSoup of the Day — INR 400\n\n"
        "SECTION 2: FAQ\n\n"
        "Q: Do you serve Jain food? A: Yes, with advance notice.\n\n"
        "Q: Is alcohol available? A: Yes, at the bar.\n\n"
        "Q: What are opening hours? A: 7 AM to 11 PM daily."
    )
    chunks = chunk_source(normalized_text=text, chunk_type_hint="menu_item")

    faq_chunks = [c for c in chunks if c.chunk_type == "faq"]
    other_chunks = [c for c in chunks if c.chunk_type != "faq"]

    assert len(faq_chunks) == 3
    assert len(other_chunks) >= 1
    assert any("Garlic Bread" in c.content_normalized for c in other_chunks)
    assert any("Soup of the Day" in c.content_normalized for c in other_chunks)


def test_chunk_source_pure_faq_file_is_almost_entirely_faq_chunks():
    text = "\n\n".join(f"Q: Question number {i}? A: Answer number {i}." for i in range(10))
    chunks = chunk_source(normalized_text=text)
    assert all(c.chunk_type == "faq" for c in chunks)
    assert len(chunks) == 10


def test_chunk_source_below_faq_threshold_uses_generic_chunker():
    # Only two Q/A-shaped lines — below the 3-pair detection threshold,
    # so this should NOT be routed through FAQ chunking at all.
    text = "Q: One question? A: One answer.\n\nSome unrelated policy text here."
    chunks = chunk_source(normalized_text=text)
    assert all(c.chunk_type == "generic" for c in chunks)


def test_chunk_generic_text_respects_token_budget():
    paragraph = "This is a sentence about resort policy. " * 40  # ~280 tokens
    text = "\n\n".join([paragraph] * 5)
    chunks = chunk_generic_text(text, max_tokens=300, overlap_tokens=30)
    assert len(chunks) > 1
    for chunk in chunks:
        # Allow some slack: a single oversized paragraph can exceed the
        # budget on its own (see chunk_generic_text's docstring).
        assert chunk.token_count <= 300 or len(chunk.content_normalized.split("\n\n")) == 1


def test_chunk_generic_text_empty_input_returns_no_chunks():
    assert chunk_generic_text("   \n\n   ") == []


def test_chunk_table_produces_one_chunk_per_data_row():
    tables = [
        {
            "sheet_name": "Rates",
            "rows": [
                ["Room Type", "Rate (INR)", "Occupancy"],
                ["Deluxe Suite", "25000", "2"],
                ["Garden Villa", "40000", "4"],
                ["", "", ""],  # blank row must be skipped
            ],
        }
    ]
    chunks = chunk_table(tables, chunk_type="room_rate")
    assert len(chunks) == 2
    assert "Room Type: Deluxe Suite" in chunks[0].content_normalized
    assert chunks[0].entity_metadata["Rate (INR)"] == "25000"
    assert chunks[0].section_title == "Rates"


def test_chunk_table_skips_sheets_with_only_a_header_row():
    tables = [{"sheet_name": "Empty", "rows": [["A", "B"]]}]
    assert chunk_table(tables) == []


@pytest.mark.parametrize("text,expected_min", [("hello world", 1), ("", 0)])
def test_count_tokens_is_non_negative(text, expected_min):
    assert count_tokens(text) >= expected_min
