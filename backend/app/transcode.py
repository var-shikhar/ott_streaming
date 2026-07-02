import subprocess
from pathlib import Path

RENDITIONS = [(1920, 4000), (1280, 2000), (854, 1000)]  # (long-side px, video kbps)


def probe_duration(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def transcode_to_hls(src: Path, outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    for height, kbps in RENDITIONS:
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
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    # lowest rendition first: players start on it instantly, then adapt up
    for height, kbps in sorted(RENDITIONS, key=lambda r: r[1]):
        width = int(height * 9 / 16 / 2) * 2
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={kbps * 1100},RESOLUTION={width}x{height}")
        lines.append(f"{height}.m3u8")
    (outdir / "master.m3u8").write_text("\n".join(lines) + "\n")
    return round(probe_duration(src))


def extract_thumbnail(src: Path, out_jpg: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
         "-vf", "scale=-2:854", str(out_jpg)],
        check=True, capture_output=True)
