"""APK analyzer: package name, version, permissions, SDK info - via aapt or ZIP parsing."""

from __future__ import annotations

import logging
import re
import struct
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

DANGEROUS_PERMISSIONS = {
    "android.permission.READ_SMS": "Read SMS",
    "android.permission.SEND_SMS": "Send SMS",
    "android.permission.RECEIVE_SMS": "Receive SMS",
    "android.permission.READ_CALL_LOG": "Read call log",
    "android.permission.WRITE_CALL_LOG": "Write call log",
    "android.permission.PROCESS_OUTGOING_CALLS": "Intercept outgoing calls",
    "android.permission.CAMERA": "Camera",
    "android.permission.RECORD_AUDIO": "Microphone",
    "android.permission.ACCESS_FINE_LOCATION": "Precise location",
    "android.permission.ACCESS_COARSE_LOCATION": "Approximate location",
    "android.permission.READ_CONTACTS": "Read contacts",
    "android.permission.WRITE_CONTACTS": "Write contacts",
    "android.permission.READ_EXTERNAL_STORAGE": "Read storage",
    "android.permission.WRITE_EXTERNAL_STORAGE": "Write storage",
    "android.permission.MANAGE_EXTERNAL_STORAGE": "Manage all files",
    "android.permission.RECORD_VIDEO": "Record video",
    "android.permission.READ_PHONE_STATE": "Phone state",
    "android.permission.CALL_PHONE": "Direct dial",
    "android.permission.BODY_SENSORS": "Body sensors",
    "android.permission.SYSTEM_ALERT_WINDOW": "Draw over apps",
    "android.permission.REQUEST_INSTALL_PACKAGES": "Install packages",
    "android.permission.QUERY_ALL_PACKAGES": "List all apps",
}


def analyze(apk_path: str | Path) -> dict:
    """Analyze an APK file (AndroidManifest.axml parsed directly - no aapt needed)."""
    path = Path(apk_path)
    if not path.is_file():
        return {"ok": False, "error": f"File not found: {path}"}
    if path.suffix.lower() != ".apk":
        return {"ok": False, "error": "Not an .apk file."}

    result: dict = {"ok": True, "file": str(path), "name": path.name,
                    "size_bytes": path.stat().st_size}
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            result["entries"] = len(names)
            result["dex_files"] = [n for n in names if n.endswith(".dex")]
            if "AndroidManifest.xml" not in names:
                return {"ok": False, "error": "AndroidManifest.xml missing (not an APK?)"}
            manifest_bytes = zf.read("AndroidManifest.xml")
            info = _parse_axml(manifest_bytes)
            result.update(info)
    except zipfile.BadZipFile:
        return {"ok": False, "error": "Corrupt or unsupported file (not a valid APK)."}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    permissions = result.pop("permissions", [])
    result["permissions"] = permissions
    result["permission_count"] = len(permissions)
    result["risky_permissions"] = [
        {"name": p, "description": DANGEROUS_PERMISSIONS.get(p, "")}
        for p in permissions if p in DANGEROUS_PERMISSIONS
    ]
    return result


def _parse_axml(data: bytes) -> dict:
    """Minimal Android binary XML (AXML) parser for manifest attributes."""
    info: dict = {"permissions": [], "labels": {}}
    try:
        strings = _parse_string_pool(data) if b"\\x00" else []
    except Exception:
        strings = []

    # Walk chunk boundaries looking for START_ELEMENT (0x0102) events.
    pos = 8  # skip header of the whole AXML document
    try:
        while pos + 8 <= len(data):
            chunk_type, _header_size, size = struct.unpack_from("<HHI", data, pos)
            if chunk_type == 0x0102:  # START_ELEMENT
                attrs = _parse_start_element(data, pos, strings)
                for ns, name, raw_value in attrs:
                    if name == "uses-permission" or ns and ns.endswith("uses-permission"):
                        if raw_value:
                            info["permissions"].append(raw_value)
                    elif name == "package":
                        info["package"] = raw_value
                    elif name in ("versionCode", "versionName", "platformBuildVersionCode", "compileSdkVersion", "compileSdkVersionCodename"):
                        info[name] = raw_value
                    elif name == "targetSdkVersion":
                        info["target_sdk"] = raw_value
                    elif name == "minSdkVersion":
                        info["min_sdk"] = raw_value
            elif chunk_type == 0x0101:  # END_ELEMENT
                pass
            if size <= 0:
                break
            pos += size
    except (struct.error, MemoryError) as exc:  # pragma: no cover
        log.debug("axml parse stopped: %s", exc)
    return info


def _parse_string_pool(data: bytes) -> list[str]:
    """Extract the global string pool (best effort)."""
    strings: list[str] = []
    pos = 8
    while pos + 8 <= len(data):
        chunk_type, _hsize, size = struct.unpack_from("<HHI", data, pos)
        if chunk_type == 0x0001:  # STRING_POOL
            _typ, _hs, _sz, str_count, _style_count, _flags, strings_start, _styles_start = struct.unpack_from(
                "<IIIIIIII", data, pos + 8
            )
            utf8 = bool(_flags & (1 << 8))
            base = pos + strings_start
            offsets = struct.unpack_from(f"<{str_count}I", data, pos + 28)
            for off in offsets:
                start = base + off
                try:
                    if utf8:
                        # u16len, u8len, bytes
                        _u16len, n = _read_len(data, start)
                        text_end = start + n + 1
                        raw = data[text_end:text_end + _u16len]
                        strings.append(raw.decode("utf-8", errors="replace"))
                    else:
                        length = struct.unpack_from("<H", data, start)[0]
                        raw = data[start + 2:start + 2 + length * 2]
                        strings.append(raw.decode("utf-16-le", errors="replace"))
                except (struct.error, UnicodeDecodeError):
                    strings.append("")
            break
        if size <= 0:
            break
        pos += size
    return strings


def _read_len(data: bytes, pos: int) -> tuple[int, int]:
    high = data[pos]
    if high & 0x80:
        length = ((high & 0x7F) << 8) | data[pos + 1]
        return length, 2
    return high, 1


def _parse_start_element(data: bytes, pos: int, strings: list[str]) -> list[tuple[str, str, str]]:
    """Return [(ns, name, raw_value)] for one START_ELEMENT chunk."""
    attrs_out = []
    try:
        _line, _comment = struct.unpack_from("<II", data, pos + 8)
        ns_ref, name_ref = struct.unpack_from("<iI".replace("i", "i"), data, pos + 16)[:2]
        attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, pos + 24)
        for i in range(attr_count):
            base = pos + 36 + i * 20
            ns, name, raw, _ = struct.unpack_from("<iiiI", data, base)[:4]
            ns_str = strings[ns] if 0 <= ns < len(strings) and ns != -1 else ""
            name_str = strings[name] if 0 <= name < len(strings) else ""
            value = strings[raw] if 0 <= raw < len(strings) else ""
            attrs_out.append((ns_str, name_str, value))
    except (struct.error, IndexError):
        pass
    return attrs_out
