"""Persist data files back to GitHub so uploads survive container restarts.

Uses a GITHUB_TOKEN PAT to authenticate. If the token is absent (e.g. local
dev), every function here is a no-op. Failures are logged but never raised —
persistence must not break the upload request.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_REMOTE = "https://github.com/shraddhautmsangle04-art/ALT_Mobility_ss.git"
DEFAULT_BRANCH = "feat/api-incremental-upload"
DEFAULT_USER_NAME = "ALT Mobility Bot"
DEFAULT_USER_EMAIL = "bot@altmobility.local"

PERSIST_PATHS = [
    "data/extracted.json",
    "data/extracted.xlsx",
    "dashboard/index.html",
]


def _enabled() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN"))


def _auth_url() -> str:
    token = os.environ["GITHUB_TOKEN"]
    remote = os.environ.get("GIT_REMOTE_URL", DEFAULT_REMOTE)
    return remote.replace("https://", f"https://x-access-token:{token}@")


def _branch() -> str:
    return os.environ.get("GIT_BRANCH", DEFAULT_BRANCH)


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def _ensure_identity(repo_root: Path) -> None:
    name = os.environ.get("GIT_USER_NAME", DEFAULT_USER_NAME)
    email = os.environ.get("GIT_USER_EMAIL", DEFAULT_USER_EMAIL)
    _run(["git", "config", "user.name", name], repo_root)
    _run(["git", "config", "user.email", email], repo_root)


def commit_and_push(repo_root: Path, source_filename: str) -> None:
    """Stage data files, commit, and push to GitHub. Silent no-op without a token."""
    if not _enabled():
        return

    try:
        _ensure_identity(repo_root)

        existing = [p for p in PERSIST_PATHS if (repo_root / p).exists()]
        if not existing:
            return
        _run(["git", "add", *existing], repo_root, check=False)

        status = _run(["git", "status", "--porcelain", *existing], repo_root, check=False)
        if not status.stdout.strip():
            return  # nothing actually changed

        message = f"data: upload {source_filename} [skip render]"
        _run(["git", "commit", "-m", message], repo_root)

        auth_url = _auth_url()
        branch = _branch()

        for attempt in range(2):
            _run(["git", "fetch", auth_url, branch], repo_root, check=False)
            rebase = _run(["git", "rebase", f"FETCH_HEAD"], repo_root, check=False)
            if rebase.returncode != 0:
                _run(["git", "rebase", "--abort"], repo_root, check=False)
                # Conflict on a data file we just wrote — accept ours
                _run(["git", "merge", "FETCH_HEAD", "-X", "ours",
                      "-m", "merge: accept local data state"], repo_root, check=False)

            push = _run(["git", "push", auth_url, f"HEAD:{branch}"], repo_root, check=False)
            if push.returncode == 0:
                print(f"[git-persist] pushed {source_filename}")
                return
            print(f"[git-persist] push attempt {attempt + 1} failed: {push.stderr.strip()}")
        print("[git-persist] giving up after retries")
    except Exception as exc:
        print(f"[git-persist] unexpected error: {exc}")


def pull_latest(repo_root: Path) -> None:
    """On startup, fast-forward local repo to whatever GitHub has. Silent no-op without a token."""
    if not _enabled():
        return
    try:
        _ensure_identity(repo_root)
        auth_url = _auth_url()
        branch = _branch()
        _run(["git", "fetch", auth_url, branch], repo_root, check=False)
        # Reset committed paths to match remote — local writes since last push are discarded
        _run(["git", "checkout", "FETCH_HEAD", "--", *PERSIST_PATHS], repo_root, check=False)
        print("[git-persist] pulled latest data from GitHub")
    except Exception as exc:
        print(f"[git-persist] pull failed: {exc}")
