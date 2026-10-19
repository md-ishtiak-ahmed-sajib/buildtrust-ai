"""Exercise the Windows launcher only in an isolated source copy, never the working DB."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def snapshot(directory):
    result = {"tables": {}, "files": {}}
    connection = sqlite3.connect(
        f"file:{(directory / 'buildtrust.db').as_posix()}?mode=ro", uri=True
    )
    try:
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            rows = list(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
            result["tables"][name] = hashlib.sha256(
                json.dumps(rows, default=str).encode()
            ).hexdigest()
    finally:
        connection.close()
    files = [
        directory / "demo-credentials.json",
        directory / "signing-secret",
        *(directory / "uploads").rglob("*"),
    ]
    for path in files:
        if path.is_file():
            result["files"][path.relative_to(directory).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target, output = args.root.resolve(), args.output.resolve()
    if not target.is_relative_to(ROOT / "data") or target == ROOT / "data":
        raise SystemExit(
            "Use a fresh source copy under data/, not your working project."
        )
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot(target / "data")
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(target / "scripts/try_demo.ps1"),
    ]
    with (output / "public-demo-launcher.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(command, cwd=target, stdout=log, stderr=log)
        try:
            client = httpx.Client(base_url="http://127.0.0.1:8003", timeout=30)
            for _ in range(900):
                if server.poll() is not None:
                    raise RuntimeError("Public launcher failed; see its isolated log.")
                try:
                    if client.get("/api/v1/health").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError(
                    "Public launcher did not start within three minutes."
                )
            assert "BuildTrust AI" in client.get("/").text
            accounts = json.loads((target / "demo/public-accounts.json").read_text())[
                "accounts"
            ]
            headers = {}
            for account in accounts:
                response = client.post(
                    "/api/v1/auth/login",
                    json={"email": account["email"], "password": account["password"]},
                )
                response.raise_for_status()
                headers[account["role"]] = {
                    "Authorization": "Bearer " + response.json()["access_token"]
                }
            operator, manager, auditor = (
                headers[r] for r in ("OPERATOR", "FINANCE_MANAGER", "AUDITOR")
            )
            invoices = client.get("/api/v1/invoices", headers=operator).json()
            invoice = next(
                i for i in invoices if i["invoice_number"] == "INV-CEMENT-070"
            )
            assert (
                client.post(
                    "/api/v1/payments/proposals",
                    json={"invoice_id": invoice["id"]},
                    headers=auditor,
                ).status_code
                == 403
            )
            response = client.post(
                "/api/v1/payments/proposals",
                json={"invoice_id": invoice["id"]},
                headers=operator,
            )
            response.raise_for_status()
            proposal = response.json()
            assert (
                client.post(
                    f"/api/v1/payments/{proposal['id']}/approve", headers=operator
                ).status_code
                == 403
            )
            client.post(
                f"/api/v1/payments/{proposal['id']}/approve", headers=manager
            ).raise_for_status()
            response = client.post(
                f"/api/v1/payments/{proposal['id']}/execute",
                headers={**manager, "Idempotency-Key": "fresh-public-demo"},
            )
            response.raise_for_status()
            assert response.json()["balance_after"] == "930000.00"
            assert client.get("/api/v1/audit/verify", headers=auditor).json()["valid"]
            providers = client.get("/api/v1/prices/providers", headers=operator)
            providers.raise_for_status()
            (output / "public-provider-status.json").write_text(
                json.dumps(providers.json(), indent=2), encoding="utf-8"
            )
            occupied = subprocess.run(
                command, cwd=target, capture_output=True, text=True, timeout=20
            )
            assert (
                occupied.returncode
                and "already in use" in occupied.stdout + occupied.stderr
            )
            client.close()
        finally:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                    capture_output=True,
                )
            else:
                server.terminate()
            server.wait(timeout=20)
    public_before = snapshot(target / "data/public-demo")
    prepared = subprocess.run(
        [
            str(target / "backend/.venv/Scripts/python.exe"),
            "-m",
            "app.public_demo",
            "--prepare-only",
        ],
        cwd=target / "backend",
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stderr
    assert snapshot(target / "data/public-demo") == public_before
    assert snapshot(target / "data") == before
    receipt = {
        "passed": True,
        "profile": "isolated public demo",
        "port": 8003,
        "four_readme_passwords_login": True,
        "operator_self_approval_denied": True,
        "auditor_write_denied": True,
        "independent_payment_balance": "930000.00",
        "audit_valid": True,
        "repeat_prepare_preserved_records": True,
        "occupied_port_failed_clearly": True,
        "private_profile_unchanged": True,
        "private_table_count": len(before["tables"]),
        "simulation": True,
    }
    (output / "public-demo-install.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(
        "Fresh Windows public-demo launcher, four logins, payment and preservation: PASS"
    )


if __name__ == "__main__":
    main()
