"""Restrict only application-owned runtime trees, never the project checkout."""
import csv
import os
from pathlib import Path
import stat
import subprocess
from functools import lru_cache


def managed_paths(root):
    names = {"uploads", "backups", "signing-secret", "mfa-encryption-key", "demo-credentials.json", "public-demo-profile.json", "buildtrust.db", "buildtrust.db-wal", "buildtrust.db-shm"}
    return [p for p in Path(root).iterdir() if p.name in names]


def reject_links(root):
    root = Path(root)
    entries = [root]
    for p in managed_paths(root):
        entries.append(p)
        if p.is_dir() and not p.is_symlink():
            entries.extend(p.rglob("*"))
    for entry in entries:
        if entry.is_symlink() or (os.name == "nt" and entry.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("Private storage must not contain symbolic links or reparse points")


@lru_cache(maxsize=1)
def windows_sid():
    result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return next(csv.reader([result.stdout.strip()]))[1]


def protect_file(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Linked private files are not supported")
    if os.name == "nt":
        _set_windows_acl(str(path.resolve()), path.stat().st_ino, False)
    else:
        path.chmod(0o600)


@lru_cache(maxsize=8192)
def _set_windows_acl(path, inode, inherit):
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = api.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    apply = api.SetFileSecurityW
    apply.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    apply.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    flags = "OICI" if inherit else ""
    sddl = "D:P" + "".join(f"(A;{flags};FA;;;{sid})" for sid in (windows_sid(), "SY", "BA"))
    descriptor = ctypes.c_void_p()
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # This supported low-level operation deliberately does not propagate to
        # unrelated developer/tool trees. We explicitly secure managed paths.
        if not apply(path, 0x80000004, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def protect_runtime(directory):
    directory = Path(directory)
    reject_links(directory)
    if os.name == "nt":
        _set_windows_acl(str(directory.resolve()), directory.stat().st_ino, False)
        for path in managed_paths(directory):
            entries = [path, *path.rglob("*")] if path.is_dir() else [path]
            for item in entries:
                _set_windows_acl(str(item.resolve()), item.stat().st_ino, item.is_dir())
    else:
        paths = [directory]
        for p in managed_paths(directory):
            paths.extend([p, *p.rglob("*")] if p.is_dir() else [p])
        for path in paths:
            path.chmod(0o700 if path.is_dir() else 0o600)


def private_path(directory, *parts):
    root = Path(directory).resolve()
    if any(Path(part).is_absolute() or ".." in Path(part).parts for part in parts):
        raise ValueError("Private storage paths cannot be absolute or contain parent traversal")
    candidate = root.joinpath(*parts)
    # Check lexical parents before resolving so symlinks cannot hide an escape.
    for part in [candidate, *candidate.parents]:
        if part == root.parent:
            break
        if part.is_symlink() or (part.exists() and os.name == "nt" and part.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("Linked private files are unavailable")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Private storage path is outside its root")
    return resolved
