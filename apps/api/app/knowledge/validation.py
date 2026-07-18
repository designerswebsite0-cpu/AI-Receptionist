"""Upload validation: MIME/magic-byte sniffing, size limits, filename
sanitization, ZIP-bomb detection. Runs before any file is written to
Storage or handed to a parser — "validate at the boundary" (docs/CLAUDE.md
Security section).

Deliberately does not depend on python-magic/libmagic: that requires a
native shared library that isn't reliably installable on this dev
environment (Windows, no package manager assumption), and the handful of
formats this pipeline accepts (PDF, DOCX, XLSX, CSV, HTML, common image
types) are distinguishable from their own byte signatures without it.
"""

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO

from app.errors import ValidationErrorApp

# (extension, declared mime types accepted, magic-byte signature, max size)
_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024  # 25 MB — largest real RKPR source is low-single-digit MB
_MAX_IMAGE_BYTES = 15 * 1024 * 1024
_MAX_CSV_BYTES = 10 * 1024 * 1024

_SIGNATURES: dict[str, bytes] = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
}
# DOCX/XLSX are ZIP containers (PK\x03\x04); disambiguated by their
# internal [Content_Types].xml, not just the outer ZIP signature.
_ZIP_SIGNATURE = b"PK\x03\x04"

_FORMAT_MAX_BYTES = {
    "pdf": _MAX_DOCUMENT_BYTES,
    "docx": _MAX_DOCUMENT_BYTES,
    "xlsx": _MAX_DOCUMENT_BYTES,
    "csv": _MAX_CSV_BYTES,
    "html": _MAX_DOCUMENT_BYTES,
    "png": _MAX_IMAGE_BYTES,
    "jpg": _MAX_IMAGE_BYTES,
    "txt": _MAX_CSV_BYTES,
}

# ZIP-bomb guard for docx/xlsx: reject if the archive claims a decompressed
# size wildly larger than its compressed size, or contains an implausible
# number of entries for a document.
_MAX_ZIP_COMPRESSION_RATIO = 100
_MAX_ZIP_ENTRY_COUNT = 2000

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class ValidationResult:
    file_format: str
    sanitized_filename: str
    size_bytes: int


def sanitize_filename(filename: str) -> str:
    """Strips any directory components and replaces unsafe characters —
    the sanitized name is used to build the Storage path, so a raw
    filename like "../../etc/passwd" or one containing null bytes must
    never reach it."""
    base = filename.replace("\\", "/").split("/")[-1].strip()
    if not base:
        raise ValidationErrorApp("Filename is empty after sanitization")
    base = base.replace("\x00", "")
    if "." in base:
        name, _, ext = base.rpartition(".")
    else:
        name, ext = base, ""
    name = _FILENAME_SAFE.sub("_", name)[:200] or "file"
    ext = _FILENAME_SAFE.sub("", ext)[:10]
    return f"{name}.{ext}" if ext else name


def sniff_format(content: bytes) -> str:
    if content.startswith(_SIGNATURES["pdf"]):
        return "pdf"
    if content.startswith(_SIGNATURES["png"]):
        return "png"
    if content.startswith(_SIGNATURES["jpg"]):
        return "jpg"
    if content.startswith(_ZIP_SIGNATURE):
        return _sniff_zip_office_format(content)
    if _looks_like_html(content):
        return "html"
    if _looks_like_csv(content):
        return "csv"
    if _looks_like_plain_text(content):
        return "txt"
    raise ValidationErrorApp("File content does not match a supported format's signature")


def _sniff_zip_office_format(content: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ValidationErrorApp("File declares a ZIP signature but is not a valid ZIP archive") from exc

    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    raise ValidationErrorApp("ZIP-based file is not a recognized DOCX or XLSX document")


def _looks_like_html(content: bytes) -> bool:
    head = content[:1024].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _looks_like_csv(content: bytes) -> bool:
    try:
        sample = content[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not sample:
        return False
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    return "," in first_line or ";" in first_line or "\t" in first_line


def _looks_like_plain_text(content: bytes) -> bool:
    """Fallback for genuinely plain files like Resort_FAQ.txt: no
    distinguishing magic bytes exist for ".txt", so anything that decodes
    cleanly as UTF-8 and isn't null-byte-laden binary is accepted as text.
    Checked last, after every more specific format has had a chance."""
    if b"\x00" in content[:4096]:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def check_zip_bomb(content: bytes) -> None:
    """Only meaningful for docx/xlsx (ZIP-based); called after
    sniff_format confirms the container is a valid ZIP."""
    with zipfile.ZipFile(BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > _MAX_ZIP_ENTRY_COUNT:
            raise ValidationErrorApp(f"Archive has too many entries ({len(infos)} > {_MAX_ZIP_ENTRY_COUNT})")
        total_compressed = sum(i.compress_size for i in infos) or 1
        total_uncompressed = sum(i.file_size for i in infos)
        ratio = total_uncompressed / total_compressed
        if ratio > _MAX_ZIP_COMPRESSION_RATIO:
            raise ValidationErrorApp(f"Archive compression ratio ({ratio:.0f}x) exceeds the safety limit")


def validate_upload(filename: str, content: bytes) -> ValidationResult:
    if not content:
        raise ValidationErrorApp("Uploaded file is empty")

    file_format = sniff_format(content)
    max_bytes = _FORMAT_MAX_BYTES[file_format]
    if len(content) > max_bytes:
        raise ValidationErrorApp(
            f"File is {len(content)} bytes, exceeding the {max_bytes} byte limit for {file_format}"
        )

    if file_format in ("docx", "xlsx"):
        check_zip_bomb(content)

    return ValidationResult(
        file_format=file_format,
        sanitized_filename=sanitize_filename(filename),
        size_bytes=len(content),
    )
