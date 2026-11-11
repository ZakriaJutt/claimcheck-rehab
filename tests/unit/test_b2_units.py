"""B2 unit tests: TOTP (RFC 6238 vectors, window, replay), secret box, recovery codes, password policy,
object keys and clinic binding, email links, production settings rules."""

from __future__ import annotations

import uuid

import pytest

from claimcheck_core.auth import passwords, totp
from claimcheck_core.mail import invite_mail, reset_mail
from claimcheck_core.storage import ClinicObjects, MemoryBlobStore, object_key
from tests.unit.test_foundation import _run

RFC_SECRET = b"12345678901234567890"


@pytest.mark.parametrize(("t", "code8"), [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
                                          (1234567890, "89005924"), (2000000000, "69279037")])
def test_totp_rfc6238_sha1_vectors(t: int, code8: str) -> None:
    step = totp.current_step(t)
    assert totp.code_at(RFC_SECRET, step, digits=8) == code8
    assert totp.code_at(RFC_SECRET, step) == code8[-6:]


def test_totp_window_and_replay() -> None:
    now = 1_800_000_000.0
    step = totp.current_step(now)
    assert totp.match_step(RFC_SECRET, totp.code_at(RFC_SECRET, step), now) == step
    assert totp.match_step(RFC_SECRET, totp.code_at(RFC_SECRET, step - 1), now) == step - 1
    assert totp.match_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + 1), now) == step + 1
    assert totp.match_step(RFC_SECRET, totp.code_at(RFC_SECRET, step - 2), now) is None  # outside the window
    # a step already used is never accepted again
    assert totp.match_step(RFC_SECRET, totp.code_at(RFC_SECRET, step), now, last_used_step=step) is None
    assert totp.match_step(RFC_SECRET, "12345", now) is None
    assert totp.match_step(RFC_SECRET, "abcdef", now) is None


def test_secret_box_round_trip_and_tamper() -> None:
    from cryptography.exceptions import InvalidTag
    box = totp.SecretBox("dGVzdC1vbmx5LXRvdHAta2V5LTMyLWJ5dGVzLWxvbmc=")
    sealed = box.seal(RFC_SECRET)
    assert RFC_SECRET not in sealed and box.open(sealed) == RFC_SECRET
    assert box.seal(RFC_SECRET) != sealed  # fresh nonce
    with pytest.raises(InvalidTag):
        box.open(sealed[:-1] + bytes([sealed[-1] ^ 1]))


def test_recovery_codes() -> None:
    codes = totp.new_recovery_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(c.replace("-", "")) == 24 for c in codes)  # 24 symbols of 5 bits = 120 bits
    assert totp.recovery_hash(codes[0]) == totp.recovery_hash(codes[0].lower().replace("-", " "))


def test_password_policy_and_hashing() -> None:
    assert passwords.policy_problem("short7!") == "too_short"
    assert passwords.policy_problem("password123") == "too_common"
    assert passwords.policy_problem("PassWord123") == "too_common"
    assert passwords.policy_problem("a" * 129) == "too_long"
    assert passwords.policy_problem("x" * 64) is None  # long passwords allowed, no composition rule
    assert passwords.policy_problem("ab@example.test", "AB@example.test") == "same_as_email"
    assert passwords.policy_problem("tidal-heron-kettle") is None
    assert len(passwords.common_passwords()) >= 100
    h = passwords.hash_password("tidal-heron-kettle")
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "tidal-heron-kettle")
    assert not passwords.verify_password(h, "tidal-heron-kettlf")
    assert not passwords.verify_password(None, "anything")


def test_object_keys_isolate_clinic_source_and_purpose() -> None:
    a, b, obj = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert object_key(a, "jane_export", "import_payload", obj) == f"clinic/{a}/jane_export/import_payload/{obj}.json"
    with pytest.raises(ValueError):
        object_key(a, "jane_export", "raw_file", obj)
    with pytest.raises(ValueError):
        object_key(a, "../other", "import_payload", obj)
    with pytest.raises(TypeError):
        object_key(a, "jane_export", "import_payload", "../x")  # type: ignore[arg-type]
    store = MemoryBlobStore()
    ka = ClinicObjects(store, a).put("jane_export", "import_payload", obj, b"{}")
    kb = ClinicObjects(store, b).put("jane_export", "import_payload", obj, b"{}")
    assert ka != kb
    with pytest.raises(PermissionError):
        ClinicObjects(store, b).get(ka)
    with pytest.raises(PermissionError):
        ClinicObjects(store, b).delete(ka)
    assert ClinicObjects(store, a).delete_all() == 1
    assert list(store.objects) == [kb]


