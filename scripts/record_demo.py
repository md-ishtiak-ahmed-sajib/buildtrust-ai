"""Record a freshly seeded private demonstration; never reset the working database."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import hashlib
import httpx
from verification_client import VerificationClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8013)
    args = parser.parse_args()
    if args.port == 8000:
        raise SystemExit(
            "Use a dedicated recording port; 8000 belongs to the working application."
        )
    runtime = ROOT / "data" / ("recording-" + uuid.uuid4().hex[:8])
    runtime.mkdir(parents=True)
    base = f"http://127.0.0.1:{args.port}"
    env = {
        **os.environ,
        "BUILDTRUST_DATA_DIR": str(runtime),
        "BUILDTRUST_LLM_PROVIDER": "none",
        "BUILDTRUST_SERPAPI_KEY": "",
        "BUILDTRUST_DATAFORSEO_LOGIN": "",
        "BUILDTRUST_DATAFORSEO_PASSWORD": "",
        "BUILDTRUST_RECORDING_BASE_URL": base,
        "BUILDTRUST_TRUSTED_ORIGINS": json.dumps([base]),
        "BUILDTRUST_RECORDING_RUNTIME": str(runtime),
    }
    subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=ROOT / "backend",
        env=env,
        check=True,
        capture_output=True,
    )
    marker = {
        "purpose": "isolated-recording",
        "base_url": base,
        "database": str(runtime / "buildtrust.db"),
    }
    paths = []
    for folder in ("backend/app", "backend/alembic", "frontend/src"):
        paths.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix in (".py", ".tsx", ".ts", ".css")
        )
    paths.extend(
        ROOT / name
        for name in (
            "backend/pyproject.toml",
            "backend/uv.lock",
            "frontend/package.json",
            "frontend/package-lock.json",
        )
    )
    marker["app_source_files"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }
    marker["app_source_fingerprint"] = hashlib.sha256(
        json.dumps(marker["app_source_files"], sort_keys=True).encode()
    ).hexdigest()
    (runtime / "recording-runtime.json").write_text(
        json.dumps(marker), encoding="utf-8"
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
                str(args.port),
            ],
            cwd=ROOT / "backend",
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Dedicated recording server failed")
                try:
                    if httpx.get(base + "/api/v1/health").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.15)
            # Enroll only this isolated fixture before recording. The browser
            # still performs its visible real second-factor sign-in below.
            credentials=json.loads((runtime/'demo-credentials.json').read_text())
            with VerificationClient(base_url=base,timeout=30) as verifier:
                for role in ('admin','manager'):
                    email=role+'@buildtrust.demo'
                    verifier.post('/api/v1/auth/login',json={'email':email,'password':credentials[email]}).raise_for_status()
                cache=runtime/'mfa-testing-credentials.json'
                cache.write_text(json.dumps(verifier.mfa_cache))
                sys.path.insert(0,str(ROOT/'backend'))
                from app.private_storage import protect_file
                protect_file(cache)
            subprocess.run(
                ["node", str(ROOT / "scripts/record_demo.mjs")],
                cwd=ROOT,
                env=env,
                check=True,
            )
        finally:
            server.terminate()
            server.wait(timeout=15)
    print("Private recording database:", runtime)


if __name__ == "__main__":
    main()
