import subprocess
from pathlib import Path

PORTRAIT_RENDITIONS = [(1920, 4000), (1280, 2000), (854, 1000)]  # (height px, video kbps)
LANDSCAPE_RENDITIONS = [(1080, 4500), (720, 2500), (480, 1000)]
RENDITIONS = PORTRAIT_RENDITIONS  # back-compat alias


def probe_duration(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def write_master_playlist(outdir: Path, renditions: list[tuple[int, int]],
                          orientation: str) -> None:
    aspect = 16 / 9 if orientation == "landscape" else 9 / 16
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    # lowest rendition first: players start on it instantly, then adapt up
    for height, kbps in sorted(renditions, key=lambda r: r[1]):
        width = int(height * aspect / 2) * 2
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={kbps * 1100},RESOLUTION={width}x{height}")
        lines.append(f"{height}.m3u8")
    (outdir / "master.m3u8").write_text("\n".join(lines) + "\n")


def transcode_to_hls(src: Path, outdir: Path, orientation: str = "portrait") -> int:
    renditions = LANDSCAPE_RENDITIONS if orientation == "landscape" else PORTRAIT_RENDITIONS
    outdir.mkdir(parents=True, exist_ok=True)
    for height, kbps in renditions:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-vf", f"scale=-2:{height}",
             "-c:v", "libx264", "-preset", "veryfast",
             "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.2)}k", "-bufsize", f"{kbps * 2}k",
             "-c:a", "aac", "-b:a", "128k", "-ac", "2",
             "-hls_time", "4", "-hls_playlist_type", "vod",
             "-hls_segment_filename", str(outdir / f"{height}_%04d.ts"),
             str(outdir / f"{height}.m3u8")],
            check=True, capture_output=True)
    write_master_playlist(outdir, renditions, orientation)
    return round(probe_duration(src))


def make_progressive_mp4(src: Path, out: Path, max_mb: int = 90) -> int:
    """Single H.264 MP4 (faststart) sized to fit under max_mb — used by the
    ImageKit demo storage mode instead of an HLS ladder."""
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(src)
    # bitrate that fits the size budget, capped at 1800k, floored at 400k
    budget_kbps = int(max_mb * 8 * 1000 / max(duration, 1) * 0.9) - 128  # audio reserve
    v_kbps = max(400, min(1800, budget_kbps))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-vf", "scale='if(gt(a,1),1280,-2)':'if(gt(a,1),-2,1280)'",
         "-c:v", "libx264", "-preset", "veryfast",
         "-b:v", f"{v_kbps}k", "-maxrate", f"{int(v_kbps * 1.3)}k", "-bufsize", f"{v_kbps * 2}k",
         "-c:a", "aac", "-b:a", "128k", "-ac", "2",
         "-movflags", "+faststart",
         str(out)],
        check=True, capture_output=True)
    return round(duration)


def extract_frame(src: Path, out_jpg: Path, at_seconds: float = 1.0, height: int = 854) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", str(src), "-frames:v", "1",
         "-vf", f"scale=-2:{height}", str(out_jpg)],
        check=True, capture_output=True)


def extract_thumbnail(src: Path, out_jpg: Path) -> None:
    extract_frame(src, out_jpg)
