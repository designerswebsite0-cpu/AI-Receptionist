"""Pure-logic tests for app.knowledge.validation and .normalization — no
database required, so these run everywhere (including this dev machine),
unlike the service-layer tests in test_knowledge_sources.py.
"""

import zipfile
from io import BytesIO

import pytest

from app.errors import ValidationErrorApp
from app.knowledge.normalization import normalize_text, strip_repeated_lines
from app.knowledge.validation import sanitize_filename, sniff_format, validate_upload


def test_sniff_pdf():
    assert sniff_format(b"%PDF-1.7\n...") == "pdf"


def test_sniff_png():
    assert sniff_format(b"\x89PNG\r\n\x1a\n\x00\x00") == "png"


def test_sniff_html():
    assert sniff_format(b"<!DOCTYPE html><html><body>hi</body></html>") == "html"


def test_sniff_csv():
    assert sniff_format(b"name,rate,currency\nDeluxe,250,USD\n") == "csv"


def test_sniff_plain_text_falls_back_to_txt():
    # Plain text with no format-specific delimiters (e.g. Resort_FAQ.txt)
    # is still a supported format — sniffed as "txt", not rejected.
    assert sniff_format(b"just some plain unstructured text with no delimiters") == "txt"


def test_sniff_unrecognized_content_raises():
    with pytest.raises(ValidationErrorApp):
        # Invalid UTF-8 with none of the known magic-byte signatures —
        # genuinely unclassifiable, unlike plain decodable text.
        sniff_format(b"\xff\xfe\x00\x01\x02\xfe\xff\x00\xff")


def _make_docx_like_zip(inner_names: list[str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in inner_names:
            archive.writestr(name, "content")
    return buffer.getvalue()


def test_sniff_docx_zip():
    content = _make_docx_like_zip(["word/document.xml", "[Content_Types].xml"])
    assert sniff_format(content) == "docx"


def test_sniff_xlsx_zip():
    content = _make_docx_like_zip(["xl/workbook.xml", "[Content_Types].xml"])
    assert sniff_format(content) == "xlsx"


def test_sniff_unrecognized_zip_raises():
    content = _make_docx_like_zip(["random/file.txt"])
    with pytest.raises(ValidationErrorApp):
        sniff_format(content)


def test_sanitize_filename_strips_path_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\evil.exe") == "evil.exe"


def test_sanitize_filename_strips_unsafe_characters():
    result = sanitize_filename("ra🏝️te card (final)!!.pdf")
    assert result.endswith(".pdf")
    assert " " not in result
    assert "(" not in result


def test_sanitize_filename_rejects_empty():
    with pytest.raises(ValidationErrorApp):
        sanitize_filename("///")


def test_validate_upload_rejects_empty_file():
    with pytest.raises(ValidationErrorApp):
        validate_upload("empty.pdf", b"")


def test_validate_upload_rejects_oversized_csv():
    # Each row easily exceeds the 10MB CSV cap when repeated enough times.
    row = ("a," * 200 + "\n").encode()
    content = b"header\n" + row * 60_000
    with pytest.raises(ValidationErrorApp):
        validate_upload("huge.csv", content)


def test_validate_upload_rejects_zip_bomb():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "A" * 50_000_000)
        archive.writestr("[Content_Types].xml", "x")
    content = buffer.getvalue()
    with pytest.raises(ValidationErrorApp):
        validate_upload("bomb.docx", content)


def test_normalize_text_collapses_whitespace_and_strips_artifacts():
    raw = "Room Rate\n\n\n\nDeluxe   Suite\n\x0c$250 / night  \n"
    normalized = normalize_text(raw)
    assert "\n\n\n" not in normalized
    assert "\x0c" not in normalized
    assert normalized == normalized.strip()


def test_strip_repeated_lines_removes_running_header():
    text = "\n".join(
        ["RKPR Resort — Confidential", "Room details here", "RKPR Resort — Confidential", "More content",
         "RKPR Resort — Confidential", "Even more content"]
    )
    cleaned = strip_repeated_lines(text, min_repeats=3)
    assert "RKPR Resort — Confidential" not in cleaned
    assert "Room details here" in cleaned


def test_strip_repeated_lines_keeps_unique_content():
    text = "Line one\nLine two\nLine three"
    assert strip_repeated_lines(text) == text
