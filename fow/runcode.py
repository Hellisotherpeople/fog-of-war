"""A short code for a battlefield, so the same ground can be fought again (or by someone else).

The code carries the seed and the choices that made the opening, plus a checksum against typos.  It is
Crockford base32: no I, L, O or U, so a code can be read out over a radio and written down correctly.
"""
from __future__ import annotations

import base64
import hashlib
import json

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIX = "FOW-"
FIELDS = ("seed", "theatre", "nation", "role", "setup")


def _b32(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = []
    while n:
        n, r = divmod(n, 32)
        out.append(ALPHABET[r])
    return "".join(reversed(out)) or "0"


def _unb32(text: str) -> bytes:
    n = 0
    for ch in text:
        n = n * 32 + ALPHABET.index(ch)
    return n.to_bytes((n.bit_length() + 7) // 8, "big")


def _clean(code: str) -> str:
    c = code.upper().strip()
    if c.startswith(PREFIX):
        c = c[len(PREFIX):]
    return "".join(ch for ch in c if ch in ALPHABET)


def make(seed: int, theatre: str, nation: str, role: str | None, setup: dict | None) -> str:
    payload = dict(seed=int(seed), theatre=theatre, nation=nation, role=role,
                   setup={k: v for k, v in (setup or {}).items()
                          if k in ("scenario", "battlefield", "reality_radius", "difficulty",
                                   "difficulty_custom", "service", "unit", "rank", "name", "traits",
                                   "kit", "fair", "vehicle", "station", "captured_vehicle")})
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    check = hashlib.sha256(raw).digest()[:2]
    body = _b32(b"\x01" + raw + check)          # (the leading byte keeps the encoding's first bits)
    return PREFIX + "-".join(body[i:i + 5] for i in range(0, len(body), 5))


def parse(code: str) -> dict | None:
    try:
        raw = _unb32(_clean(code))
        if raw[:1] == b"\x01":
            raw = raw[1:]
        body, check = raw[:-2], raw[-2:]
        if hashlib.sha256(body).digest()[:2] != check:
            return None
        d = json.loads(body)
    except (ValueError, KeyError, IndexError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(d, dict) or "seed" not in d or "theatre" not in d or "nation" not in d:
        return None
    return d


def looks_like(code: str) -> bool:
    return code.upper().strip().startswith(PREFIX) and len(_clean(code)) > 8
