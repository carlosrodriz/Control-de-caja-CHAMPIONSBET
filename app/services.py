import csv
import io
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.models import (
    KIND_EXPENSE,
    KIND_PURCHASE,
    KIND_SALE,
    STATUS_PAID,
    STATUS_PENDING,
    Account,
    Collaborator,
    Payment,
    Platform,
    Transaction,
)

STATUS_OK = "optimo"
STATUS_WARNING = "advertencia"
STATUS_CRITICAL = "critico"


class BusinessError(Exception):
    """Regla de negocio incumplida al registrar una operación."""


def platform_status(balance: float, min_balance: float, warning_balance: float) -> str:
    if balance <= min_balance:
        return STATUS_CRITICAL
    if balance <= warning_balance:
        return STATUS_WARNING
    return STATUS_OK


def _get(db: Session, model, obj_id, label: str):
    obj = db.get(model, obj_id) if obj_id is not None else None
    if obj is None:
        raise BusinessError(f"{label} no encontrado")
    return obj


def register_transaction(
    db: Session,
    *,
    kind: str,
    amount: float,
    collaborator_id: int,
    platform_id: int | None = None,
    account_id: int | None = None,
    status: str = STATUS_PAID,
    client_name: str | None = None,
    note: str | None = None,
) -> Transaction:
    if amount <= 0:
        raise BusinessError("El monto debe ser mayor a cero")
    if status not in (STATUS_PAID, STATUS_PENDING):
        raise BusinessError("Estado inválido")

    collaborator = _get(db, Collaborator, collaborator_id, "Colaborador")
    platform = _get(db, Platform, platform_id, "Plataforma") if platform_id else None
    account = _get(db, Account, account_id, "Cuenta") if account_id else None

    if kind == KIND_SALE:
        if platform is None:
            raise BusinessError("La venta requiere una plataforma")
        if status == STATUS_PAID and account is None:
            raise BusinessError("La venta cancelada requiere cuenta o efectivo de ingreso")
        if status == STATUS_PENDING and not client_name:
            raise BusinessError("El crédito requiere el nombre del cliente")
        platform.balance = round(platform.balance - amount, 2)
        if status == STATUS_PAID:
            account.balance = round(account.balance + amount, 2)
    elif kind == KIND_PURCHASE:
        if platform is None:
            raise BusinessError("La compra de cupo requiere una plataforma")
        if status == STATUS_PAID and account is None:
            raise BusinessError("La compra de contado requiere la cuenta de salida")
        platform.balance = round(platform.balance + amount, 2)
        if status == STATUS_PAID:
            account.balance = round(account.balance - amount, 2)
    elif kind == KIND_EXPENSE:
        if account is None:
            raise BusinessError("El egreso requiere una cuenta o efectivo")
        account.balance = round(account.balance - amount, 2)
        status = STATUS_PAID
    else:
        raise BusinessError("Tipo de operación inválido")

    tx = Transaction(
        kind=kind,
        amount=round(amount, 2),
        collaborator_id=collaborator.id,
        platform_id=platform.id if platform else None,
        account_id=account.id if account else None,
        status=status,
        client_name=client_name,
        paid_amount=round(amount, 2) if status == STATUS_PAID else 0.0,
        note=note,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def register_payment(
    db: Session,
    *,
    transaction_id: int,
    amount: float,
    account_id: int,
    collaborator_id: int | None = None,
) -> Payment:
    if amount <= 0:
        raise BusinessError("El abono debe ser mayor a cero")

    tx = _get(db, Transaction, transaction_id, "Transacción")
    account = _get(db, Account, account_id, "Cuenta")

    if tx.status != STATUS_PENDING:
        raise BusinessError("La transacción ya está liquidada")
    if amount > tx.outstanding + 1e-9:
        raise BusinessError("El abono supera el saldo pendiente")

    if tx.kind == KIND_SALE:
        account.balance = round(account.balance + amount, 2)
    elif tx.kind == KIND_PURCHASE:
        account.balance = round(account.balance - amount, 2)
    else:
        raise BusinessError("Solo ventas a crédito o compras a crédito admiten abonos")

    tx.paid_amount = round(tx.paid_amount + amount, 2)
    if tx.outstanding <= 0:
        tx.status = STATUS_PAID

    payment = Payment(
        transaction_id=tx.id,
        account_id=account.id,
        collaborator_id=collaborator_id,
        amount=round(amount, 2),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def total_receivables(db: Session) -> float:
    pending = db.query(Transaction).filter_by(kind=KIND_SALE, status=STATUS_PENDING).all()
    return round(sum(tx.outstanding for tx in pending), 2)


def total_payables(db: Session) -> float:
    pending = db.query(Transaction).filter_by(kind=KIND_PURCHASE, status=STATUS_PENDING).all()
    return round(sum(tx.outstanding for tx in pending), 2)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


def transactions_of_day(db: Session, day: date) -> list[Transaction]:
    start, end = _day_bounds(day)
    return (
        db.query(Transaction)
        .filter(Transaction.created_at >= start, Transaction.created_at <= end)
        .order_by(Transaction.created_at)
        .all()
    )


def daily_totals(db: Session, day: date) -> dict:
    txs = transactions_of_day(db, day)
    sales = sum(t.amount for t in txs if t.kind == KIND_SALE)
    sales_cash = sum(t.amount for t in txs if t.kind == KIND_SALE and t.status == STATUS_PAID)
    sales_credit = sum(t.amount for t in txs if t.kind == KIND_SALE and t.status == STATUS_PENDING)
    purchases = sum(t.amount for t in txs if t.kind == KIND_PURCHASE)
    expenses = sum(t.amount for t in txs if t.kind == KIND_EXPENSE)
    return {
        "fecha": day.isoformat(),
        "ventas_total": round(sales, 2),
        "ventas_cobradas": round(sales_cash, 2),
        "ventas_credito": round(sales_credit, 2),
        "compras_cupo": round(purchases, 2),
        "egresos": round(expenses, 2),
        "utilidad_operativa": round(sales_cash - expenses, 2),
        "cuentas_por_cobrar": total_receivables(db),
        "deuda_distribuidores": total_payables(db),
    }


def build_state(db: Session) -> dict:
    platforms = []
    for p in db.query(Platform).order_by(Platform.name).all():
        platforms.append(
            {
                "id": p.id,
                "name": p.name,
                "balance": round(p.balance, 2),
                "min_balance": p.min_balance,
                "warning_balance": p.warning_balance,
                "status": platform_status(p.balance, p.min_balance, p.warning_balance),
            }
        )

    accounts = [
        {"id": a.id, "name": a.name, "kind": a.kind, "balance": round(a.balance, 2)}
        for a in db.query(Account).order_by(Account.id).all()
    ]
    collaborators = [
        {"id": c.id, "name": c.name, "active": c.active}
        for c in db.query(Collaborator).order_by(Collaborator.id).all()
    ]

    pending = (
        db.query(Transaction)
        .filter(Transaction.status == STATUS_PENDING)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    recent = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(25).all()

    return {
        "platforms": platforms,
        "accounts": accounts,
        "collaborators": collaborators,
        "credits": [serialize_transaction(t) for t in pending if t.kind == KIND_SALE],
        "debts": [serialize_transaction(t) for t in pending if t.kind == KIND_PURCHASE],
        "transactions": [serialize_transaction(t) for t in recent],
        "totals": {
            **daily_totals(db, date.today()),
            "efectivo_y_bancos": round(sum(a["balance"] for a in accounts), 2),
        },
    }


def serialize_transaction(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "created_at": tx.created_at.isoformat(timespec="seconds"),
        "kind": tx.kind,
        "amount": round(tx.amount, 2),
        "paid_amount": round(tx.paid_amount, 2),
        "outstanding": tx.outstanding,
        "status": tx.status,
        "client_name": tx.client_name,
        "note": tx.note,
        "collaborator": tx.collaborator.name if tx.collaborator else None,
        "platform": tx.platform.name if tx.platform else None,
        "account": tx.account.name if tx.account else None,
    }


def daily_report_csv(db: Session, day: date) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["ARQUEO DE CAJA", day.isoformat()])
    writer.writerow([])

    writer.writerow(["Transacciones del día"])
    writer.writerow(
        ["Hora", "Tipo", "Colaborador", "Plataforma", "Cuenta", "Monto", "Estado", "Cliente", "Pendiente"]
    )
    for tx in transactions_of_day(db, day):
        writer.writerow(
            [
                tx.created_at.strftime("%H:%M:%S"),
                tx.kind,
                tx.collaborator.name if tx.collaborator else "",
                tx.platform.name if tx.platform else "",
                tx.account.name if tx.account else "",
                f"{tx.amount:.2f}",
                tx.status,
                tx.client_name or "",
                f"{tx.outstanding:.2f}",
            ]
        )

    writer.writerow([])
    writer.writerow(["Saldos de plataformas"])
    writer.writerow(["Plataforma", "Saldo", "Mínimo", "Estado"])
    for p in db.query(Platform).order_by(Platform.name).all():
        writer.writerow(
            [
                p.name,
                f"{p.balance:.2f}",
                f"{p.min_balance:.2f}",
                platform_status(p.balance, p.min_balance, p.warning_balance),
            ]
        )

    writer.writerow([])
    writer.writerow(["Saldos de cuentas"])
    writer.writerow(["Cuenta", "Tipo", "Saldo"])
    for a in db.query(Account).order_by(Account.id).all():
        writer.writerow([a.name, a.kind, f"{a.balance:.2f}"])

    writer.writerow([])
    writer.writerow(["Resumen"])
    for key, value in daily_totals(db, day).items():
        writer.writerow([key, value])

    return buffer.getvalue()
