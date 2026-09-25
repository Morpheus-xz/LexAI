"""Security-header and CORS behaviour tests."""


def test_security_headers_on_get(client):
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_security_headers_on_post(client, mock_gemini):
    mock_gemini.return_value = {"ai_summary": "Security header check summary."}
    resp = client.post(
        "/analyze",
        json={"text": "Unique text used only for the security header POST test case."},
    )
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_hsts_header_present(client):
    resp = client.get("/health")
    assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]


def test_permissions_policy_present(client):
    resp = client.get("/health")
    assert resp.headers["Permissions-Policy"] == "geolocation=(), microphone=()"


def test_security_headers_on_404(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_cors_credentials_false(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-credentials") != "true"
