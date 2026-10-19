"""Package source and verified submission artifacts, excluding all private runtime state."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile
import argparse
import tomllib

parser = argparse.ArgumentParser(
    description="Regenerate submission artifacts only on explicit instruction"
)
parser.add_argument("--update-submission", action="store_true", required=True)
parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
submission = ROOT / "submission"
required = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "backend/uv.lock",
    "frontend/package-lock.json",
    "docs/technical-documentation.md",
    "docs/security-self-assessment.md",
    "docs/financial-rules.md",
    "docs/test-results.md",
    "docs/demo-script.md",
    "docs/judges-quickstart.md",
    "submission/BuildTrustAI_Presentation.pptx",
    "submission/BuildTrustAI_Demo.mp4",
    "submission/execution-evidence/manifest.json",
    "submission/execution-evidence/clean-install.json",
]
for name in required:
    assert (ROOT / name).is_file(), f"Missing deliverable: {name}"
evidence = json.loads(
    (submission / "execution-evidence/manifest.json").read_text(encoding="utf-8")
)
from collect_evidence import source_manifest

assert source_manifest() == evidence["source_files"], (
    "Source file set or content changed after evidence capture"
)
assert len(evidence["scenarios"]) == 8 and all(
    s["passed"] for s in evidence["scenarios"]
)
assert evidence["audit_integrity"]["valid"]
for name, expected in evidence["source_files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, (
        f"Source changed after evidence capture: {name}"
    )
assert json.loads((submission / "execution-evidence/clean-install.json").read_text())[
    "passed"
]
backend = (submission / "execution-evidence/backend-tests.log").read_text(
    encoding="utf-8-sig"
)
assert re.search(r"[1-9][0-9]* passed", backend) and "FAILED" not in backend
backend_count = int(re.search(r"(\d+) passed", backend)[1])
video = json.loads(
    (submission / "execution-evidence/video-provenance.json").read_text()
)
assert video["duration_seconds"] <= 300 and video["playback_decode_passed"]
for name, expected in video["recording"]["app_source_files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, (
        "Video application source changed: " + name
    )
video_label = (
    f"{int(video['duration_seconds'] // 60)}:{int(video['duration_seconds'] % 60):02d}"
)
repository = "https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai"
publication_file = submission / "execution-evidence/github-publication.json"
publication = (
    json.loads(publication_file.read_text(encoding="utf-8"))
    if publication_file.exists()
    else None
)
published = bool(publication and publication.get("remote_commit_verified"))
github_item = (
    f"- [x] Reviewed source published to {repository}; verified commit and hosted-run evidence are recorded separately"
    if published
    else f"- [ ] Push the reviewed source to the authorized repository: {repository}"
)

checklist = f"""# Submission checklist

Deadline: October 20, 2026, 21:59 Dhaka / 23:59 Beijing. Target upload readiness remains 20:00 Dhaka.

## Generated and verified

- [x] Functional local application and generated demo accounts
- [x] Actual PDF, CSV, and JSON contents; editable extraction and provenance
- [x] Four-way verification, BDT 1,050,000 steel excess, and compliant BDT 70,000 invoice
- [x] Base/stress liquidity gating and dedicated liquidity-shortfall project
- [x] Independent authorization, exact snapshots, role ceilings, reservations, atomic settlement, and idempotency
- [x] Verifiable local audit chain and preserved reset history
- [x] {backend_count} backend tests and separately recorded frontend/browser checks, plus A–H HTTP evidence
- [x] Fresh Windows setup and payment smoke test
- [x] Technical documentation, financial rules, security assessment, threat model, API reference, and limitations
- [x] Nine-slide presentation with notes, actual screenshots, editable comparison/evidence tables, and architecture
- [x] {video_label} actual browser recording with locally synthesized English narration
- [x] Reproducible execution evidence, source fingerprints, and release checksums
- [x] AGPL license, dependency locks, attribution, and source archive
{github_item}

## Human submission actions

- [ ] Confirm team registration with the competition organizer
- [ ] Review team identity/presenter information and rehearse the deck within ten minutes
- [ ] Upload the required reports, source link/archive, deck, video, and execution evidence before the deadline

Unresolved external prerequisites, owners and next actions are listed in prompt/Not implemented.md. Live free USD/BDT persistence passed in an isolated database. Hosted CI is reported by its actual run receipt; it is separate from native local platform acceptance. No real bank transfer or regulatory certification is claimed.
"""
(submission / "submission-checklist.md").write_text(checklist, encoding="utf-8")
excluded = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "test-results",
    "playwright-report",
    "data",
}
excluded_files = {
    ".env",
    "BuildTrustAI_Source.zip",
    "BuildTrustAI_Source.zip.sha256",
    "release-manifest.json",
}
files = []
for directory in [
    "backend",
    "frontend",
    "demo",
    "docs",
    "scripts",
    "prompt",
    ".github",
    "submission",
]:
    for item in (ROOT / directory).rglob("*"):
        relative = item.relative_to(ROOT)
        if (
            item.is_file()
            and not set(relative.parts).intersection(excluded)
            and item.name not in excluded_files
            and item.suffix not in (".pyc", ".tsbuildinfo")
        ):
            files.append(item)
files.extend(
    p
    for p in ROOT.iterdir()
    if p.is_file() and p.name not in excluded_files and p.name != ".env"
)
files = sorted(set(files))
checksums = {
    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in files
}
release = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "version": tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())[
        "project"
    ]["version"],
    "simulation": True,
    "source_fingerprint": evidence["source_fingerprint"],
    "file_count": len(files),
    "files": checksums,
    "private_runtime_included": False,
    "repository": repository,
    "git_remote_published": published,
    "github_publication": publication,
    "competition_submitted": False,
}
manifest = submission / "release-manifest.json"
manifest.write_text(json.dumps(release, indent=2), encoding="utf-8")
archive = submission / "BuildTrustAI_Source.zip"
with zipfile.ZipFile(
    archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
) as output:
    for item in [*files, manifest]:
        output.write(item, Path("buildtrust-ai") / item.relative_to(ROOT))
with zipfile.ZipFile(archive) as output:
    assert output.testzip() is None
    assert not any(
        set(Path(name).parts).intersection(excluded)
        or Path(name).name == "demo-credentials.json"
        for name in output.namelist()
    )
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(submission / "BuildTrustAI_Source.zip.sha256").write_text(
    digest + "  BuildTrustAI_Source.zip\n", encoding="utf-8"
)
print(f"Packaged {len(files) + 1} files: {archive} ({archive.stat().st_size:,} bytes)")
print("Archive integrity and private-state exclusion: PASS")
