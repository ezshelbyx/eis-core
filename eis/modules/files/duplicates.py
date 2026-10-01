"""Duplicate-file finder (hash-based) with protected-directory guard."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from eis.core.paths import record_command
from eis.core.safety import get_safety_engine
from eis.core.utils import format_bytes
from eis.modules.files.hashing import hash_file

log = logging.getLogger(__name__)


def find_duplicates(
    roots: list[str | Path],
    min_size: int = 4096,
    confirm_delete: bool = False,
    delete_mode: str = "none",
) -> dict:
    """Find duplicate files by content hash.

    Stages: size -> partial hash (64 KB) -> full hash.  Never scans protected
    system directories unless the safety engine allows it.

    ``delete_mode``: "none" (report only), "keep_first" (delete later dupes).
    Deletion requires ``confirm_delete=True``.
    """
    engine = get_safety_engine()
    scan_roots: list[Path] = []
    blocked = []
    for r in roots:
        root = Path(r)
        ok, reason = engine.guard_scan_root(root)
        if ok:
            scan_roots.append(root)
        else:
            blocked.append({"root": str(root), "reason": reason})

    # Stage 1: group by size
    by_size: dict[int, list[Path]] = defaultdict(list)
    scanned = 0
    for root in scan_roots:
        try:
            for item in root.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    size = item.stat().st_size
                except OSError:
                    continue
                if size >= min_size:
                    by_size[size].append(item)
                scanned += 1
        except OSError as exc:
            blocked.append({"root": str(root), "reason": str(exc)})

    candidates = {s: files for s, files in by_size.items() if len(files) > 1}

    # Stage 2: partial hash (first 64 KB)
    partial_groups: dict[tuple[int, bytes], list[Path]] = defaultdict(list)
    for size, files in candidates.items():
        for f in files:
            digest = _partial_hash(f)
            partial_groups[(size, digest)].append(f)

    # Stage 3: full hash on remaining candidates
    duplicate_groups: list[list[Path]] = []
    wasted = 0
    for _key, files in partial_groups.items():
        if len(files) < 2:
            continue
        full_groups: dict[str, list[Path]] = defaultdict(list)
        for f in files:
            res = hash_file(f, ("md5",))
            if res["ok"]:
                full_groups[res["hashes"]["md5"]].append(f)
        for group in full_groups.values():
            if len(group) > 1:
                duplicate_groups.append(sorted(group))
                wasted += group[0].stat().st_size * (len(group) - 1)

    deleted = []
    delete_errors = []
    if delete_mode == "keep_first" and confirm_delete:
        for group in duplicate_groups:
            keeper = group[0]
            for dupe in group[1:]:
                try:
                    dupe.unlink()
                    deleted.append(str(dupe))
                except OSError as exc:
                    delete_errors.append(f"{dupe}: {exc}")
        record_command("files.duplicates_delete", command=", ".join(str(r) for r in roots),
                       result="ok" if not delete_errors else "error",
                       details={"deleted": len(deleted)})

    return {
        "ok": True,
        "scanned_files": scanned,
        "duplicate_groups": len(duplicate_groups),
        "wasted_bytes": wasted,
        "wasted_human": format_bytes(wasted),
        "groups": [
            {
                "hash_key": str(group[0].name),
                "size": group[0].stat().st_size,
                "files": [str(f) for f in group],
            }
            for group in duplicate_groups[:200]
        ],
        "blocked_roots": blocked,
        "deleted": deleted,
        "delete_errors": delete_errors,
    }


def _partial_hash(path: Path, chunk: int = 65536) -> bytes:
    import hashlib

    h = hashlib.md5()  # noqa: S324 - collision-resistance not needed for pre-filter
    try:
        with path.open("rb") as fh:
            h.update(fh.read(chunk))
    except OSError:
        pass
    return h.digest()
