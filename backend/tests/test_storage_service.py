import asyncio
from pathlib import Path

from app.config import get_settings
from app.services.storage_service import get_attachment_storage


def test_local_attachment_storage_round_trip(tmp_path: Path, monkeypatch) -> None:
    """Docker development storage remains available behind the provider boundary."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("FOLLOWUP_ATTACHMENT_DIR", str(tmp_path))
    get_settings.cache_clear()
    get_attachment_storage.cache_clear()

    async def round_trip() -> None:
        storage = get_attachment_storage()
        key = await storage.put("test.txt", b"StarLink", "text/plain")
        assert key == "test.txt"
        assert await storage.get(key) == b"StarLink"
        await storage.delete(key)
        assert not (tmp_path / key).exists()

    try:
        asyncio.run(round_trip())
    finally:
        get_settings.cache_clear()
        get_attachment_storage.cache_clear()
