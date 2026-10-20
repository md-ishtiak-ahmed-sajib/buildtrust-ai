"""Run the supplied shell setup/launcher in an isolated native Linux CI profile."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import httpx
from verification_client import VerificationClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit(
            "This check requires native Linux. Do not use Docker's managed WSL distribution."
        )
    runtime = ROOT / "data" / ("linux-startup-" + uuid.uuid4().hex[:8])
    runtime.mkdir(parents=True)
    env = {
        **os.environ,
        "BUILDTRUST_DATA_DIR": str(runtime),
        "BUILDTRUST_LLM_PROVIDER": "none",
        "BUILDTRUST_SERPAPI_KEY": "",
        "BUILDTRUST_DATAFORSEO_LOGIN": "",
        "BUILDTRUST_DATAFORSEO_PASSWORD": "",
    }
    setup = subprocess.run(
        ["bash", "scripts/setup.sh"], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert setup.returncode == 0, "Linux setup failed; no private profile was used."
    with (runtime / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            ["bash", "scripts/run_demo.sh"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            client = VerificationClient(base_url="http://127.0.0.1:8000", timeout=30)
            for _ in range(200):
                if process.poll() is not None:
                    raise RuntimeError("Linux launcher stopped before health was ready")
                try:
                    if client.get("/api/v1/health").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Linux launcher did not become ready")
            credentials = json.loads((runtime / "demo-credentials.json").read_text())
            headers = {}
            for role in ("operator", "manager", "admin", "auditor"):
                response = client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": role + "@buildtrust.demo",
                        "password": credentials[role + "@buildtrust.demo"],
                    },
                )
                response.raise_for_status()
                headers[role] = {
                    "Authorization": "Bearer " + response.json()["access_token"]
                }
            assert "BuildTrust AI" in client.get("/").text
            assert client.get(
                "/api/v1/audit/verify", headers=headers["auditor"]
            ).json()["valid"]
            client.close()
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=20)
    result = {
        "passed": True,
        "platform": sys.platform,
        "setup": "scripts/setup.sh",
        "launcher": "scripts/run_demo.sh",
        "four_private_logins": True,
        "static_frontend": True,
        "audit_valid": True,
        "isolated_data": True,
    }
    (runtime / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Native Linux shell setup, launcher, four logins and audit: PASS")
    print("Isolated result:", runtime / "result.json")


if __name__ == "__main__":
    main()
