from app.models import KIND_SALE
from app.services import (
    STATUS_CRITICAL,
    STATUS_OK,
    STATUS_WARNING,
    build_state,
    platform_status,
    register_transaction,
)


def test_umbrales_de_abastecimiento():
    assert platform_status(500, 50, 150) == STATUS_OK
    assert platform_status(151, 50, 150) == STATUS_OK
    assert platform_status(150, 50, 150) == STATUS_WARNING
    assert platform_status(51, 50, 150) == STATUS_WARNING
    assert platform_status(50, 50, 150) == STATUS_CRITICAL
    assert platform_status(0, 50, 150) == STATUS_CRITICAL
    assert platform_status(-10, 50, 150) == STATUS_CRITICAL


def test_venta_puede_llevar_plataforma_a_nivel_critico(db, carlos, ecuabet, efectivo):
    register_transaction(
        db, kind=KIND_SALE, amount=360.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, account_id=efectivo.id,
    )
    state = build_state(db)
    ecuabet_state = next(p for p in state["platforms"] if p["name"] == "Ecuabet")
    assert ecuabet_state["balance"] == 140.0
    assert ecuabet_state["status"] == STATUS_WARNING

    register_transaction(
        db, kind=KIND_SALE, amount=100.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, account_id=efectivo.id,
    )
    state = build_state(db)
    ecuabet_state = next(p for p in state["platforms"] if p["name"] == "Ecuabet")
    assert ecuabet_state["status"] == STATUS_CRITICAL
