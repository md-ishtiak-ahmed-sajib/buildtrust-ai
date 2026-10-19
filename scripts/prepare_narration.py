import json
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parents[1]
segments = json.loads((ROOT / "scripts/demo_segments.json").read_text())
media = ROOT / "data/media"
params = None
frames = []
timeline = []
elapsed = 0
for index, segment in enumerate(segments):
    with wave.open(str(media / f"scene-{index}.wav"), "rb") as sound:
        if params is None:
            params = sound.getparams()
        assert (sound.getnchannels(), sound.getsampwidth(), sound.getframerate()) == (
            params.nchannels,
            params.sampwidth,
            params.framerate,
        )
        spoken = sound.getnframes() / sound.getframerate()
        duration = max(segment["seconds"], int(spoken + 2))
        content = sound.readframes(sound.getnframes())
        silence = bytes(
            int((duration - spoken) * params.framerate)
            * params.nchannels
            * params.sampwidth
        )
        frames.extend([content, silence])
        timeline.append(
            {
                **segment,
                "start": elapsed,
                "duration": duration,
                "spoken_seconds": spoken,
            }
        )
        elapsed += duration
with wave.open(str(media / "narration.wav"), "wb") as output:
    output.setparams(params)
    output.writeframes(b"".join(frames))
assert elapsed <= 290, f"Recording would exceed submission limit: {elapsed}s"
(media / "timing.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
(ROOT / "docs/demo-script.md").write_text(
    "# Demonstration script\n\nThis video shows the actual app in a separate fictional database. Narration uses the local Microsoft Zira synthetic voice. Screen actions, amounts and receipts come from the running app. No success screen or transaction reference is invented. The public demo in README uses a different separate profile.\n\n"
    + "\n\n".join(
        f"## {int(s['start'] // 60)}:{int(s['start'] % 60):02d} - {s['title']}\n\n{s['text']}"
        for s in timeline
    )
    + "\n\nFor a new recording, use the isolated recording wrapper and its own generated accounts. Follow these scenes and stay below five minutes. Do not reset the working database. For a personal trial, use the separate public launcher and README passwords.\n",
    encoding="utf-8",
)
print(f"Prepared narration and scene timing: {elapsed} seconds")
