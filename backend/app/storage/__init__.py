from app.config import settings
from app.storage.base import PlaybackAuth, Storage  # noqa: F401


def get_storage() -> Storage:
    if settings.storage_mode == "s3":
        from app.storage.s3 import S3Storage
        return S3Storage()
    from app.storage.local import LocalStorage
    return LocalStorage()
