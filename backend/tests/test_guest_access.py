"""Signed guest-access tokens: what makes a token valid, and what it can't be used for.
Pure unit tests - no database or web framework needed."""

import time
from datetime import timedelta

from app.core import guest_access as ga

SECRET = "unit-test-secret-value"


def test_a_fresh_token_verifies_to_its_own_record():
    token = ga.sign_token("application", "abc-123", SECRET)
    assert ga.verify_token(token, SECRET) == ("application", "abc-123")


def test_a_token_is_bound_to_one_record_and_one_kind():
    token = ga.sign_token("application", "abc-123", SECRET)
    grants = ga.grants_from_header(token, SECRET)
    assert ("application", "abc-123") in grants
    assert ("application", "other-id") not in grants
    assert ("financing", "abc-123") not in grants


def test_a_tampered_token_is_rejected():
    body, sig = ga.sign_token("application", "abc-123", SECRET).split(".")
    forged = ga.sign_token("application", "victim-id", SECRET).split(".")[0] + "." + sig
    assert ga.verify_token(forged, SECRET) is None
    assert ga.verify_token(body + ".AAAA", SECRET) is None
    assert ga.verify_token("not-a-token", SECRET) is None
    assert ga.verify_token("", SECRET) is None


def test_a_token_signed_with_another_secret_is_rejected():
    token = ga.sign_token("application", "abc-123", "some-other-secret")
    assert ga.verify_token(token, SECRET) is None


def test_an_expired_token_is_rejected():
    long_ago = time.time() - 3 * 86400
    token = ga.sign_token("application", "abc-123", SECRET, now=long_ago, ttl=timedelta(days=1))
    assert ga.verify_token(token, SECRET) is None


def test_several_tokens_in_one_header_are_all_honoured_but_capped():
    tokens = [ga.sign_token("application", f"id-{i}", SECRET) for i in range(20)]
    grants = ga.grants_from_header(",".join(tokens), SECRET)
    assert len(grants) == ga.MAX_TOKENS_PER_REQUEST
    assert ga.grants_from_header(None, SECRET) == set()


def test_a_guest_token_is_not_a_login_token():
    """The signing key is derived, so the raw JWT secret can't be used to forge one."""
    import base64, hashlib, hmac, json

    body = base64.urlsafe_b64encode(json.dumps({"k": "application", "r": "x", "e": int(time.time()) + 999}).encode()).rstrip(b"=").decode()
    raw_sig = base64.urlsafe_b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert ga.verify_token(f"{body}.{raw_sig}", SECRET) is None
