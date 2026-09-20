import pytest

from app.models import KIND_EXPENSE, KIND_PURCHASE, KIND_SALE, STATUS_PAID, STATUS_PENDING
from app.services import (
    BusinessError,
    daily_totals,
    register_payment,
    register_transaction,
    total_payables,
    total_receivables,
)
from datetime import date


def test_venta_pagada_descuenta_plataforma_y_suma_caja(db, carlos, ecuabet, efectivo):
    register_transaction(
        db, kind=KIND_SALE, amount=120.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, account_id=efectivo.id,
    )
    assert ecuabet.balance == 380.0
    assert efectivo.balance == 320.0
    assert total_receivables(db) == 0.0


def test_venta_a_credito_no_mueve_cuentas_y_genera_cxc(db, carlos, ecuabet, efectivo):
    register_transaction(
        db, kind=KIND_SALE, amount=75.0, collaborator_id=carlos.id, platform_id=ecuabet.id,
        status=STATUS_PENDING, client_name="Juan",
    )
    assert ecuabet.balance == 425.0
    assert efectivo.balance == 200.0
    assert total_receivables(db) == 75.0


def test_compra_cupo_contado_incrementa_plataforma_y_descuenta_banco(db, carlos, ecuabet, pichincha):
    pichincha.balance = 1000.0
    db.commit()
    register_transaction(
        db, kind=KIND_PURCHASE, amount=300.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, account_id=pichincha.id,
    )
    assert ecuabet.balance == 800.0
    assert pichincha.balance == 700.0
    assert total_payables(db) == 0.0


def test_compra_cupo_a_credito_genera_deuda(db, carlos, ecuabet, pichincha):
    register_transaction(
        db, kind=KIND_PURCHASE, amount=250.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, status=STATUS_PENDING, note="DoradoBet mayorista",
    )
    assert ecuabet.balance == 750.0
    assert pichincha.balance == 0.0
    assert total_payables(db) == 250.0


def test_egreso_descuenta_cuenta(db, carlos, efectivo):
    register_transaction(db, kind=KIND_EXPENSE, amount=50.0, collaborator_id=carlos.id, account_id=efectivo.id)
    assert efectivo.balance == 150.0


def test_montos_invalidos_y_reglas_obligatorias(db, carlos, ecuabet, efectivo):
    with pytest.raises(BusinessError):
        register_transaction(db, kind=KIND_SALE, amount=0, collaborator_id=carlos.id, platform_id=ecuabet.id, account_id=efectivo.id)
    with pytest.raises(BusinessError):
        register_transaction(db, kind=KIND_SALE, amount=10, collaborator_id=carlos.id, account_id=efectivo.id)
    with pytest.raises(BusinessError):
        register_transaction(db, kind=KIND_SALE, amount=10, collaborator_id=carlos.id, platform_id=ecuabet.id, status=STATUS_PENDING)
    with pytest.raises(BusinessError):
        register_transaction(db, kind=KIND_EXPENSE, amount=10, collaborator_id=carlos.id)
    with pytest.raises(BusinessError):
        register_transaction(db, kind="otro", amount=10, collaborator_id=carlos.id, account_id=efectivo.id)


def test_arqueo_diario_consolida_totales(db, carlos, ecuabet, efectivo):
    register_transaction(db, kind=KIND_SALE, amount=100.0, collaborator_id=carlos.id, platform_id=ecuabet.id, account_id=efectivo.id)
    register_transaction(db, kind=KIND_SALE, amount=40.0, collaborator_id=carlos.id, platform_id=ecuabet.id, status=STATUS_PENDING, client_name="Ana")
    register_transaction(db, kind=KIND_EXPENSE, amount=25.0, collaborator_id=carlos.id, account_id=efectivo.id)
    register_transaction(db, kind=KIND_PURCHASE, amount=200.0, collaborator_id=carlos.id, platform_id=ecuabet.id, status=STATUS_PENDING)

    totals = daily_totals(db, date.today())
    assert totals["ventas_total"] == 140.0
    assert totals["ventas_cobradas"] == 100.0
    assert totals["ventas_credito"] == 40.0
    assert totals["egresos"] == 25.0
    assert totals["compras_cupo"] == 200.0
    assert totals["utilidad_operativa"] == 75.0
    assert totals["cuentas_por_cobrar"] == 40.0
    assert totals["deuda_distribuidores"] == 200.0


def test_reporte_csv_incluye_secciones(db, carlos, ecuabet, efectivo):
    from app.services import daily_report_csv

    register_transaction(db, kind=KIND_SALE, amount=10.0, collaborator_id=carlos.id, platform_id=ecuabet.id, account_id=efectivo.id)
    csv_text = daily_report_csv(db, date.today())
    assert "ARQUEO DE CAJA" in csv_text
    assert "Saldos de plataformas" in csv_text
    assert "Ecuabet" in csv_text
    assert "cuentas_por_cobrar" in csv_text
