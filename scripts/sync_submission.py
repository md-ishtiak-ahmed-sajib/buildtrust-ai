"""Keep the public submission and local email bundle in agreement."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
EMAIL = ROOT / "data/email-attachments-security-final"
FILES = (
    "BuildTrustAI_Technical_Documentation.pdf",
    "BuildTrustAI_Security_Self_Assessment.pdf",
    "BuildTrustAI_Project_Overview.pdf",
    "BuildTrustAI_Presentation.pptx",
    "BuildTrustAI_Demo.mp4",
    "BuildTrustAI_Source.zip",
    "BuildTrustAI_Execution_Evidence.zip",
)
POST_PACKAGE = (
    "final-archive-acceptance.json",
    "final-archive-acceptance.log",
    "final-source-agreement.json",
    "security-publication.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_changed(source: Path, target: Path) -> None:
    if not target.exists() or digest(source) != digest(target):
        shutil.copyfile(source, target)


def import_email() -> None:
    expected = json.loads((EMAIL / "checksums.json").read_text(encoding="utf-8"))
    # Validate the complete source bundle before changing any public file.
    for name in FILES:
        if not (EMAIL / name).is_file() or expected.get(name) != digest(EMAIL / name):
            raise ValueError(f"Email bundle checksum failed: {name}")
    for name in FILES:
        copy_changed(EMAIL / name, SUBMISSION / name)
    write_checksums()


def write_checksums() -> dict[str, str]:
    values = {name: digest(SUBMISSION / name) for name in FILES}
    (SUBMISSION / "checksums.json").write_text(
        json.dumps(values, indent=2) + "\n", encoding="utf-8"
    )
    return values


def refresh_evidence() -> None:
    evidence = SUBMISSION / "execution-evidence"
    paths = sorted(
        path for path in evidence.rglob("*")
        if path.is_file()
        and path.name not in {"presentation-build.log", "presentation-validation.json"}
    )
    paths += [SUBMISSION / name for name in POST_PACKAGE]
    for path in paths:
        if path.name in {
            "signing-secret", "mfa-encryption-key", "private-manifest.json"
        } or any(word in path.name.lower() for word in ("credentials", ".private.zip")):
            raise ValueError("Private file cannot enter execution evidence")
        if not path.is_file():
            raise ValueError(f"Missing post-package receipt: {path.name}")
    (ROOT / "data").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="submission-bundle-", dir=ROOT / "data") as temp:
        temporary = Path(temp).resolve()
        if temporary.parent != (ROOT / "data").resolve():
            raise ValueError("Temporary bundle escaped its workspace")
        candidate = temporary / FILES[-1]
        with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out:
            for path in paths:
                out.write(path, path.relative_to(SUBMISSION))
        with zipfile.ZipFile(candidate) as out:
            if out.testzip() is not None or len(out.namelist()) != len(set(out.namelist())):
                raise ValueError("Evidence archive integrity failed")
        copy_changed(candidate, SUBMISSION / FILES[-1])
    write_checksums()


def sync_email() -> None:
    EMAIL.mkdir(parents=True, exist_ok=True)
    for name in (*FILES, "checksums.json"):
        copy_changed(SUBMISSION / name, EMAIL / name)
    if any(digest(SUBMISSION / name) != digest(EMAIL / name) for name in (*FILES, "checksums.json")):
        raise ValueError("Submission and email bundle differ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--import-email", action="store_true")
    action.add_argument("--refresh", action="store_true")
    parser.add_argument("--sync-email", action="store_true")
    args = parser.parse_args()
    if args.import_email:
        import_email()
    else:
        refresh_evidence()
    if args.sync_email:
        sync_email()
    print("Seven submission files and checksums verified.")


if __name__ == "__main__":
    main()
