"""Verify the Windows setup script from a fresh source copy, excluding all runtime state."""

import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import httpx
import argparse
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--output", type=Path, default=ROOT / "data" / "clean-install-verification"
)
parser.add_argument("--archive", type=Path)
args = parser.parse_args()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
target = (ROOT / "data" / ("clean-checkout-" + uuid.uuid4().hex[:8])).resolve()
assert target.parent == (ROOT / "data").resolve()
target.mkdir(parents=True)
if args.archive:
    with zipfile.ZipFile(args.archive.resolve()) as source:
        assert source.testzip() is None
        for info in source.infolist():
            parts = Path(info.filename).parts
            if not parts or parts[0] != "buildtrust-ai" or ".." in parts:
                raise ValueError("Unsafe release archive member")
            destination = target.joinpath(*parts[1:]).resolve()
            if not destination.is_relative_to(target):
                raise ValueError("Archive escapes installation directory")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read(info))
    release = json.loads(
        (target / "submission/release-manifest.json").read_text(encoding="utf-8")
    )
    for name, expected in release["files"].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == expected, (
            name
        )
else:
    for name in ["backend", "frontend", "scripts", "demo", "docs", "prompt", ".github"]:
        shutil.copytree(
            ROOT / name,
            target / name,
            ignore=shutil.ignore_patterns(
                ".venv",
                "node_modules",
                "dist",
                "__pycache__",
                ".pytest_cache",
                "test-results",
                "playwright-report",
            ),
        )
    for name in [".env.example", "AGENTS.md", "README.md", "LICENSE"]:
        shutil.copy2(ROOT / name, target / name)
result = subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(target / "scripts/setup.ps1"),
    ],
    cwd=target,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
# The setup output includes newly generated test credentials; redact them from exported logs.
log = result.stdout + result.stderr
credential_file = target / "data/demo-credentials.json"
creds = json.loads(credential_file.read_text()) if credential_file.exists() else {}
for value in creds.values():
    log = log.replace(value, "[generated credential redacted]")
(OUT / "clean-install.log").write_text(log, encoding="utf-8")
assert result.returncode == 0, log[-4000:]
server = subprocess.Popen(
    [
        str(target / "backend/.venv/Scripts/python.exe"),
        "-m",
        "uvicorn",
        "app.main:get_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8002",
        "--log-level",
        "warning",
    ],
    cwd=target / "backend",
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    c = httpx.Client(base_url="http://127.0.0.1:8002", timeout=30)
    for _ in range(100):
        try:
            if c.get("/api/v1/health").is_success:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("Fresh installation did not start")
    assert "BuildTrust AI" in c.get("/").text
    headers = {}
    for role in ["operator", "manager", "admin"]:
        r = c.post(
            "/api/v1/auth/login",
            json={
                "email": role + "@buildtrust.demo",
                "password": creds[role + "@buildtrust.demo"],
            },
        )
        r.raise_for_status()
        headers[role] = {"Authorization": "Bearer " + r.json()["access_token"]}
    invoices = c.get("/api/v1/invoices", headers=headers["operator"]).json()
    steel = next(i for i in invoices if i["invoice_number"] == "INV-STEEL-095")
    report = c.post(
        f"/api/v1/invoices/{steel['id']}/analyze", headers=headers["operator"]
    ).json()
    assert report["difference"] == "1050000.00"
    invoice = next(i for i in invoices if i["invoice_number"] == "INV-CEMENT-070")
    proposal = c.post(
        "/api/v1/payments/proposals",
        headers=headers["operator"],
        json={"invoice_id": invoice["id"]},
    ).json()
    assert proposal["status"] == "PENDING_APPROVAL"
    r = c.post(f"/api/v1/payments/{proposal['id']}/approve", headers=headers["manager"])
    r.raise_for_status()
    r = c.post(
        f"/api/v1/payments/{proposal['id']}/execute",
        headers={**headers["manager"], "Idempotency-Key": "fresh-checkout"},
    )
    r.raise_for_status()
    assert r.json()["balance_after"] == "930000.00"
    assert c.get("/api/v1/audit/verify", headers=headers["manager"]).json()["valid"]
    advanced = c.post("/api/v1/advanced/demo-project", headers=headers["admin"])
    advanced.raise_for_status()
    advanced = advanced.json()
    task = c.post(
        f"/api/v1/materials/{advanced['material_id']}/prices/refresh",
        json={"mode": "DEMO", "quantity": "20"},
        headers=headers["operator"],
    )
    task.raise_for_status()
    task = task.json()
    for _ in range(100):
        status = c.get(
            f"/api/v1/prices/searches/{task['id']}", headers=headers["operator"]
        ).json()
        if status["status"] not in ("QUEUED", "RUNNING"):
            break
        time.sleep(0.1)
    prices = c.get(
        f"/api/v1/materials/{advanced['material_id']}/prices?search_id={task['id']}",
        headers=headers["operator"],
    ).json()
    selected = c.post(
        f"/api/v1/materials/{advanced['material_id']}/prices/select",
        json={
            "estimate_id": advanced["estimate_id"],
            "expected_version": 1,
            "line_id": "steel-line",
            "component_id": "steel-material",
            "observation_id": prices["recommended_observation_id"],
            "search_id": task["id"],
        },
        headers=headers["operator"],
    )
    selected.raise_for_status()
    assert selected.json()["total"] == "1480000.00"
    preview = c.get(
        f"/api/v1/estimates/{advanced['estimate_id']}/forecast",
        headers=headers["operator"],
    ).json()
    assert preview["scenarios"][0]["lowest_balance"] == "520000.00"
    assert preview["recorded_cash"] == "2000000.00"
    summary = {
        "passed": True,
        "setup_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1",
        "source_copy": str(target.relative_to(ROOT)),
        "checks": [
            "locked dependency setup",
            "frontend production build",
            "fresh migrations",
            "generated credentials",
            "static frontend served",
            "steel discrepancy",
            "independent approval",
            "70000.00 settlement",
            "930000.00 closing cash",
            "audit integrity",
            "upgrade material search and immutable selection",
            "1480000.00 estimate and 520000.00 forecast",
        ],
        "simulation": True,
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest()
        if args.archive
        else None,
    }
    (OUT / "clean-install.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(
        "Fresh Windows source-copy installation, payment and estimating smoke tests: PASS"
    )
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
