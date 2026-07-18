"""Supabase Storage client for knowledge source files.

Uses the service_role key (server-side only, never sent to a client) via
httpx against the Storage REST API — same pattern as app.auth.service's
GoTrue proxy. All knowledge object bytes live in one private bucket
(`knowledge_storage_bucket`, default "knowledge-documents"); DB rows only
ever store the storage_path, never a public URL, so visibility is enforced
by our own retrieval query rather than bucket ACLs alone.
"""

import httpx

from app.config import get_settings
from app.errors import AppError
from app.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class StorageError(AppError):
    code = "STORAGE_ERROR"
    status_code = 502


def _headers(*, content_type: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {settings.supabase_service_role_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def ensure_bucket_exists() -> None:
    """Idempotent bucket creation, called once at startup. A private bucket
    (public=false) — every read goes through the backend's service_role
    connection, never a direct public URL."""
    bucket = settings.knowledge_storage_bucket
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.supabase_storage_url}/bucket/{bucket}", headers=_headers()
        )
        if response.status_code == 200:
            return
        response = await client.post(
            f"{settings.supabase_storage_url}/bucket",
            headers=_headers(content_type="application/json"),
            json={"id": bucket, "name": bucket, "public": False},
        )
    if response.status_code not in (200, 201):
        # Non-fatal: bucket may already exist under a race, or storage
        # setup may be deferred to a manual Supabase console step. Log
        # loudly rather than crash startup — upload calls will fail
        # explicitly (StorageError) if the bucket truly doesn't exist.
        logger.warning(
            "knowledge_bucket_ensure_failed",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )


async def upload_file(path: str, content: bytes, *, content_type: str = "application/octet-stream") -> str:
    bucket = settings.knowledge_storage_bucket
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.supabase_storage_url}/object/{bucket}/{path}",
            headers=_headers(content_type=content_type),
            content=content,
        )
    if response.status_code not in (200, 201):
        raise StorageError(f"Failed to upload {path}: {response.status_code} {response.text[:300]}")
    return path


async def download_file(path: str) -> bytes:
    bucket = settings.knowledge_storage_bucket
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{settings.supabase_storage_url}/object/{bucket}/{path}", headers=_headers()
        )
    if response.status_code != 200:
        raise StorageError(f"Failed to download {path}: {response.status_code}")
    return response.content


async def delete_file(path: str) -> None:
    bucket = settings.knowledge_storage_bucket
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{settings.supabase_storage_url}/object/{bucket}/{path}", headers=_headers()
        )
    if response.status_code not in (200, 204):
        logger.warning("knowledge_file_delete_failed", extra={"path": path, "status_code": response.status_code})
