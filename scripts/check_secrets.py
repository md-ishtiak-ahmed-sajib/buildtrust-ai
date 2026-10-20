"""Pinned, redacted history/current/build/archive scans. Never scan private runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
import io
import sys

ROOT=Path(__file__).resolve().parents[1]
VERSION="8.30.1"
PINNED = {"windows": "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
          "linux": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"}


def known_private_values():
    """Supplement patterns with exact local private values, never their output."""
    values=[]
    credentials=ROOT/"data/demo-credentials.json"
    if credentials.exists():values.extend(json.loads(credentials.read_text()).values())
    secret=ROOT/"data/signing-secret"
    if secret.exists():values.append(secret.read_text().strip())
    sys.path.insert(0,str(ROOT/"backend"))
    from app.config import Settings
    settings=Settings()
    values.extend([settings.serpapi_key,settings.dataforseo_password])
    public={v["password"] for v in json.loads((ROOT/"demo/public-accounts.json").read_text())["accounts"]}
    return [v.encode() for v in set(values) if isinstance(v,str) and len(v)>=8 and v not in public]


def contains_private(data, values, depth=0):
    if any(v in data for v in values):return True
    if depth<4 and data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist())>500*1024*1024:raise ValueError("Archive exceeds private-value scan bound")
                return any(contains_private(z.read(i),values,depth+1) for i in z.infolist() if not i.is_dir())
        except zipfile.BadZipFile:pass
    return False


def scanner():
    directory=ROOT/"data/security-tools";directory.mkdir(parents=True,exist_ok=True)
    windows=os.name=="nt"
    name=f"gitleaks_{VERSION}_{'windows' if windows else 'linux'}_x64.{'zip' if windows else 'tar.gz'}"
    binary=directory/("gitleaks.exe" if windows else "gitleaks")
    checks=directory/f"gitleaks_{VERSION}_checksums.txt"
    asset=directory/name
    base=f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/"
    for file in (checks,asset):
        if not file.exists():urllib.request.urlretrieve(base+file.name,file)
    expected=next(line.split()[0] for line in checks.read_text().splitlines() if line.split()[-1]==name)
    if expected != PINNED["windows" if windows else "linux"]:raise ValueError("Published checksum differs from pinned checksum")
    if hashlib.sha256(asset.read_bytes()).hexdigest()!=expected:raise ValueError("Scanner checksum mismatch")
    # Extract only the verified executable, with no archive-provided paths.
    if windows:
        with zipfile.ZipFile(asset) as source:binary.write_bytes(source.read("gitleaks.exe"))
    else:
        with tarfile.open(asset) as source:binary.write_bytes(source.extractfile("gitleaks").read())
        binary.chmod(0o700)
    actual=subprocess.check_output([str(binary),"version"],text=True).strip()
    if actual!=VERSION:raise ValueError("Unexpected scanner version")
    return binary,expected


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,default=ROOT/"data/security-scan");args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    binary,checksum=scanner();results=[]
    known=known_private_values();exact_matches=[]
    def run(label,command):
        report=out/(label+".json")
        result=subprocess.run([str(binary),*command,"--config",str(ROOT/".gitleaks.toml"),"--redact=100","--no-banner","--no-color","--max-archive-depth=4","--max-decode-depth=3","--report-format=json","--report-path",str(report)],cwd=ROOT,capture_output=True,text=True)
        (out/(label+".log")).write_text(result.stdout+result.stderr,encoding="utf-8")
        findings=json.loads(report.read_text()) if report.exists() else []
        results.append({"scope":label,"passed":result.returncode==0,"findings":len(findings)})
    run("all-history",["git",str(ROOT),"--log-opts=--all"])
    with tempfile.TemporaryDirectory(prefix="buildtrust-scan-") as temp:
        stage=Path(temp)
        names=subprocess.check_output(["git","ls-files","-co","--exclude-standard","-z"],cwd=ROOT).decode().split("\0")
        for name in names:
            source=ROOT/name
            if not name or not source.is_file():continue
            if name.startswith("prompt/") or Path(name).name.lower()=="agents.md":continue
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        for relative in ["frontend/dist","frontend/public"]:
            source=ROOT/relative
            if source.exists():shutil.copytree(source,stage/relative,dirs_exist_ok=True)
        unsafe=[p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file() and ((p.name.startswith(".env") and p.name!=".env.example") or p.name=="signing-secret" or "credentials" in p.name.lower())]
        if unsafe:raise ValueError("Private filenames in public source: "+", ".join(unsafe))
        if known:
            exact_matches.extend(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file() and contains_private(p.read_bytes(),known))
        run("current-build-and-archives",["dir",str(stage)])
    # Git patch scans cannot inspect historical binary ZIP bodies. Scan each
    # distinct historical release archive explicitly, preserving old history.
    objects=subprocess.check_output(["git","rev-list","--objects","--all"],cwd=ROOT,text=True)
    types=subprocess.check_output(["git","cat-file","--batch-check=%(objectname) %(objecttype)"],input="\n".join(line.split(" ",1)[0] for line in objects.splitlines())+"\n",cwd=ROOT,text=True)
    blob_ids={line.split()[0] for line in types.splitlines() if line.endswith(" blob")}
    if known:
        for line in objects.splitlines():
            bits=line.split(" ",1)
            if len(bits)!=2 or bits[0] not in blob_ids:continue
            data=subprocess.check_output(["git","cat-file","blob",bits[0]],cwd=ROOT)
            if contains_private(data,known):exact_matches.append("historical-blob:"+bits[0]+":"+bits[1])
    with tempfile.TemporaryDirectory(prefix="buildtrust-history-archives-") as temp:
        stage=Path(temp);seen=set()
        for line in objects.splitlines():
            bits=line.split(" ",1)
            if len(bits)==2 and bits[1].endswith("BuildTrustAI_Source.zip") and bits[0] not in seen:
                seen.add(bits[0]);(stage/(bits[0]+".zip")).write_bytes(subprocess.check_output(["git","cat-file","blob",bits[0]],cwd=ROOT))
        run("historical-release-archives",["dir",str(stage)])
    summary={"passed":all(r["passed"] for r in results),"scanner":"Gitleaks","version":VERSION,"download_sha256":checksum,"results":results,"history_rewritten":False,"paid_credentials_rotated":False,"scope":"Pattern-based redacted scan; not proof that no undiscovered secret exists."}
    summary["known_private_values_checked"]=len(known)
    summary["known_private_value_matches"]=exact_matches
    summary["passed"] &= not exact_matches
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    if not summary["passed"]:raise SystemExit(1)


if __name__=="__main__":main()
