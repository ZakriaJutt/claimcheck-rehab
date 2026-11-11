"""Password policy and storage (TRD Identity and tenancy; ASVS 6.2.1, 6.2.4, 6.2.9, 11.4.2).

Minimum 8 characters (15 recommended in the screen copy), at most 128, no composition rules, refused when
on the common-password list or equal to the email address. Stored with argon2id (argon2-cffi defaults).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 8
MAX_LENGTH = 128
_hasher = PasswordHasher()
# Verified when the email is unknown, so a missing account costs the same time as a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password-used-for-timing-only")


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    lines = (Path(__file__).with_name("common_passwords.txt")).read_text().splitlines()
    return frozenset(x.strip().lower() for x in lines if x.strip() and not x.startswith("#"))


def policy_problem(password: str, email: str | None = None) -> str | None:
    """None when acceptable; otherwise a code from a fixed list."""
    if len(password) < MIN_LENGTH:
        return "too_short"
    if len(password) > MAX_LENGTH:
        return "too_long"
    low = password.lower()
    if low in common_passwords():
        return "too_common"
    if email and low == email.lower():
        return "same_as_email"
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
