from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlite3
from datetime import datetime, timezone
import uuid


def migrate(engine):
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    # SQLite online backup includes committed WAL data. Never copy only the .db file.
    database = Path(engine.url.database)
    if database.exists():
        with sqlite3.connect(database) as source:
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            ).fetchone()
            version = (
                source.execute("SELECT version_num FROM alembic_version").fetchone()
                if exists
                else None
            )
            if version and version[0] != head:
                backup_dir = database.parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                name = (
                    "pre-advanced-"
                    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    + "-"
                    + uuid.uuid4().hex[:6]
                    + ".db"
                )
                with sqlite3.connect(backup_dir / name) as dest:
                    source.backup(dest)
                    if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Migration backup integrity check failed")
    rebuild = head >= "0008" and (
        not database.exists() or not version or version[0] < "0008"
        or (head >= "0013" and version[0] < "0013")
    )
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        if rebuild:
            raw.execute("PRAGMA foreign_keys=OFF")
        try:
            with connection.begin():
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                    raise RuntimeError(
                        "Migration foreign-key validation failed; restore the pre-migration backup"
                    )
        finally:
            if rebuild:
                raw.execute("PRAGMA foreign_keys=ON")