def test_email_links_use_public_base_url_and_carry_no_row_data() -> None:
    m = invite_mail("staff@example.test", "tok_abcdefghijklmnopqrstuvwxyz", 72)
    assert "http://localhost:3107/invite#token=tok_abcdefghijklmnopqrstuvwxyz" in m.body
    r = reset_mail("staff@example.test", "tok_abcdefghijklmnopqrstuvwxyz", 30)
    assert "/reset#token=" in r.body and "authenticator code" in r.body
    for text in (m.body, r.body):
        assert "invoice" not in text.lower() and "$" not in text


def test_production_settings_refuse_local_links_and_plain_storage() -> None:
    env = {"APP_ENV": "production", "DATABASE_URL": "postgresql://x@localhost/none",
           "PUBLIC_BASE_URL": "http://localhost:3107", "S3_BUCKET": "claimcheck-prod",
           "TOTP_ENCRYPTION_KEY": "dGVzdC1vbmx5LXRvdHAta2V5LTMyLWJ5dGVzLWxvbmc="}
    r = _run("from claimcheck_core.settings import load_settings; load_settings()", env)
    assert r.returncode == 2 and "PUBLIC_BASE_URL" in r.stderr
    ok = {**env, "PUBLIC_BASE_URL": "https://app.claimcheck.example", "S3_SERVER_SIDE_ENCRYPTION": "aws:kms"}
    r = _run("from claimcheck_core.settings import load_settings; load_settings(); print('ok')", ok)
    assert r.returncode == 0, r.stderr
    r = _run("from claimcheck_core.settings import load_settings; load_settings()",
             {**ok, "TOTP_ENCRYPTION_KEY": "c2hvcnQ="})
    assert r.returncode == 2 and "TOTP_ENCRYPTION_KEY" in r.stderr


def test_payload_purge_has_no_latest_batch_exception_and_removes_orphans() -> None:
    """B2-S02 at unit level: objects older than 24 hours and orphans older than an hour go; the store
    binding refuses a key with a `..` segment."""
    from datetime import UTC, datetime, timedelta

    from claimcheck_core.payloads import sweep_expired_objects
    store = MemoryBlobStore()
    a = uuid.uuid4()
    k_old = ClinicObjects(store, a).put("jane_export", "import_payload", uuid.uuid4(), b"{}")
    k_new = ClinicObjects(store, a).put("jane_export", "import_payload", uuid.uuid4(), b"{}")
    store.modified[k_old] -= timedelta(hours=25)
    assert sweep_expired_objects(store, datetime.now(tz=UTC)) == 1
    assert list(store.objects) == [k_new]
    with pytest.raises(PermissionError):
        ClinicObjects(store, a).get(f"clinic/{a}/../{uuid.uuid4()}/jane_export/import_payload/x.json")


def test_s08_client_address_trusts_only_configured_proxies() -> None:
    from claimcheck_api.deps import client_address
    # untrusted peer: X-Forwarded-For is ignored entirely
    assert client_address("198.51.100.9", ["203.0.113.1"], "") == "198.51.100.9"
    assert client_address("198.51.100.9", ["203.0.113.1"], "10.0.0.0/8") == "198.51.100.9"
    # trusted peer: the right-most hop that is not a trusted proxy; hops to its left are the client's
    assert client_address("10.0.0.5", ["1.2.3.4, 203.0.113.7"], "10.0.0.0/8") == "203.0.113.7"
    assert client_address("10.0.0.5", ["1.2.3.4, 203.0.113.7, 10.0.0.9"], "10.0.0.0/8") == "203.0.113.7"
    assert client_address("10.0.0.5", ["1.2.3.4", "203.0.113.7"], "10.0.0.0/8") == "203.0.113.7"
    assert client_address("10.0.0.5", [], "10.0.0.0/8") == "10.0.0.5"
    assert client_address("10.0.0.5", ["not-an-ip"], "10.0.0.0/8") == "not-an-ip"
    assert client_address(None, ["1.2.3.4"], "") == "unknown"


def test_s08_server_proxy_header_trust_is_off_in_the_start_command() -> None:
    from tests.conftest import ROOT
    dev = (ROOT / "scripts/dev.sh").read_text()
    assert "--no-proxy-headers" in dev and 'FORWARDED_ALLOW_IPS=""' in dev
    example = (ROOT / ".env.example").read_text()
    assert "TRUSTED_PROXIES=" in example and "FORWARDED_ALLOW_IPS=" in example
