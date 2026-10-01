"""Troubleshooting knowledge base engine: search, match, feedback, custom entries."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from eis.core.logging_config import KB_CUSTOM_PATH
from eis.core.paths import record_command
from eis.core.settings import get_settings
from eis.modules.knowledge.kb_data import ENTRIES

log = logging.getLogger(__name__)

CATEGORIES = ("Hardware", "Performance", "Network", "Storage", "Android",
              "Security", "System repair", "Peripherals", "General")
SEVERITIES = ("low", "medium", "high", "critical")


def _custom_entries() -> list[dict]:
    path = Path(KB_CUSTOM_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("custom KB unreadable: %s", exc)
        return []


def all_entries() -> list[dict]:
    """Built-in pack merged with user's custom entries."""
    return list(ENTRIES) + _custom_entries()


def _entry_text(entry: dict) -> str:
    return " ".join(
        [
            entry.get("title", ""),
            entry.get("category", ""),
            *entry.get("symptoms", []),
            *entry.get("error_patterns", []),
            *entry.get("causes", []),
        ]
    ).lower()


def search(query: str, category: str = "", limit: int | None = None) -> list[dict]:
    """Rank entries against a free-text query (word overlap scoring)."""
    settings = get_settings()
    limit = limit or int(settings.get("tools.kb_search_limit", 40))
    query = (query or "").strip().lower()
    entries = all_entries()
    if category:
        entries = [e for e in entries if e.get("category") == category]
    if not query:
        return entries[:limit]

    terms = re.findall(r"[a-z0-9_]+", query)
    scored = []
    for entry in entries:
        text = _entry_text(entry)
        patterns = " ".join(entry.get("error_patterns", [])).lower()
        score = 0
        for term in terms:
            if term in text:
                score += 2
            if term in patterns:
                score += 3
        # Exact error-pattern hits dominate
        for pattern in entry.get("error_patterns", []):
            if pattern.lower() in query:
                score += 10
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for score, entry in scored[:limit]:
        enriched = dict(entry)
        enriched["relevance"] = score
        results.append(enriched)
    return results


def match_error_text(text: str) -> list[dict]:
    """Scan a log/message block and return entries whose error_patterns hit."""
    text = (text or "").lower()
    hits = []
    for entry in all_entries():
        matched = [p for p in entry.get("error_patterns", []) if p.lower() in text]
        if matched:
            enriched = dict(entry)
            enriched["matched_patterns"] = matched
            hits.append(enriched)
    hits.sort(key=lambda e: len(e["matched_patterns"]), reverse=True)
    return hits


def get_entry(entry_id: str) -> dict | None:
    for entry in all_entries():
        if entry.get("id") == entry_id:
            return entry
    return None


def categories_present() -> list[str]:
    seen = []
    for entry in all_entries():
        cat = entry.get("category", "General")
        if cat not in seen:
            seen.append(cat)
    return seen


# ---------------------------------------------------------------------------
# Custom entries (JSON persisted)
# ---------------------------------------------------------------------------

def add_custom_entry(title: str, category: str, symptoms: list[str], causes: list[str],
                     diagnostics: list[str], solutions: list[str],
                     error_patterns: list[str] | None = None,
                     severity: str = "medium", entry_id: str | None = None) -> dict:
    entry = {
        "id": entry_id or f"custom-{int(Path(KB_CUSTOM_PATH).stat().st_size if Path(KB_CUSTOM_PATH).exists() else 0)+1:03d}",
        "title": title.strip(),
        "category": category if category in CATEGORIES else "General",
        "os": "Any",
        "severity": severity if severity in SEVERITIES else "medium",
        "symptoms": symptoms,
        "error_patterns": error_patterns or [],
        "causes": causes,
        "diagnostics": diagnostics,
        "solutions": solutions,
        "references": [],
        "custom": True,
    }
    entries = _custom_entries()
    entries.append(entry)
    _save_custom(entries)
    record_command("knowledge.entry_added", command=title, result="ok", details={"id": entry["id"]})
    return entry


def delete_custom_entry(entry_id: str) -> bool:
    entries = _custom_entries()
    remaining = [e for e in entries if e.get("id") != entry_id]
    if len(remaining) != len(entries):
        _save_custom(remaining)
        return True
    return False


def _save_custom(entries: list[dict]) -> None:
    KB_CUSTOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(KB_CUSTOM_PATH).with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(KB_CUSTOM_PATH)


def export_entries(path: Path | str, fmt: str = "json") -> dict:
    """Export the merged KB (built-in + custom) for sharing."""
    entries = all_entries()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        target.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt == "md":
        lines = ["# E.I.S. Core Troubleshooting Knowledge Base", ""]
        for e in entries:
            lines += [f"## {e['title']}", f"*Category:* {e.get('category')} | *Severity:* {e.get('severity')}",
                      "", "**Symptoms:**", *[f"- {s}" for s in e.get("symptoms", [])], "",
                      "**Causes:**", *[f"- {c}" for c in e.get("causes", [])], "",
                      "**Diagnostics:**", *[f"- {d}" for d in e.get("diagnostics", [])], "",
                      "**Solutions:**", *[f"- {s}" for s in e.get("solutions", [])], ""]
        target.write_text("\n".join(lines), encoding="utf-8")
    else:
        return {"ok": False, "error": f"Unsupported format: {fmt}"}
    return {"ok": True, "path": str(target), "entries": len(entries)}
