import pytest
from fastapi.testclient import TestClient

import app.main as app_main
from app.database import get_db
from app.main import app


@pytest.fixture()
def client(db, monkeypatch):
    monkeypatch.setattr(app_main, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def ids(state):
    return (
        next(c["id"] for c in state["collaborators"] if c["name"] == "Carlos"),
        next(p["id"] for p in state["platforms"] if p["name"] == "Ecuabet"),
        next(a["id"] for a in state["accounts"] if a["name"] == "Efectivo"),
    )


def test_estado_inicial_expone_semillas(client):
    state = client.get("/api/state").json()
    assert len(state["platforms"]) == 7
    assert len(state["accounts"]) == 8
    assert {c["name"] for c in state["collaborators"]} == {"Carlos", "Refa"}


def test_registro_de_venta_por_api(client):
    carlos_id, platform_id, account_id = ids(client.get("/api/state").json())
    client.patch(f"/api/platforms/{platform_id}/thresholds", json={"min_balance": 50, "warning_balance": 150})
    client.patch(f"/api/accounts/{account_id}/balance", json={"balance": 100})

    res = client.post(
        "/api/transactions",
        json={
            "kind": "venta",
            "amount": 25.5,
            "collaborator_id": carlos_id,
            "platform_id": platform_id,
            "account_id": account_id,
            "status": "pagada",
        },
    )
    assert res.status_code == 201

    state = client.get("/api/state").json()
    assert next(a["balance"] for a in state["accounts"] if a["id"] == account_id) == 125.5
    assert next(p["balance"] for p in state["platforms"] if p["id"] == platform_id) == -25.5


def test_error_de_negocio_devuelve_400(client):
    carlos_id, platform_id, _ = ids(client.get("/api/state").json())
    res = client.post(
        "/api/transactions",
        json={"kind": "venta", "amount": 10, "collaborator_id": carlos_id, "platform_id": platform_id, "status": "pendiente"},
    )
    assert res.status_code == 400
    assert "cliente" in res.json()["detail"].lower()


def test_nuevo_colaborador_y_turno(client):
    created = client.post("/api/collaborators", json={"name": "Ana"})
    assert created.status_code == 201
    assert client.post("/api/collaborators", json={"name": "Ana"}).status_code == 400

    toggled = client.patch(f"/api/collaborators/{created.json()['id']}", json={"active": False})
    assert toggled.json()["active"] is False


def test_export_csv(client):
    res = client.get("/api/report/csv")
    assert res.status_code == 200
    assert "ARQUEO DE CAJA" in res.text
    assert "attachment" in res.headers["content-disposition"]
    assert client.get("/api/report/csv?day=2024-13-40").status_code == 400


def test_websocket_recibe_estado_inicial_y_actualizaciones(client):
    carlos_id, platform_id, account_id = ids(client.get("/api/state").json())
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["event"] == "estado_inicial"

        client.post(
            "/api/transactions",
            json={
                "kind": "compra_cupo",
                "amount": 300,
                "collaborator_id": carlos_id,
                "platform_id": platform_id,
                "account_id": account_id,
                "status": "pagada",
            },
        )
        update = ws.receive_json()
        assert update["event"] == "transaccion_registrada"
        assert next(p["balance"] for p in update["state"]["platforms"] if p["id"] == platform_id) == 300.0
