"""Signed "guest access" tokens.

A guest (someone getting a quote and buying without an account) has no login, so
the only thing that used to protect their application, payment or financing record
was knowing its id. These tokens fix that: when the server creates an application
or a financing application it also hands the browser a signed token for THAT
record only, and every later call for it must present the token.

- Tokens are bound to one record ("application" / "financing" + its id), so
  holding one never opens anyone else's record - not even another record of the
  same customer.
- They are signed (HMAC-SHA256) with a key derived from JWT_SECRET_KEY and expire.
- The browser sends them back in the X-Guest-Token header (comma-separated when it
  holds several). The frontend stores and sends them automatically (lib/api.ts).

This module is deliberately standard-library only (no web-framework imports in the
signing/verifying part) so it is easy to test on its own.
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta

GUEST_HEADER = "X-Guest-Token"
GUEST_TOKEN_TTL = timedelta(days=14)
MAX_TOKENS_PER_REQUEST = 12

_DOMAIN = b"somosure-guest-access-v1"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key(secret: str) -> bytes:
    # Derived (not the raw JWT secret) so a guest token can never be replayed as, or
    # confused with, a login token.
    return hmac.new(secret.encode(), _DOMAIN, hashlib.sha256).digest()


def sign_token(kind: str, resource_id: str, secret: str, *, now: float | None = None, ttl: timedelta = GUEST_TOKEN_TTL) -> str:
    issued = time.time() if now is None else now
    body = _b64(json.dumps({"k": kind, "r": str(resource_id), "e": int(issued + ttl.total_seconds())}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_key(secret), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str, secret: str, *, now: float | None = None) -> tuple[str, str] | None:
    """(kind, resource_id) for a valid, unexpired token; None for anything else."""
    try:
        body, sig = token.strip().split(".", 1)
        expected = _b64(hmac.new(_key(secret), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(body))
        if int(data["e"]) < (time.time() if now is None else now):
            return None
        return str(data["k"]), str(data["r"])
    except Exception:
        return None


def grants_from_header(header_value: str | None, secret: str, *, now: float | None = None) -> set[tuple[str, str]]:
    """Every valid (kind, resource_id) grant carried by an X-Guest-Token header."""
    if not header_value:
        return set()
    found: set[tuple[str, str]] = set()
    for part in header_value.split(",")[:MAX_TOKENS_PER_REQUEST]:
        grant = verify_token(part, secret, now=now)
        if grant:
            found.add(grant)
    return found


# ------------------------------------------------------------- app wiring


def issue_token(kind: str, resource_id) -> str:
    from app.core.config import get_settings

    return sign_token(kind, str(resource_id), get_settings().jwt_secret_key)


def has_grant(request, kind: str, resource_id) -> bool:
    from app.core.config import get_settings

    grants = grants_from_header(request.headers.get(GUEST_HEADER), get_settings().jwt_secret_key)
    return (kind, str(resource_id)) in grants
