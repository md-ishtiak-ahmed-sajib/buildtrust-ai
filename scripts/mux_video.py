"""Optional media tool: uv run --with imageio-ffmpeg python scripts/mux_video.py."""

import json
from pathlib import Path
import subprocess
import imageio_ffmpeg
import hashlib

ROOT = Path(__file__).resolve().parents[1]
media = ROOT / "data/media"
target = ROOT / "submission/BuildTrustAI_Demo.mp4"
subprocess.run(
    [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(media / "browser-recording.webm"),
        "-i",
        str(media / "narration.wav"),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(target),
    ],
    check=True,
)
timeline = json.loads((media / "timing.json").read_text())
recording = json.loads((media / "recording.json").read_text(encoding="utf-8"))
for name, expected in recording["app_source_files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, (
        "Application changed after recording: " + name
    )
reader = imageio_ffmpeg.read_frames(str(target))
metadata = next(reader)
reader.close()
assert 220 <= metadata["duration"] <= 300, metadata
playback = subprocess.run(
    [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-v",
        "error",
        "-i",
        str(target),
        "-f",
        "null",
        "-",
    ],
    capture_output=True,
    text=True,
)
assert playback.returncode == 0, playback.stderr
summary = {
    "duration_seconds": metadata["duration"],
    "planned_duration_seconds": sum(s["duration"] for s in timeline),
    "narration": "Local Windows Microsoft Zira synthetic voice",
    "screen_source": "Actual running application browser recording",
    "simulation": True,
    "playback_decode_passed": True,
    "video_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "recording": recording,
}
(ROOT / "submission/execution-evidence/video-provenance.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
print(target)
