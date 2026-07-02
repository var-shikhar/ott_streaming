import shutil
from pathlib import Path

from app.config import settings
from app.storage.base import PlaybackAuth


class LocalStorage:
    def __init__(self):
        self.root = Path(settings.media_root)

    def publish(self, episode_id: str, local_dir: Path) -> str:
        dest = self.root / episode_id
        if dest.resolve() != local_dir.resolve():
            dest.mkdir(parents=True, exist_ok=True)
            for f in local_dir.iterdir():
                shutil.copy2(f, dest / f.name)
        return f"{episode_id}/master.m3u8"

    def playback(self, hls_path: str) -> PlaybackAuth:
        return PlaybackAuth(url=f"{settings.api_base_url}/media/{hls_path}")
