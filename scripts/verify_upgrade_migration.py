"""Migrate a consistent private DB copy, compare legacy records and rehearse recovery."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database import make_engine
from app.migrations import migrate
from alembic.config import Config
from alembic.script import ScriptDirectory


def migration_head():
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def state(path, tables=None):
    with sqlite3.connect(path) as connection:
        tables = tables or [
            r[0]
            for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='alembic_version'"
            )
        ]
        result = {}
        for name in tables:
            columns = (
                tables[name]["columns"]
                if isinstance(tables, dict)
                else [
                    r[1]
                    for r in connection.execute(
                        'PRAGMA table_info("' + name.replace('"', '""') + '")'
                    )
                ]
            )
            column_sql = ",".join('"' + c.replace('"', '""') + '"' for c in columns)
            rows = connection.execute(
                "SELECT " + column_sql + ' FROM "' + name.replace('"', '""') + '"'
            ).fetchall()
            result[name] = {
                "columns": columns,
                "rows": len(rows),
                "sha256": hashlib.sha256(
                    json.dumps(sorted(rows, key=repr), sort_keys=True).encode()
                ).hexdigest(),
            }
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "buildtrust.db")
    original = parser.parse_args().source.resolve()
    folder = ROOT / "data" / ("migration-check-" + uuid.uuid4().hex[:8])
    folder.mkdir()
    copy, recovery = folder / "migrated.db", folder / "recovery.db"
    with (
        sqlite3.connect(original) as source,
        sqlite3.connect(copy) as dest,
        sqlite3.connect(recovery) as restore,
    ):
        source.backup(dest)
        source.backup(restore)
    before = state(copy)
    engine = make_engine(copy)
    migrate(engine)
    engine.dispose()
    after = state(copy, before)
    assert before == after, "Migration changed existing records"
    assert state(recovery, before) == before
    with sqlite3.connect(copy) as check:
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            check.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == migration_head()
        )
    result = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "legacy_tables_preserved": len(before),
        "records": before,
        "copy": str(copy),
        "recovery": str(recovery),
        "note": "Both migration and recovery operated on copies; the workspace database was preserved.",
    }
    (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"PASS: {len(before)} legacy tables unchanged; migration and recovery integrity checked. {folder}"
    )


if __name__ == "__main__":
    main()
