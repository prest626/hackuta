def test_contracts_placeholder():
    assert True


def test_health():
    from fastapi.testclient import TestClient

    from api.main import app

    res = TestClient(app).get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
