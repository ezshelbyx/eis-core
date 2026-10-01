"""Generators: secure passwords/passphrases and QR payload builders.

QR rendering happens in the UI via an HTML template (no third-party Python QR
library needed on low-end machines); this module builds the payload strings.
"""

from __future__ import annotations

import logging
import secrets
import string

log = logging.getLogger(__name__)

CHARSETS = {
    "lower": string.ascii_lowercase,
    "upper": string.ascii_uppercase,
    "digits": string.digits,
    "symbols": "!@#$%^&*()-_=+[]{};:,.?/",
}
AMBIGUOUS = set("O0oIl1|`'\";:.,")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def generate_password(
    length: int = 20,
    use_lower: bool = True,
    use_upper: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = True,
) -> dict:
    """Cryptographically secure random password (``secrets`` module)."""
    if length < 4 or length > 256:
        return {"ok": False, "error": "Length must be between 4 and 256."}
    pool = ""
    required = []
    if use_lower:
        pool += CHARSETS["lower"]
        required.append(CHARSETS["lower"])
    if use_upper:
        pool += CHARSETS["upper"]
        required.append(CHARSETS["upper"])
    if use_digits:
        pool += CHARSETS["digits"]
        required.append(CHARSETS["digits"])
    if use_symbols:
        pool += CHARSETS["symbols"]
        required.append(CHARSETS["symbols"])
    if not pool:
        return {"ok": False, "error": "Select at least one character set."}
    if exclude_ambiguous:
        pool = "".join(c for c in pool if c not in AMBIGUOUS)
        required = ["".join(c for c in group if c not in AMBIGUOUS) for group in required]
        required = [g for g in required if g]

    if len(pool) < 4:
        return {"ok": False, "error": "Character pool too small after exclusions."}

    # Guarantee at least one char from each selected set, then fill randomly.
    chars = [secrets.choice(group) for group in required]
    while len(chars) < length:
        chars.append(secrets.choice(pool))
    # Shuffle without bias using secrets-based Fisher-Yates
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    entropy = _entropy_bits(length, len(pool))
    return {
        "ok": True,
        "password": "".join(chars),
        "length": length,
        "entropy_bits": entropy,
        "strength": _strength_word(entropy),
    }


def generate_passphrase(words: int = 4, separator: str = "-", capitalize: bool = True, add_digit: bool = True) -> dict:
    """Diceware-style passphrase using a built-in word list (offline)."""
    if not (2 <= words <= 12):
        return {"ok": False, "error": "Word count must be between 2 and 12."}
    from eis.modules.files.wordlist import WORDS

    picked = [secrets.choice(WORDS) for _ in range(words)]
    if capitalize:
        picked = [w.capitalize() for w in picked]
    phrase = separator.join(picked)
    if add_digit:
        phrase += separator + str(secrets.randbelow(90) + 10)
    entropy = _entropy_bits(words, len(WORDS))
    return {"ok": True, "passphrase": phrase, "entropy_bits": entropy, "strength": _strength_word(entropy)}


def _entropy_bits(length: int, pool_size: int) -> float:
    import math

    if pool_size <= 1:
        return 0.0
    return round(length * math.log2(pool_size), 1)


def _strength_word(bits: float) -> str:
    if bits >= 100:
        return "Excellent"
    if bits >= 80:
        return "Strong"
    if bits >= 60:
        return "Good"
    if bits >= 40:
        return "Fair"
    return "Weak"


# ---------------------------------------------------------------------------
# QR payloads
# ---------------------------------------------------------------------------

def wifi_payload(ssid: str, password: str = "", encryption: str = "WPA", hidden: bool = False) -> str:
    """WIFI: QR payload (WPA/WEP/nopass)."""
    esc = lambda s: s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    auth = encryption.upper()
    parts = [f"WIFI:T:{'nopass' if auth == 'NOPASS' else 'WPA' if auth == 'WPA' else 'WEP'}",
             f"S:{esc(ssid)}"]
    if auth != "NOPASS" and password:
        parts.append(f"P:{esc(password)}")
    if hidden:
        parts.append("H:true")
    return ";".join(parts) + ";;"


def url_payload(url: str) -> str:
    url = url.strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def text_payload(text: str) -> str:
    return text


def vcard_payload(name: str, org: str = "", phone: str = "", email: str = "", note: str = "") -> str:
    """Technician contact card (vCard 3.0)."""
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
    if org:
        lines.append(f"ORG:{org}")
    if phone:
        lines.append(f"TEL;TYPE=CELL:{phone}")
    if email:
        lines.append(f"EMAIL:{email}")
    if note:
        lines.append(f"NOTE:{note}")
    lines.append("END:VCARD")
    return "\n".join(lines)
