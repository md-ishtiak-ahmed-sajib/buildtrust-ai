"""Reproducible synthetic local workload; never uses the demonstration database."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid
import re
import hashlib
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def percentile(values, fraction):
    ordered = sorted(values)
    return (
        round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3)
        if ordered
        else None
    )


def summary(values):
    return {
        "count": len(values),
        "median_ms": round(statistics.median(values), 3) if values else None,
        "p95_ms": percentile(values, 0.95),
        "max_ms": round(max(values), 3) if values else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    if args.serve:
        from app.main import create_app
        from sqlalchemy import event
        import uvicorn

        app = create_app()

        @event.listens_for(app.state.engine, "before_cursor_execute")
        def before(conn, cursor, statement, parameters, context, executemany):
            context.load_started = time.perf_counter()

        @event.listens_for(app.state.engine, "after_cursor_execute")
        def after(conn, cursor, statement, parameters, context, executemany):
            table = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-z_]+)", statement, re.I)
            print(
                json.dumps(
                    {
                        "event": "load_sql",
                        "operation": statement.split()[0],
                        "table": table.group(1) if table else "transaction",
                        "duration_ms": (time.perf_counter() - context.load_started)
                        * 1000,
                    }
                ),
                flush=True,
            )

        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
        return
    from app.main import create_app
    from app.config import Settings
    from app.database import transaction
    from app.seed import seed
    from app import models as m, advanced_models as a, audit
    from app.money import canonical, digest, utcnow
    from sqlalchemy import select, func, insert

    runtime = ROOT / "data" / ("load-check-" + uuid.uuid4().hex[:8])
    runtime.mkdir(parents=True)
    app = create_app(Settings(data_dir=runtime, background_jobs=False))
    with transaction(app.state.engine, True) as session:
        seed(session, app.state.settings, test_password="Synthetic-Load-Password-2026!")
    with transaction(app.state.engine, True) as session:
        project = session.scalar(select(m.Project).where(m.Project.active.is_(True)))
        actor = session.scalar(select(m.User).where(m.User.role == "OPERATOR"))
        invoice = session.scalar(
            select(m.Invoice).where(m.Invoice.project_id == project.id)
        )
        template = {
            col.name: getattr(invoice, col.name)
            for col in m.Invoice.__table__.columns
            if col.name != "id"
        }
        existing = session.scalar(select(func.count()).select_from(m.Invoice))
        session.execute(
            insert(m.Invoice),
            [
                {
                    **template,
                    "number": f"SYNTHETIC-LOAD-{i}",
                    "status": "PENDING_REVIEW",
                }
                for i in range(2000 - existing)
            ],
        )
        session.execute(
            insert(a.Estimate),
            [
                {
                    "project_id": project.id,
                    "estimate_key": f"LOAD-{i}",
                    "revision": 1,
                    "name": f"Synthetic estimate {i}",
                    "fields_json": '{"lines":[]}',
                    "calculated_json": '{"lines":[],"total":"0.00"}',
                    "total_minor": 0,
                    "prepared_by": actor.id,
                }
                for i in range(500)
            ],
        )
        material = a.Material(
            project_id=project.id,
            name="Synthetic workload material",
            category="LOAD",
            unit="kg",
            specification_json="{}",
            created_by=actor.id,
        )
        session.add(material)
        session.flush()
        session.execute(
            insert(a.Quotation),
            [
                {
                    "project_id": project.id,
                    "material_id": material.id,
                    "prepared_by": actor.id,
                    "fields_json": canonical(
                        {
                            "material_id": material.id,
                            "supplier": f"Synthetic supplier {i}",
                            "title": "Synthetic workload quotation",
                        }
                    ),
                }
                for i in range(10000)
            ],
        )
        previous = session.scalar(
            select(m.AuditEvent).order_by(m.AuditEvent.id.desc()).limit(1)
        )
        count = session.scalar(select(func.count()).select_from(m.AuditEvent))
        identity = previous.id
        head = previous.event_hash
        rows = []
        for i in range(50000 - count):
            identity += 1
            row = {
                "id": identity,
                "project_id": project.id,
                "actor_id": None,
                "actor_name": "Synthetic load generator",
                "role": "SYSTEM",
                "event_type": "SYNTHETIC_LOAD_FIXTURE",
                "entity_type": "load_fixture",
                "entity_id": str(i),
                "details_json": '{"synthetic":true}',
                "previous_hash": head,
                "created_at": utcnow(),
            }
            payload = {k: v for k, v in row.items() if k != "details_json"}
            payload["details"] = {"synthetic": True}
            row["event_hash"] = digest(payload)
            head = row["event_hash"]
            rows.append(row)
        session.execute(insert(m.AuditEvent), rows)
        project_id = project.id
    with transaction(app.state.engine) as session:
        integrity = audit.verify(session)
        assert integrity["valid"]
        counts = {
            name: session.scalar(select(func.count()).select_from(cls))
            for name, cls in [
                ("invoices", m.Invoice),
                ("estimates", a.Estimate),
                ("quotations", a.Quotation),
                ("audit_events", m.AuditEvent),
            ]
        }
    app.state.engine.dispose()
    env = {
        **os.environ,
        "BUILDTRUST_DATA_DIR": str(runtime),
        "BUILDTRUST_BACKGROUND_JOBS": "false",
        "BUILDTRUST_LLM_PROVIDER": "none",
    }
    with (runtime / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, __file__, "--serve", "--port", str(args.port)],
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            base = f"http://127.0.0.1:{args.port}/api/v1"
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Load server failed; inspect its private log")
                try:
                    if httpx.get(base + "/health").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.15)
            with httpx.Client(base_url=base, timeout=60) as client:
                login = client.post(
                    "/auth/login",
                    json={
                        "email": "operator@buildtrust.demo",
                        "password": "Synthetic-Load-Password-2026!",
                    },
                )
                login.raise_for_status()
                headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            runs = []
            for run in range(3):

                def worker(index):
                    samples = []
                    with httpx.Client(
                        base_url=base, headers=headers, timeout=60
                    ) as client:
                        for n in range(30):
                            started = time.perf_counter()
                            if n % 6 == 5:
                                response = client.post(
                                    "/controls",
                                    json={
                                        "project_id": project_id,
                                        "name": f"Load draft {run}-{index}-{n}",
                                        "payload": {
                                            "kind": "OBLIGATION",
                                            "direction": "OUTFLOW",
                                            "category": "OTHER",
                                            "amount": "1",
                                            "evidence": "Synthetic write contention measurement only",
                                        },
                                    },
                                )
                            else:
                                kind = [
                                    "invoices",
                                    "estimates",
                                    "quotations",
                                    "audit",
                                    "controls",
                                ][n % 6]
                                response = client.get(
                                    f"/registers/{kind}",
                                    params={
                                        "project_id": project_id,
                                        "offset": n * 20,
                                        "q": "SYNTHETIC" if n % 3 == 0 else "",
                                    },
                                )
                            samples.append(
                                {
                                    "ms": (time.perf_counter() - started) * 1000,
                                    "status": response.status_code,
                                    "write": n % 6 == 5,
                                }
                            )
                    return samples

                started = time.perf_counter()
                with ThreadPoolExecutor(max_workers=10) as pool:
                    samples = [v for rows in pool.map(worker, range(10)) for v in rows]
                runs.append(
                    {
                        "run": run + 1,
                        "clients": 10,
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "reads": summary([v["ms"] for v in samples if not v["write"]]),
                        "writes": summary([v["ms"] for v in samples if v["write"]]),
                        "errors": [v for v in samples if v["status"] not in (200, 201)],
                    }
                )
                assert not runs[-1]["errors"], runs[-1]["errors"]
        finally:
            server.terminate()
            server.wait(timeout=15)
    events = []
    for line in (
        (runtime / "server.log")
        .read_text(encoding="utf-8", errors="replace")
        .splitlines()
    ):
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    queries = [v["duration_ms"] for v in events if v.get("event") == "load_sql"]
    locks = [v["duration_ms"] for v in events if v.get("event") == "sqlite_lock_wait"]
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": counts,
        "runs": runs,
        "sql": summary(queries),
        "sql_by_table": {
            table: summary(
                [
                    v["duration_ms"]
                    for v in events
                    if v.get("event") == "load_sql" and v.get("table") == table
                ]
            )
            for table in sorted(
                {
                    v.get("table", "unknown")
                    for v in events
                    if v.get("event") == "load_sql"
                }
            )
        },
        "lock_waits_at_least_50ms": summary(locks),
        "audit_integrity_before_load": integrity,
        "runtime": str(runtime),
        "limitations": "Synthetic local Windows workload, three runs on this device; no production-capacity inference. Lock events are logged only at >=50ms.",
    }
    result["source_files"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("backend/app", "backend/alembic")
        for p in sorted((ROOT / folder).rglob("*.py"))
        if "__pycache__" not in p.parts
    }
    (runtime / "measurements.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (ROOT / "data" / "latest-load-check.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
