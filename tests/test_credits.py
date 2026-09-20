import pytest

from app.models import KIND_PURCHASE, KIND_SALE, STATUS_PAID, STATUS_PENDING
from app.services import (
    BusinessError,
    register_payment,
    register_transaction,
    total_payables,
    total_receivables,
)


def test_abono_parcial_y_liquidacion_de_credito_cliente(db, carlos, ecuabet, efectivo):
    tx = register_transaction(
        db, kind=KIND_SALE, amount=100.0, collaborator_id=carlos.id, platform_id=ecuabet.id,
        status=STATUS_PENDING, client_name="Maria",
    )

    register_payment(db, transaction_id=tx.id, amount=40.0, account_id=efectivo.id, collaborator_id=carlos.id)
    assert tx.outstanding == 60.0
    assert tx.status == STATUS_PENDING
    assert efectivo.balance == 240.0
    assert total_receivables(db) == 60.0

    register_payment(db, transaction_id=tx.id, amount=60.0, account_id=efectivo.id)
    assert tx.status == STATUS_PAID
    assert tx.outstanding == 0.0
    assert efectivo.balance == 300.0
    assert total_receivables(db) == 0.0


def test_liquidar_deuda_distribuidor_descuenta_banco(db, carlos, ecuabet, pichincha):
    pichincha.balance = 500.0
    db.commit()
    tx = register_transaction(
        db, kind=KIND_PURCHASE, amount=300.0, collaborator_id=carlos.id,
        platform_id=ecuabet.id, status=STATUS_PENDING,
    )

    register_payment(db, transaction_id=tx.id, amount=300.0, account_id=pichincha.id)
    assert pichincha.balance == 200.0
    assert tx.status == STATUS_PAID
    assert total_payables(db) == 0.0


def test_abono_invalido(db, carlos, ecuabet, efectivo):
    tx = register_transaction(
        db, kind=KIND_SALE, amount=50.0, collaborator_id=carlos.id, platform_id=ecuabet.id,
        status=STATUS_PENDING, client_name="Luis",
    )
    with pytest.raises(BusinessError):
        register_payment(db, transaction_id=tx.id, amount=80.0, account_id=efectivo.id)
    with pytest.raises(BusinessError):
        register_payment(db, transaction_id=tx.id, amount=0, account_id=efectivo.id)

    register_payment(db, transaction_id=tx.id, amount=50.0, account_id=efectivo.id)
    with pytest.raises(BusinessError):
        register_payment(db, transaction_id=tx.id, amount=10.0, account_id=efectivo.id)


def test_egreso_no_admite_abonos(db, carlos, efectivo):
    from app.models import KIND_EXPENSE

    tx = register_transaction(db, kind=KIND_EXPENSE, amount=20.0, collaborator_id=carlos.id, account_id=efectivo.id)
    tx.status = STATUS_PENDING
    db.commit()
    with pytest.raises(BusinessError):
        register_payment(db, transaction_id=tx.id, amount=5.0, account_id=efectivo.id)
