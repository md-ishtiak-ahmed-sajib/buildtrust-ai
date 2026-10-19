from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
import time
import json
from .diagnostics import log


def make_engine(path: Path):
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA journal_mode=WAL")

    @event.listens_for(engine, "begin")
    def begin(connection):
        started = time.monotonic()
        connection.exec_driver_sql(
            "BEGIN IMMEDIATE"
            if connection.get_execution_options().get("write")
            else "BEGIN"
        )
        elapsed = round((time.monotonic() - started) * 1000)
        if elapsed >= 50:
            log.info(
                json.dumps(
                    {
                        "event": "sqlite_lock_wait",
                        "duration_ms": elapsed,
                        "write": bool(connection.get_execution_options().get("write")),
                    }
                )
            )

    return engine


@contextmanager
def transaction(engine, write=False):
    with engine.connect().execution_options(write=write) as connection:
        with Session(connection, expire_on_commit=False) as session:
            with session.begin():
                yield session
