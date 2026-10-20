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
    "features.md",
    "demo/public-accounts.json",
    "docs/README.md",
    "docs/glossary.md",
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
    "submission/BuildTrustAI_Security_Self_Assessment.pdf",
    "submission/BuildTrustAI_Technical_Documentation.pdf",
    "submission/BuildTrustAI_Project_Overview.pdf",
    "submission/execution-evidence/security-19-acceptance.json",
    "submission/execution-evidence/manifest.json",
    "submission/execution-evidence/clean-install.json",
    "submission/execution-evidence/public-demo-install.json",
    "submission/execution-evidence/documentation-check.json",
    ".gitleaks.toml",
    "submission/execution-evidence/security-secret-scan.json",
    "submission/execution-evidence/security-private-preservation.json",
    "submission/execution-evidence/security-private-backup-restore.json",
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
for receipt in ("public-demo-install.json", "documentation-check.json"):
    assert json.loads(
        (submission / "execution-evidence" / receipt).read_text(encoding="utf-8")
    )["passed"], receipt
accounts = json.loads((ROOT / "demo/public-accounts.json").read_text(encoding="utf-8"))[
    "accounts"
]
readme = (ROOT / "README.md").read_text(encoding="utf-8")
assert all(a["email"] in readme and a["password"] in readme for a in accounts)
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

## Prepared and checked

- [x] Working local app, with a separate public demo and four README passwords
- [x] Private setup still uses generated passwords; public setup does not overwrite private data
- [x] Real PDF/CSV/JSON reading, reviewed fields and saved source references
- [x] Inflated steel claim blocked; valid BDT 70,000 invoice approved by a different person
- [x] Cash reserve checks, exact approval evidence, rollback and one payment on retry
- [x] Accounting, estimates, quantity tools, prices, contracts and reviewed corrections
- [x] Local audit verification and preserved archived demo runs
- [x] {backend_count} backend tests, separately recorded frontend/browser checks and A–H HTTP examples
- [x] Fresh Windows setup, public logins, payment and estimating checks
- [x] Implemented security hardening: private privileged MFA, request/access protections, scans and private backup/restore
- [x] Hosted Windows and Linux security release passed; each skipped one optional OCR model check
- [x] Simple-English README, feature list, glossary and technical/security/judge guides
- [x] Short project overview explains the implemented app, tested examples and current limits
- [x] Real screenshots, labelled charts, flowcharts and readable data tables
- [x] Nine-slide presentation with speaker notes and editable comparison/evidence tables
- [x] {video_label} real app recording with a clearly disclosed local synthetic English voice
- [x] Actual evidence, source fingerprints, archive checksums, AGPL license and dependency attribution
{github_item}

## Team actions still needed

- [x] Registration email sent by the team
- [ ] Receive registration confirmation from the competition organizer
- [ ] Add the real team/presenter details and rehearse the talk within ten minutes
- [ ] Upload the required reports, source link/archive, presentation, video and evidence; keep confirmation

Read docs/remaining-work.md for unresolved tasks, owners and prerequisites. Live free USD/BDT retrieval and storage passed in a separate database. Hosted/platform results are recorded for their actual source revision. All transfers are simulated. No regulatory or professional certification is claimed.
"""
(submission / "submission-checklist.md").write_text(checklist, encoding="utf-8")
excluded = {
    ".git",
    "prompt",
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
    "AGENTS.md",
    "agents.md",
    "presentation-validation.json",
    "presentation-build.log",
    # These receipts are created after packaging/publication. Keeping them
    # beside the archive avoids circular checksums and stale embedded receipts.
    "final-archive-acceptance.json",
    "final-archive-acceptance.log",
    "final-source-agreement.json",
    "security-publication.json",
    "BuildTrustAI_Source.zip",
    "BuildTrustAI_Source.zip.sha256",
    "release-manifest.json",
}
# These are assembled after the source ZIP. Including either would create
# circular archive/checksum references and duplicate the retained evidence.
standalone_delivery_files = {
    "submission/BuildTrustAI_Execution_Evidence.zip",
    "submission/checksums.json",
}
files = []
for directory in [
    "backend",
    "frontend",
    "demo",
    "docs",
    "scripts",

    ".github",
    "submission",
]:
    for item in (ROOT / directory).rglob("*"):
        relative = item.relative_to(ROOT)
        if (
            item.is_file()
            and not item.name.startswith(".env")
            and not any(value in item.name.lower() for value in ("credentials", "signing-secret", "mfa-encryption-key", ".private.zip"))
            and item.suffix.lower() not in (".pem", ".key", ".db", ".sqlite", ".sqlite3")
            and not set(relative.parts).intersection(excluded)
            and item.name not in excluded_files
            and relative.as_posix() not in standalone_delivery_files
            and item.suffix not in (".pyc", ".tsbuildinfo")
        ):
            files.append(item)
files.extend(
    p
    for p in ROOT.iterdir()
    if p.is_file() and p.name not in excluded_files and (not p.name.startswith(".env") or p.name == ".env.example")
    and not any(value in p.name.lower() for value in ("credentials", "signing-secret", "mfa-encryption-key", ".private.zip"))
    and p.suffix.lower() not in (".pem", ".key", ".db", ".sqlite", ".sqlite3")
)
files = sorted(set(files))
for item in files:
    if item.suffix.lower()=='.zip':
        with zipfile.ZipFile(item) as candidate:
            assert not any(Path(n).name in ('private-manifest.json','signing-secret','mfa-encryption-key','demo-credentials.json') for n in candidate.namelist()), 'Private backup cannot be packaged as public source.'
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
    "github_publication_scope": "Historical tested revision; current archive publication is verified separately in security-publication.json beside the archive.",
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
