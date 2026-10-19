"""Run old and new browser flows against a separate database; no submission artifacts."""

import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    runtime = ROOT / "data" / ("advanced-browser-" + uuid.uuid4().hex[:8])
    runtime.mkdir(parents=True)
    env = {
        **os.environ,
        "BUILDTRUST_DATA_DIR": str(runtime),
        "BUILDTRUST_LLM_PROVIDER": "none",
        "BUILDTRUST_DEMO_MODE": "true",
        "BUILDTRUST_SERPAPI_KEY": "",
        "BUILDTRUST_DATAFORSEO_LOGIN": "",
        "BUILDTRUST_DATAFORSEO_PASSWORD": "",
        "BUILDTRUST_E2E_BASE_URL": "http://127.0.0.1:8010",
        "BUILDTRUST_E2E_CREDENTIALS": str(runtime / "demo-credentials.json"),
        "BUILDTRUST_E2E_OUTPUT": str(runtime / "screenshots"),
    }
    subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=ROOT / "backend",
        env=env,
        check=True,
        capture_output=True,
    )
    with (runtime / "server.log").open("w", encoding="utf-8") as log:
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
                "8010",
            ],
            cwd=ROOT / "backend",
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(
                        "Browser test server could not start; see "
                        + str(runtime / "server.log")
                    )
                try:
                    if httpx.get(
                        env["BUILDTRUST_E2E_BASE_URL"] + "/api/v1/health"
                    ).is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.15)
            npm = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm, "run", "test:e2e"],
                cwd=ROOT / "frontend",
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout + result.stderr
            (runtime / "browser-tests.log").write_text(output, encoding="utf-8")
            print(output)
            print("Actual browser artifacts:", runtime)
            if result.returncode:
                raise SystemExit(result.returncode)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
