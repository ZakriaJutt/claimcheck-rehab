"""Time-based one-time codes (RFC 6238, HMAC-SHA-1, 6 digits, 30-second step, one step either side) and
the AES-256-GCM box for stored secrets (ASVS 6.5.1, 6.5.5, 11.3.x). Recovery codes: 120 bits each, stored
as SHA-256 (single use is enforced in the database function)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1
RECOVERY_CODES = 10
_AAD = b"claimcheck-totp-v1"


def new_secret() -> bytes:
    return secrets.token_bytes(20)


def b32(secret: bytes) -> str:
    return base64.b32encode(secret).decode().rstrip("=")


def otpauth_uri(secret: bytes, account: str, issuer: str = "ClaimCheck Rehab") -> str:
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={b32(secret)}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def code_at(secret: bytes, step: int, digits: int = DIGITS) -> str:
    mac = hmac.new(secret, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def match_step(secret: bytes, code: str, now: float | None = None, last_used_step: int | None = None) -> int | None:
    """The time step the code belongs to, within one step either side; never a step already used."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    base = current_step(now)
    for step in (base, base - WINDOW, base + WINDOW):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


class SecretBox:
    def __init__(self, key_b64: str) -> None:
        self._aead = AESGCM(base64.b64decode(key_b64))

    def seal(self, secret: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return nonce + self._aead.encrypt(nonce, secret, _AAD)

    def open(self, sealed: bytes) -> bytes:
        return self._aead.decrypt(sealed[:12], sealed[12:], _AAD)


_RC_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 32 symbols, no 0/O or 1/I


def new_recovery_codes(n: int = RECOVERY_CODES) -> list[str]:
    codes = []
    for _ in range(n):
        raw = "".join(secrets.choice(_RC_ALPHABET) for _ in range(24))  # 24 x 5 bits = 120 bits
        codes.append("-".join(raw[i:i + 4] for i in range(0, 24, 4)))
    return codes


def recovery_hash(code: str) -> str:
    norm = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(norm.encode()).hexdigest()
