async def test_login_rate_limit_blocks_after_threshold(client):
    """The login endpoint is limited to 10/minute (spec §30). This test
    owns a fresh limiter state (see conftest.py's per-test reset) so it
    can assert the exact threshold without interference from other tests'
    login calls sharing the same in-memory limiter storage."""
    responses = []
    for _ in range(12):
        res = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        responses.append(res.status_code)

    # First 10 should be processed normally (401, since credentials are
    # wrong - the point is they're not blocked by the rate limiter yet).
    assert all(code == 401 for code in responses[:10])
    # 11th and 12th should be rate-limited.
    assert responses[10] == 429
    assert responses[11] == 429
