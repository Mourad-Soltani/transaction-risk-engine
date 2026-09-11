"""Health and root endpoint tests.

Author: Mourad.Soltani
"""


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["project"] == "Transaction Risk Assessment Engine"
    assert data["author"] == "Mourad.Soltani"
    assert data["signature"] == "Mourad.Soltani"
    assert data["version"] == "1.0.0"


def test_root_lists_endpoints(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.get_json()
    assert data["signature"] == "Mourad.Soltani"
    assert "/api/assess" in data["endpoints"]
    assert "/api/screen" in data["endpoints"]
    assert data["project"] == "Transaction Risk Assessment Engine"


def test_unknown_api_route_returns_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    data = r.get_json()
    assert data is not None
    assert data["error"] == "not_found"
    assert data["signature"] == "Mourad.Soltani"
