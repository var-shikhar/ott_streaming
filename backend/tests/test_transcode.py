import shutil
import subprocess

import pytest

ffmpeg_missing = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None


@pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg not installed")
def test_transcode_produces_hls(tmp_path):
    from app.transcode import probe_duration, transcode_to_hls

    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "hls"
    duration = transcode_to_hls(src, out)
    assert (out / "master.m3u8").is_file()
    assert (out / "854.m3u8").is_file()
    assert list(out.glob("854_*.ts"))
    assert 1 <= duration <= 3
    master = (out / "master.m3u8").read_text()
    assert "#EXT-X-STREAM-INF" in master and "854.m3u8" in master
    assert probe_duration(src) > 0
