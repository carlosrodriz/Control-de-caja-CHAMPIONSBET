from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import services
from app.database import Base, SessionLocal, engine, get_db
from app.models import Account, Collaborator, Platform
from app.schemas import (
    AccountAdjust,
    CollaboratorIn,
    CollaboratorToggle,
    PaymentIn,
    PlatformThresholds,
    TransactionIn,
)
from app.seed import seed_defaults
from app.services import BusinessError
from app.ws import manager

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Control de Caja CHAMPIONSBET", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def broadcast_state(db: Session, event: str) -> None:
    await manager.broadcast({"event": event, "state": services.build_state(db)})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
def get_state(db: Session = Depends(get_db)) -> dict:
    return services.build_state(db)


@app.post("/api/collaborators", status_code=201)
async def create_collaborator(payload: CollaboratorIn, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    if db.query(Collaborator).filter_by(name=name).first():
        raise HTTPException(status_code=400, detail="El colaborador ya existe")
    collaborator = Collaborator(name=name, active=True)
    db.add(collaborator)
    db.commit()
    db.refresh(collaborator)
    await broadcast_state(db, "colaborador_creado")
    return {"id": collaborator.id, "name": collaborator.name, "active": collaborator.active}


@app.patch("/api/collaborators/{collaborator_id}")
async def toggle_collaborator(
    collaborator_id: int, payload: CollaboratorToggle, db: Session = Depends(get_db)
) -> dict:
    collaborator = db.get(Collaborator, collaborator_id)
    if collaborator is None:
        raise HTTPException(status_code=404, detail="Colaborador no encontrado")
    collaborator.active = payload.active
    db.commit()
    await broadcast_state(db, "turno_actualizado")
    return {"id": collaborator.id, "name": collaborator.name, "active": collaborator.active}


@app.patch("/api/platforms/{platform_id}/thresholds")
async def update_thresholds(
    platform_id: int, payload: PlatformThresholds, db: Session = Depends(get_db)
) -> dict:
    platform = db.get(Platform, platform_id)
    if platform is None:
        raise HTTPException(status_code=404, detail="Plataforma no encontrada")
    if payload.warning_balance < payload.min_balance:
        raise HTTPException(
            status_code=400, detail="El umbral de advertencia no puede ser menor al mínimo"
        )
    platform.min_balance = payload.min_balance
    platform.warning_balance = payload.warning_balance
    db.commit()
    await broadcast_state(db, "umbrales_actualizados")
    return {"id": platform.id, "min_balance": platform.min_balance, "warning_balance": platform.warning_balance}


@app.patch("/api/accounts/{account_id}/balance")
async def adjust_account(account_id: int, payload: AccountAdjust, db: Session = Depends(get_db)) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    account.balance = round(payload.balance, 2)
    db.commit()
    await broadcast_state(db, "saldo_ajustado")
    return {"id": account.id, "balance": account.balance}


@app.post("/api/transactions", status_code=201)
async def create_transaction(payload: TransactionIn, db: Session = Depends(get_db)) -> dict:
    try:
        tx = services.register_transaction(db, **payload.model_dump())
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await broadcast_state(db, "transaccion_registrada")
    return services.serialize_transaction(tx)


@app.post("/api/payments", status_code=201)
async def create_payment(payload: PaymentIn, db: Session = Depends(get_db)) -> dict:
    try:
        payment = services.register_payment(db, **payload.model_dump())
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await broadcast_state(db, "abono_registrado")
    return {
        "id": payment.id,
        "transaction_id": payment.transaction_id,
        "amount": payment.amount,
        "outstanding": payment.transaction.outstanding,
        "status": payment.transaction.status,
    }


@app.get("/api/report/csv")
def report_csv(day: str | None = None, db: Session = Depends(get_db)) -> PlainTextResponse:
    try:
        report_day = date.fromisoformat(day) if day else date.today()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Fecha inválida (use YYYY-MM-DD)") from exc
    content = services.daily_report_csv(db, report_day)
    filename = f"arqueo-{report_day.isoformat()}.csv"
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    await manager.connect(websocket)
    await websocket.send_json({"event": "estado_inicial", "state": services.build_state(db)})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
