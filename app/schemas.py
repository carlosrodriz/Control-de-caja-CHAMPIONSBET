from pydantic import BaseModel, Field

from app.models import STATUS_PAID


class CollaboratorIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CollaboratorToggle(BaseModel):
    active: bool


class PlatformThresholds(BaseModel):
    min_balance: float = Field(ge=0)
    warning_balance: float = Field(ge=0)


class AccountAdjust(BaseModel):
    balance: float
    collaborator_id: int | None = None


class TransactionIn(BaseModel):
    kind: str
    amount: float = Field(gt=0)
    collaborator_id: int
    platform_id: int | None = None
    account_id: int | None = None
    status: str = STATUS_PAID
    client_name: str | None = None
    note: str | None = None


class PaymentIn(BaseModel):
    transaction_id: int
    amount: float = Field(gt=0)
    account_id: int
    collaborator_id: int | None = None
