"""Optional explicit installation of hash-pinned English/Bengali OCR models."""

import argparse
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=ROOT / "data" / "ocr-models")
    folder = parser.parse_args().directory.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "docs" / "ocr-models.lock.json").read_text())
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        for language, model in manifest["models"].items():
            path = folder / f"{language}.traineddata"
            if (
                path.exists()
                and hashlib.sha256(path.read_bytes()).hexdigest() == model["sha256"]
            ):
                print(language, "already verified")
                continue
            with client.stream("GET", model["url"]) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > model["bytes"]:
                        raise ValueError("Model download exceeds pinned size")
            if (
                len(content) != model["bytes"]
                or hashlib.sha256(content).hexdigest() != model["sha256"]
            ):
                raise ValueError("Model checksum verification failed")
            path.write_bytes(content)
            print(language, "verified", model["sha256"])
    print(
        "Set BUILDTRUST_OCR_ENABLED=true and BUILDTRUST_OCR_TESSDATA_DIR=" + str(folder)
    )
    print(
        "Models are Apache-2.0 from "
        + manifest["repository"]
        + " at "
        + manifest["commit"]
    )


if __name__ == "__main__":
    main()
