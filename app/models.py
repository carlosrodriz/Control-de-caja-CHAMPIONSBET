from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

KIND_SALE = "venta"
KIND_EXPENSE = "egreso"
KIND_PURCHASE = "compra_cupo"

STATUS_PAID = "pagada"
STATUS_PENDING = "pendiente"


class Collaborator(Base):
    __tablename__ = "collaborators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    min_balance: Mapped[float] = mapped_column(Float, default=0.0)
    warning_balance: Mapped[float] = mapped_column(Float, default=0.0)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="banco")
    balance: Mapped[float] = mapped_column(Float, default=0.0)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    collaborator_id: Mapped[int] = mapped_column(ForeignKey("collaborators.id"))
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PAID)
    client_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    collaborator: Mapped[Collaborator] = relationship()
    platform: Mapped[Platform | None] = relationship()
    account: Mapped[Account | None] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="transaction")

    @property
    def outstanding(self) -> float:
        return round(self.amount - self.paid_amount, 2)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    collaborator_id: Mapped[int | None] = mapped_column(ForeignKey("collaborators.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)

    transaction: Mapped[Transaction] = relationship(back_populates="payments")
    account: Mapped[Account] = relationship()
