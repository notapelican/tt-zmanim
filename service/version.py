"""Engine version stamp.

The WordPress plugin stores this with each generated Timesheet so it can tell
"reprint the stored snapshot" (byte-identical to what was approved) apart from
"regenerate with the current engine" (may differ after an engine change).

The stamp is ``<git-short-hash>-<engine-source-hash>``. The git hash is a
convenience (absent in a source-only Docker image); the source hash is the part
that actually detects a change to the halachic logic — it is a digest of every
``engine/*.py`` file, so any edit to the engine changes the stamp.
"""
from __future__ import annotations

import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENGINE_DIR = _REPO_ROOT / "engine"


def _git_short_hash() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or "nogit"
    except Exception:
        return "nogit"


def _engine_source_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(_ENGINE_DIR.glob("*.py")):
        h.update(p.name.encode())
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


@lru_cache(maxsize=1)
def engine_version() -> str:
    return f"{_git_short_hash()}-{_engine_source_hash()}"
