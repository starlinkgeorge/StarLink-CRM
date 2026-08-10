"""Object-storage boundary for files that must survive serverless execution.

The legacy local backend remains the default for Docker development. Production
can select ``vercel_blob`` so the same follow-up attachment API stores opaque
object URLs instead of paths on a Vercel function's ephemeral filesystem.
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings
from app.services.errors import NotFoundError, StorageConfigurationError


class AttachmentStorage(Protocol):
    async def put(self, key: str, content: bytes, content_type: str | None) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalAttachmentStorage:
    """Development-only storage backed by the Docker-mounted local directory."""

    def _directory(self) -> Path:
        directory = Path(get_settings()["followup_attachment_dir"]).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _path(self, key: str) -> Path:
        directory = self._directory()
        candidate = (directory / key).resolve()
        if candidate.parent != directory:
            raise NotFoundError("Follow-up attachment file is unavailable.")
        return candidate

    async def put(self, key: str, content: bytes, content_type: str | None) -> str:
        self._path(key).write_bytes(content)
        return key

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise NotFoundError("Follow-up attachment file is unavailable.")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class VercelBlobAttachmentStorage:
    """Private Vercel Blob implementation used by the production API."""

    @staticmethod
    def _client():
        token = get_settings()["blob_read_write_token"]
        if not token:
            raise StorageConfigurationError(
                "BLOB_READ_WRITE_TOKEN must be configured for FILE_STORAGE_BACKEND=vercel_blob."
            )
        try:
            from vercel.blob import AsyncBlobClient
        except ImportError as error:  # pragma: no cover - dependency is deployed in production.
            raise StorageConfigurationError(
                "The Vercel Blob SDK is unavailable in this deployment."
            ) from error
        return AsyncBlobClient(token=token)

    async def put(self, key: str, content: bytes, content_type: str | None) -> str:
        async with self._client() as client:
            blob = await client.put(
                f"followups/{key}",
                content,
                access="private",
                content_type=content_type or "application/octet-stream",
                add_random_suffix=False,
            )
        return str(blob.url)

    async def get(self, key: str) -> bytes:
        async with self._client() as client:
            result = await client.get(key, access="private")
            if result is None or result.status_code != 200 or result.stream is None:
                raise NotFoundError("Follow-up attachment file is unavailable.")
            return b"".join([chunk async for chunk in result.stream])

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            await client.delete([key])


@lru_cache
def get_attachment_storage() -> AttachmentStorage:
    backend = get_settings()["file_storage_backend"]
    if backend == "local":
        return LocalAttachmentStorage()
    if backend == "vercel_blob":
        return VercelBlobAttachmentStorage()
    raise StorageConfigurationError(
        "FILE_STORAGE_BACKEND must be either 'local' or 'vercel_blob'."
    )
