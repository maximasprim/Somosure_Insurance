"""Storage abstraction for uploaded documents.

Dev/local: writes to disk under ./uploads (never served publicly).
Production: should be swapped for Supabase Storage using signed URLs -
see get_storage() below. Never expose a document via a public URL either
way (spec §20).
"""

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

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


def get_storage() -> DocumentStorage:
    if settings.supabase_url and settings.supabase_service_role_key:
        raise NotImplementedError(
            "Supabase Storage credentials are configured but the adapter isn't "
            "built yet - implement SupabaseStorage(DocumentStorage) here rather "
            "than silently falling back to local disk in production."
        )
    return LocalDiskStorage()
