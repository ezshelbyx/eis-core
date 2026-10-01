"""File hashing: MD5, SHA-1, SHA-256, SHA-512 with streaming and verification."""

from __future__ import annotations

import hashlib
import hmac
import logging
from pathlib import Path

log = logging.getLogger(__name__)

ALGORITHMS = ("md5", "sha1", "sha256", "sha512")
CHUNK = 1 << 20  # 1 MiB


def hash_file(path: str | Path, algorithms: tuple[str, ...] = ("sha256",)) -> dict:
    """Hash one file with one or more algorithms (streamed, low memory)."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    algos = [a.lower().replace("-", "") for a in algorithms]
    for algo in algos:
        if algo not in ALGORITHMS:
            return {"ok": False, "error": f"Unsupported algorithm: {algo}"}
    digests = {a: hashlib.new(a) for a in algos}
    try:
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK), b""):
                for d in digests.values():
                    d.update(chunk)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "file": str(p),
        "size": p.stat().st_size,
        "hashes": {a: d.hexdigest() for a, d in digests.items()},
    }


def hash_text(text: str, algorithm: str = "sha256") -> dict:
    algo = algorithm.lower().replace("-", "")
    if algo not in ALGORITHMS:
        return {"ok": False, "error": f"Unsupported algorithm: {algorithm}"}
    return {"ok": True, "algorithm": algo, "hash": hashlib.new(algo, text.encode("utf-8")).hexdigest()}


def verify_file(path: str | Path, expected: str, algorithm: str = "sha256") -> dict:
    """Compare a file's hash against an expected digest (constant-time compare)."""
    result = hash_file(path, (algorithm,))
    if not result["ok"]:
        return result
    actual = result["hashes"][algorithm.lower().replace("-", "")]
    expected_clean = expected.strip().lower().replace(" ", "")
    match = hmac.compare_digest(actual, expected_clean)
    return {
        "ok": True,
        "file": result["file"],
        "algorithm": algorithm,
        "expected": expected_clean,
        "actual": actual,
        "match": match,
        "verdict": "MATCH - file integrity verified" if match else "MISMATCH - file differs from expected hash",
    }


def hash_directory(path: str | Path, algorithm: str = "sha256", max_files: int = 2000) -> dict:
    """Hash every file in a folder (non-recursive by default is recursive here; capped)."""
    root = Path(path)
    if not root.is_dir():
        return {"ok": False, "error": f"Folder not found: {root}"}
    results = []
    errors = []
    count = 0
    for item in sorted(root.rglob("*")):
        if item.is_file():
            r = hash_file(item, (algorithm,))
            if r["ok"]:
                results.append({"file": str(item.relative_to(root)), "hash": r["hashes"][algorithm]})
            else:
                errors.append(str(item))
            count += 1
            if count >= max_files:
                break
    return {"ok": True, "algorithm": algorithm, "root": str(root),
            "files": results, "error_count": len(errors), "errors": errors[:20]}
