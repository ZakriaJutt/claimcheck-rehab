"""One typed settings object, read from the environment and validated at start (R-06, UT-14)."""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", case_sensitive=False)

    app_env: Literal["local", "test", "staging", "production"]
    database_url: str = Field(min_length=1)
    public_base_url: str = Field(min_length=1)
    api_port: int = 8107
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "America/Vancouver"
    session_cookie_name: str = "cc_session"
    session_idle_minutes: int = 30
    job_lease_seconds: int = 120

    # B2 sign-in (TRD Identity and tenancy). The key encrypts TOTP secrets (AES-256-GCM, base64 of 32 bytes).
    totp_encryption_key: str = Field(min_length=40)
    session_absolute_minutes: int = 720
    mfa_pending_minutes: int = 5
    invite_hours: int = 72
    reset_minutes: int = 30
    cookie_secure: bool = True
    rate_window_seconds: int = 900
    rate_signin_per_account: int = 5
    rate_signin_per_ip: int = 30
    rate_mfa_per_user: int = 5
    rate_reset_per_account: int = 3
    rate_public_per_ip: int = 30
    # S08: proxies whose X-Forwarded-For is believed (comma-separated addresses or CIDR ranges). Empty: the
    # client address is always the direct TCP peer. The server's own proxy-header trust must be off
    # (uvicorn --no-proxy-headers; FORWARDED_ALLOW_IPS empty), so the peer reaching the app is the real one.
    trusted_proxies: str = ""

    # B2 email: SMTP only (Mailpit locally, a real provider later by settings alone).
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_from: str = "ClaimCheck Rehab <no-reply@claimcheck.test>"
    smtp_starttls: bool = False
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_timeout_seconds: float = 10.0
    # C2 (CASL s. 6(2), CRTC Regulations SOR/2012-36 s. 2(1)): every message names the sender and gives a
    # mailing address and an email or web address valid for 60 days. Required in staging and production.
    mail_sender_name: str = "ClaimCheck Rehab"
    mail_postal_address: str = ""
    mail_contact: str = ""

    # B2 object store (AD-11): S3 API (MinIO locally). Credentials optional: production uses the instance role.
    s3_bucket: str = Field(min_length=3)
    s3_region: str = "ca-central-1"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_server_side_encryption: Literal["AES256", "aws:kms"] | None = None

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("must be a postgresql URL")
        return v

    @field_validator("public_base_url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("must be an absolute http(s) URL")
        return v.rstrip("/")


    @field_validator("trusted_proxies")
    @classmethod
    def _networks(cls, v: str) -> str:
        import ipaddress
        for part in (p.strip() for p in v.split(",")):
            if part:
                ipaddress.ip_network(part, strict=False)  # ValueError names the setting
        return v

    @field_validator("totp_encryption_key")
    @classmethod
    def _key_32_bytes(cls, v: str) -> str:
        import base64
        import binascii
        try:
            raw = base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("must be base64") from None
        if len(raw) != 32:
            raise ValueError("must decode to 32 bytes")
        return v

    @model_validator(mode="after")
    def _production_rules(self) -> Settings:
        # R-16: links in email come only from PUBLIC_BASE_URL, which must be public HTTPS in production.
        if self.app_env in ("staging", "production"):
            if not self.public_base_url.startswith("https://") or "localhost" in self.public_base_url \
                    or "127.0.0.1" in self.public_base_url:
                raise ValueError("public_base_url must be a public https URL")
            if not self.cookie_secure:
                raise ValueError("cookie_secure must be true")
            if self.s3_server_side_encryption is None:
                raise ValueError("s3_server_side_encryption is required")
            if not self.mail_postal_address.strip() or not self.mail_contact.strip():
                raise ValueError("mail_postal_address and mail_contact are required (CASL)")
        return self


class SettingsError(SystemExit):
    """Raised at start when a setting is missing or malformed; names the variable, never its value."""


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        names = sorted({str(err["loc"][0]).upper() if err.get("loc") else "PUBLIC_BASE_URL, COOKIE_SECURE, "
                        "S3_SERVER_SIDE_ENCRYPTION, MAIL_POSTAL_ADDRESS or MAIL_CONTACT" for err in exc.errors()})
        msg = "configuration error: missing or invalid setting(s): " + ", ".join(names)
        print(msg, file=sys.stderr)
        raise SettingsError(2) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
