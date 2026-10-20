"""Local-owner recovery and private, source-consistent backup/restore tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from sqlalchemy import select
from .config import Settings
from .database import make_engine, transaction
from .models import User
from .auth_api import issue_recovery
from .private_storage import protect_runtime, protect_file, private_path
from .money import utcnow


def backup(settings, output):
    settings.prepare()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Backup destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.data_dir / "buildtrust.db")
    try:
        with tempfile.TemporaryDirectory() as stage:
            protect_runtime(Path(stage))
            database = Path(stage) / "buildtrust.db"
            with transaction(engine, True):
                with closing(sqlite3.connect(settings.data_dir / "buildtrust.db")) as source, closing(sqlite3.connect(database)) as destination:
                    source.backup(destination)
                    assert destination.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    names = {r[0] for r in destination.execute("SELECT storage_name FROM documents WHERE storage_name IS NOT NULL")}
                    names.update(r[0] for r in destination.execute("SELECT storage_name FROM supplier_quotations WHERE storage_name IS NOT NULL"))
                files = {"buildtrust.db": database}
                for name in names:
                    if name:
                        files["uploads/"+name] = private_path(settings.data_dir, "uploads", name)
                for name in ("signing-secret", "public-demo-profile.json", "demo-credentials.json"):
                    file = private_path(settings.data_dir, name)
                    if file.is_file():
                        files[name] = file
                manifest = {"application":"BuildTrust AI", "format":1, "created_at":utcnow(),
                            "simulation":True, "config_identifiers":["BDT", "Asia/Dhaka", "local-owner"],
                            "files":{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}}
                # Create the private file before writing any database or secrets.
                descriptor = os.open(output, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
                os.close(descriptor)
                protect_file(output)
                with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
                    for name,p in files.items():archive.write(p,name)
                    archive.writestr("private-manifest.json",json.dumps(manifest,indent=2))
            return {"passed":True,"files":len(files),"archive_sha256":hashlib.sha256(output.read_bytes()).hexdigest()}
    finally:
        engine.dispose()


def restore(archive, target):
    target = Path(target).absolute()
    if target.is_symlink() or (target.exists() and any(target.iterdir())):
        raise ValueError("Restore requires a new or empty isolated directory")
    target.mkdir(parents=True,exist_ok=True)
    protect_runtime(target)
    with zipfile.ZipFile(archive) as source:
        infos=source.infolist()
        if len(infos)>10000 or sum(i.file_size for i in infos)>500*1024*1024:
            raise ValueError("Backup exceeds restore limits")
        if len({i.filename for i in infos})!=len(infos):raise ValueError("Duplicate backup members")
        manifest=json.loads(source.read("private-manifest.json"))
        if manifest.get("application")!="BuildTrust AI" or manifest.get("format")!=1:
            raise ValueError("Unknown backup format")
        if set(source.namelist())!={*manifest["files"],"private-manifest.json"}:
            raise ValueError("Backup manifest does not cover its members")
        for name,sha in manifest["files"].items():
            path=private_path(target,name)
            if Path(name).is_absolute() or ".." in Path(name).parts:raise ValueError("Unsafe backup member")
            data=source.read(name)
            if hashlib.sha256(data).hexdigest()!=sha:raise ValueError("Backup checksum mismatch")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data);protect_file(path)
    protect_runtime(target)
    with closing(sqlite3.connect(target/"buildtrust.db")) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Restored database failed integrity checks")
    from .audit import verify
    engine=make_engine(target/"buildtrust.db")
    try:
        from .migrations import migrate
        migrate(engine)
        with transaction(engine) as session:
            if not verify(session)["valid"]:raise ValueError("Restored audit chain is invalid")
        from .hardening_models import AuthSession, RecoveryToken
        from . import audit
        with transaction(engine, True) as session:
            for row in session.scalars(select(AuthSession).where(AuthSession.revoked_at.is_(None))):row.revoked_at=utcnow()
            for row in session.scalars(select(RecoveryToken).where(RecoveryToken.consumed_at.is_(None))):row.consumed_at=utcnow()
            audit.append(session,None,"BACKUP_RESTORED","system","local-owner",{"sessions_revoked":True})
    finally:engine.dispose()
    return {"passed":True,"files":len(manifest["files"]),"audit_valid":True,"copied_sessions_revoked":True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    b=sub.add_parser("backup");b.add_argument("--output",required=True,type=Path)
    r=sub.add_parser("restore");r.add_argument("--archive",required=True,type=Path);r.add_argument("--target",required=True,type=Path)
    p=sub.add_parser("recover");p.add_argument("--email",required=True)
    args=parser.parse_args()
    if args.command=="restore":result=restore(args.archive,args.target)
    else:
        settings=Settings();settings.prepare()
        if args.command=="backup":result=backup(settings,args.output)
        else:
            if not sys.stdout.isatty():raise SystemExit("Recovery token must be shown in an interactive private terminal, not redirected to a log.")
            if (settings.data_dir/"public-demo-profile.json").exists():raise SystemExit("Public demo passwords remain fixed.")
            engine=make_engine(settings.data_dir/"buildtrust.db")
            try:
                with transaction(engine,True) as session:
                    user=session.scalar(select(User).where(User.email==args.email.strip().lower()))
                    if not user:raise SystemExit("Account not found")
                    result=issue_recovery(session,settings,user,owner=True)
            finally:engine.dispose()
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
