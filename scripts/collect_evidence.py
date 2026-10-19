"""Run A–H over real HTTP against an isolated, persistent local sandbox."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / ("execution-evidence-" + uuid.uuid4().hex[:8])


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def source_manifest():
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "backend" / "pyproject.toml",
        ROOT / "backend" / "uv.lock",
        ROOT / "frontend" / "package.json",
        ROOT / "frontend" / "package-lock.json",
    ]
    for directory in [
        ROOT / "backend" / "app",
        ROOT / "backend" / "alembic",
        ROOT / "frontend" / "src",
        ROOT / "scripts",
    ]:
        paths.extend(
            p
            for p in directory.rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix
            in (".py", ".sql", ".ts", ".tsx", ".css", ".ps1", ".sh", ".mjs", ".json")
        )
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(set(paths))
    }


def main():
    global OUT
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "data" / ("evidence-" + uuid.uuid4().hex[:10])
    env = {
        **os.environ,
        "BUILDTRUST_DATA_DIR": str(runtime),
        "BUILDTRUST_DEMO_MODE": "true",
        "BUILDTRUST_LLM_PROVIDER": "none",
    }
    seed = subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    (OUT / "seed.log").write_text(seed.stdout + seed.stderr, encoding="utf-8")
    log = (OUT / "runtime.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:get_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        cwd=ROOT / "backend",
        env=env,
        stdout=log,
        stderr=log,
    )
    client = httpx.Client(base_url=f"http://127.0.0.1:{args.port}/api/v1", timeout=30)
    requests = []
    try:
        for _ in range(100):
            try:
                if client.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Evidence API did not start")
        credentials = json.loads((runtime / "demo-credentials.json").read_text())
        headers = {}
        for role in ("admin", "manager", "operator", "auditor"):
            response = client.post(
                "/auth/login",
                json={
                    "email": f"{role}@buildtrust.demo",
                    "password": credentials[f"{role}@buildtrust.demo"],
                },
            )
            response.raise_for_status()
            headers[role] = {
                "Authorization": "Bearer " + response.json()["access_token"]
            }

        def call(method, path, role="operator", expected=200, **kwargs):
            supplied_headers = kwargs.pop("headers", {})
            response = client.request(
                method, path, headers={**headers[role], **supplied_headers}, **kwargs
            )
            requests.append(
                {
                    "timestamp": stamp(),
                    "method": method,
                    "path": path,
                    "http_status": response.status_code,
                }
            )
            assert response.status_code == expected, (
                method,
                path,
                response.status_code,
                response.text,
            )
            return response.json()

        def run(invoice_id):
            started = call(
                "POST", "/agent/analyze", expected=202, json={"invoice_id": invoice_id}
            )
            for _ in range(150):
                result = call("GET", f"/agent/workflows/{started['workflow_id']}")
                if result["status"] not in ("RUNNING", "QUEUED"):
                    return result
                time.sleep(0.1)
            raise RuntimeError("Workflow did not complete")

        results = []
        for scenario in "ABCDEFGH":
            seeded = call("POST", "/demo/reset", role="admin")
            pid = (
                seeded["liquidity_project_id"]
                if scenario == "E"
                else seeded["project_id"]
            )
            invoices = call("GET", f"/invoices?project_id={pid}")
            wanted = {
                "A": "INV-STEEL-095",
                "B": "INV-CEMENT-070",
                "C": "INV-CEMENT-070",
                "D": "INV-BENEFICIARY-CHANGE",
                "E": "INV-LIQUIDITY-070",
                "F": "INV-INJECTION",
                "G": "INV-CEMENT-070",
                "H": "INV-CEMENT-070",
            }[scenario]
            invoice = next(i for i in invoices if i["invoice_number"] == wanted)
            start = call("GET", f"/projects/{pid}")
            audit_start = call("GET", "/audit/verify", role="auditor")
            result = {
                "scenario_id": scenario,
                "executed_at": stamp(),
                "run_id": seeded["run_id"],
                "source_invoice": invoice,
                "balance_before": start["balance"],
                "starting_invoice_count": len(invoices),
                "simulation": True,
            }
            if scenario in "ADEF":
                workflow = run(invoice["id"])
                report = workflow["result"]["verification"]
                result.update(
                    workflow=workflow,
                    decision=report["status"],
                    findings=report["findings"],
                )
                assert report["status"] == "BLOCKED"
                code = {
                    "A": "QUANTITY_MISMATCH",
                    "D": "BENEFICIARY_CHANGE",
                    "E": "INSUFFICIENT_FUNDS",
                    "F": "SUSPICIOUS_INSTRUCTIONS",
                }[scenario]
                assert code in [f["code"] for f in report["findings"]]
                if scenario == "A":
                    assert (
                        report["difference"] == "1050000.00"
                        and report["verified_amount"] == "5600000.00"
                    )
                    assert (
                        report["comparisons"][0]["quantity_variance_percent"] == "18.75"
                    )
            elif scenario == "C":
                content = (ROOT / "demo/fixtures/scenario-b-valid.json").read_bytes()
                duplicate = call(
                    "POST",
                    "/documents/upload",
                    expected=201,
                    data={"project_id": pid},
                    files={
                        "file": ("different-filename.json", content, "application/json")
                    },
                )
                assert duplicate["extraction_status"] == "DUPLICATE"
                after_invoices = call("GET", f"/invoices?project_id={pid}")
                assert len(after_invoices) == len(invoices)
                result.update(
                    decision="DUPLICATE_HELD",
                    duplicate_document=duplicate,
                    ending_invoice_count=len(after_invoices),
                )
            else:
                workflow = run(invoice["id"])
                assert workflow["status"] == "AWAITING_APPROVAL", workflow
                proposal_id = workflow["result"]["proposal_id"]
                result["workflow"] = workflow
                if scenario == "G":
                    denial = call(
                        "POST", f"/payments/{proposal_id}/approve", expected=403
                    )
                    result.update(
                        decision="UNAUTHORIZED_APPROVAL_DENIED", denial=denial
                    )
                    current = next(
                        p
                        for p in call("GET", f"/payments?project_id={pid}")
                        if p["id"] == proposal_id
                    )
                    assert (
                        not current["approvals"]
                        and current["status"] == "PENDING_APPROVAL"
                    )
                else:
                    approval = call(
                        "POST", f"/payments/{proposal_id}/approve", role="manager"
                    )
                    key = "evidence-" + scenario + "-" + uuid.uuid4().hex
                    receipt = call(
                        "POST",
                        f"/payments/{proposal_id}/execute",
                        role="manager",
                        headers={"Idempotency-Key": key},
                    )
                    result.update(
                        decision="SETTLED", approval=approval, receipt=receipt
                    )
                    assert (
                        receipt["amount"] == "70000.00"
                        and receipt["balance_after"] == "930000.00"
                    )
                    if scenario == "H":
                        replay = call(
                            "POST",
                            f"/payments/{proposal_id}/execute",
                            role="manager",
                            headers={"Idempotency-Key": key},
                        )
                        assert replay == receipt
                        settled = [
                            p
                            for p in call("GET", f"/payments?project_id={pid}")
                            if p["status"] == "SETTLED"
                        ]
                        assert len(settled) == 1
                        result.update(
                            retry_response=replay,
                            settled_payment_count=len(settled),
                            identical_retry_response=True,
                        )
            final = call("GET", f"/projects/{pid}")
            result["balance_after"] = final["balance"]
            if scenario not in "BH":
                assert result["balance_after"] == result["balance_before"]
            events = call(
                "GET", f"/audit/events?project_id={pid}&limit=1000", role="auditor"
            )
            result["audit_events"] = [
                e for e in events if e["id"] > audit_start["checked_events"]
            ]
            result["audit_event_ids"] = [e["id"] for e in result["audit_events"]]
            result["audit_integrity"] = call("GET", "/audit/verify", role="auditor")
            assert result["audit_integrity"]["valid"]
            report = (
                result.get("workflow", {}).get("result", {}).get("verification", {})
            )
            ids = {
                invoice["document_id"],
                *[
                    ref["document_id"]
                    for c in report.get("comparisons", [])
                    for ref in c["evidence"]
                ],
            }
            result["source_records"] = [
                call("GET", f"/documents/{identity}/extraction", role="auditor")
                for identity in sorted(ids)
            ]
            result["passed"] = True
            (OUT / f"scenario-{scenario.lower()}.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            (OUT / f"scenario-{scenario.lower()}.md").write_text(
                f"# Scenario {scenario}\n\nExecuted: {result['executed_at']}\n\nDecision: **{result['decision']}**\n\nBalance before: BDT {result['balance_before']}\n\nBalance after: BDT {result['balance_after']}\n\nAudit events: {', '.join(map(str, result['audit_event_ids']))}\n\nActual HTTP inputs, source provenance, workflow stages, findings, and receipt (where applicable): `scenario-{scenario.lower()}.json`.\n\nAll identities and transfers are fictional sandbox records.\n",
                encoding="utf-8",
            )
            results.append(
                {
                    k: result[k]
                    for k in (
                        "scenario_id",
                        "executed_at",
                        "decision",
                        "balance_before",
                        "balance_after",
                        "passed",
                    )
                }
            )
            print(f"Scenario {scenario}: PASS — {result['decision']}", flush=True)
        fingerprints = source_manifest()
        manifest = {
            "generated_at": stamp(),
            "transport": "Real local HTTP + persistent SQLite",
            "simulation": True,
            "source_fingerprint": hashlib.sha256(
                json.dumps(fingerprints, sort_keys=True).encode()
            ).hexdigest(),
            "source_files": fingerprints,
            "scenarios": results,
            "audit_integrity": call("GET", "/audit/verify", role="auditor"),
            "runtime_database": str(runtime.relative_to(ROOT) / "buildtrust.db"),
        }
        (OUT / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        (OUT / "http-operations.json").write_text(
            json.dumps(requests, indent=2), encoding="utf-8"
        )
        print("All 8 scenarios passed against the running sandbox API.")
    finally:
        client.close()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()


if __name__ == "__main__":
    main()
