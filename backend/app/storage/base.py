from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class PlaybackAuth:
    url: str
    cookies: dict[str, str] = field(default_factory=dict)


class Storage(Protocol):
    def publish(self, episode_id: str, local_dir: Path) -> str:
        """Upload a directory of HLS files; return the hls_path to store on the episode."""
        ...

    def playback(self, hls_path: str) -> PlaybackAuth:
        """Return the playable master playlist URL plus any auth cookies."""
        ...
