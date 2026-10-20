"""Explicit public demo profile. Ordinary setup still uses private random passwords."""

import argparse
import json
import socket
from pathlib import Path

from sqlalchemy import select

from .config import ROOT, Settings
from .database import make_engine, transaction
from .migrations import migrate
from .models import User
from .security import passwords

MARKER = {"application": "BuildTrust AI", "profile": "public-demo", "version": 1}


class PublicDemoSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Public examples use only explicit inputs and app defaults. A private .env
        # must not alter the reserve, expiry, workers, parser limits or paid keys.
        return (init_settings,)


def load_accounts():
    return json.loads((ROOT / "demo/public-accounts.json").read_text(encoding="utf-8"))[
        "accounts"
    ]


def validate_profile(directory, require_marker=False):
    path = Path(directory).resolve()
    if path == (ROOT / "data").resolve() or path.name != "public-demo":
        raise ValueError(
            "Use the separate public-demo folder, not the working data folder."
        )
    marker = path / "public-demo-profile.json"
    if marker.exists():
        try:
            valid = json.loads(marker.read_text(encoding="utf-8")) == MARKER
        except (ValueError, OSError):
            valid = False
        if not valid:
            raise ValueError(
                "This folder has a different profile. Nothing was overwritten."
            )
    elif require_marker or (path.exists() and any(path.iterdir())):
        raise ValueError(
            "This folder is not an empty public demo. Nothing was overwritten."
        )
    return path


def profile_settings(directory):
    return PublicDemoSettings(
        data_dir=Path(directory).resolve(),
        demo_mode=True,
        llm_provider="none",
        serpapi_key="",
        dataforseo_login="",
        dataforseo_password="",
        ocr_enabled=False,
        trusted_origins=['http://127.0.0.1:8003','http://localhost:8003'],
    )


def validate_accounts(session):
    users = list(session.scalars(select(User)))
    if not users:
        return
    expected = {a["email"]: a for a in load_accounts()}
    if {u.email for u in users} != set(expected):
        raise ValueError(
            "Public demo accounts conflict with existing accounts. Nothing was reset."
        )
    for user in users:
        account = expected[user.email]
        if (
            not user.active
            or user.role != account["role"]
            or not passwords.verify(account["password"], user.password_hash)
        ):
            raise ValueError(
                "A public demo account was changed. Existing accounts were not overwritten."
            )


def prepare_public_demo(directory=None):
    from .seed import seed

    directory = validate_profile(directory or ROOT / "data/public-demo")
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / "public-demo-profile.json"
    if not marker.exists():
        try:
            with marker.open("x", encoding="utf-8") as output:
                json.dump(MARKER, output)
        except FileExistsError:
            validate_profile(directory, require_marker=True)
    settings = profile_settings(directory)
    settings.prepare()
    engine = make_engine(directory / "buildtrust.db")
    try:
        migrate(engine)
        with transaction(engine) as session:
            validate_accounts(session)
        with transaction(engine, write=True) as session:
            result = seed(session, settings, public_demo=True)
        with transaction(engine) as session:
            validate_accounts(session)
        return settings, result
    finally:
        engine.dispose()


def check_port(port):
    if not 1024 <= port <= 65535 or port == 8000:
        raise ValueError("Choose a separate local demo port. The default is 8003.")
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    except OSError as exc:
        raise ValueError(
            f"Port {port} is already in use. Close that demo and try again."
        ) from exc


def main():
    # Running with -m creates a __main__ module. Use the canonical factory so
    # the server's trusted profile type has one identity in both launch paths.
    from .public_demo import prepare_public_demo as prepare_profile
    parser = argparse.ArgumentParser(
        description="Start the public fictional demo, separate from your working app"
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()
    try:
        if not args.prepare_only:
            check_port(args.port)
        settings, _ = prepare_profile()
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Public demo could not start: {exc}\n")
    if args.prepare_only:
        print("Public demo is ready. Your working database was not used.")
        return
    import uvicorn
    from .main import create_app
    settings.trusted_origins=[f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}']

    print(f"Public fictional demo: http://127.0.0.1:{args.port}", flush=True)
    print(
        "Use the four public passwords in README.md. No real money is connected.",
        flush=True,
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
