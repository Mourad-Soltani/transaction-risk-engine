"""HTTP surface tests.

Author: Mourad.Soltani
"""


def test_assess_endpoint_clean(client):
    payload = {
        "transaction": {
            "id": "T1", "amount": 100, "timestamp": 1_000_000,
            "direction": "debit", "country": "US", "counterparty": "Nobody",
        }
    }
    r = client.post("/api/assess", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["signature"] == "Mourad.Soltani"
    assert data["result"]["tier"] == "LOW"
    assert data["result"]["score"] == 0


def test_assess_endpoint_sanctions(client):
    payload = {
        "transaction": {
            "id": "T1", "amount": 100, "timestamp": 1_000_000,
            "direction": "debit", "country": "US",
            "counterparty": "Sanctioned Entity",
        },
        "watchlist": ["Sanctioned Entity"],
    }
    r = client.post("/api/assess", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["signature"] == "Mourad.Soltani"
    assert data["result"]["tier"] == "CRITICAL"
    assert data["result"]["score"] == 80
    assert data["result"]["alert"] is True


def test_assess_endpoint_bad_json(client):
    r = client.post("/api/assess", data="not json", content_type="application/json")
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] == "invalid_json"
    assert data["signature"] == "Mourad.Soltani"


def test_assess_endpoint_transaction_not_object(client):
    r = client.post("/api/assess", json={"transaction": "string"})
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] == "invalid_payload"
    assert data["signature"] == "Mourad.Soltani"


def test_assess_endpoint_bad_field_type(client):
    payload = {"transaction": {"amount": "ten thousand", "timestamp": 1}}
    r = client.post("/api/assess", json=payload)
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] == "invalid_payload"
    assert "amount" in data["message"]
    assert data["signature"] == "Mourad.Soltani"


def test_screen_endpoint_happy(client):
    payload = {"name": "Acme Corporation", "watchlist": ["Acme Corp", "Globex"]}
    r = client.post("/api/screen", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["signature"] == "Mourad.Soltani"
    result = data["result"]
    assert result["normalized_name"] == "acme"
    assert result["matches"] == ["Acme Corp"]
