"""Storage abstraction for uploaded documents.

Dev/local: writes to disk under ./uploads (never served publicly).
Production: Supabase Storage, accessed over its REST API with the service
role key, using signed URLs for any read (spec §20) - see SupabaseStorage
and get_storage() below. Never expose a document via a public URL either
way.
"""

import mimetypes
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.core.config import get_settings

settings = get_settings()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


class DocumentStorage(ABC):
    @abstractmethod
    async def save(self, category: str, filename: str, content: bytes) -> str:
        """Persist content, return a storage_path (not a public URL)."""

    @abstractmethod
    async def get_signed_url(self, storage_path: str, expires_seconds: int = 300) -> str:
        """Return a short-lived URL for authorized access only."""


class LocalDiskStorage(DocumentStorage):
    """Dev-only. Not suitable for production - no access control beyond
    the path itself being unguessable, and no CDN/signing."""

    def __init__(self, root: str = "./uploads"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, category: str, filename: str, content: bytes) -> str:
        safe_name = f"{uuid.uuid4().hex}_{filename}"
        category_dir = self.root / category
        category_dir.mkdir(parents=True, exist_ok=True)
        path = category_dir / safe_name
        path.write_bytes(content)
        return str(path.relative_to(self.root))

    async def get_signed_url(self, storage_path: str, expires_seconds: int = 300) -> str:
        # Placeholder: in dev, the app itself serves this behind auth.
        # A real signed-URL scheme belongs to whichever object store is used.
        return f"/api/v1/documents/local/{storage_path}"


class SupabaseStorage(DocumentStorage):
    """Production storage. Uploads go straight to a private Supabase Storage
    bucket over its REST API using the service role key - the bucket must
    NOT be public. Reads always go through a freshly-issued signed URL;
    nothing here is ever cached as a public link.
    """

    def __init__(self, url: str, service_role_key: str, bucket: str):
        self.base_url = url.rstrip("/")
        self.bucket = bucket
        self._auth_headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
        }

    async def save(self, category: str, filename: str, content: bytes) -> str:
        safe_name = f"{uuid.uuid4().hex}_{filename}"
        object_path = f"{category}/{safe_name}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/storage/v1/object/{self.bucket}/{object_path}",
                headers={**self._auth_headers, "Content-Type": content_type},
                content=content,
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Supabase Storage upload failed ({resp.status_code}): {resp.text}"
            )
        return object_path

    async def get_signed_url(self, storage_path: str, expires_seconds: int = 300) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{storage_path}",
                headers=self._auth_headers,
                json={"expiresIn": expires_seconds},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Supabase Storage signing failed ({resp.status_code}): {resp.text}"
            )
        signed_path = resp.json()["signedURL"]  # e.g. /object/sign/<bucket>/<path>?token=...
        return f"{self.base_url}/storage/v1{signed_path}"


def get_storage() -> DocumentStorage:
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseStorage(
            settings.supabase_url,
            settings.supabase_service_role_key,
            settings.supabase_storage_bucket,
        )
    return LocalDiskStorage()