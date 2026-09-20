from sqlalchemy.orm import Session

from app.models import Account, Collaborator, Platform

DEFAULT_COLLABORATORS = ["Carlos", "Refa"]

DEFAULT_PLATFORMS = [
    "Ecuabet",
    "DoradoBet",
    "Mas 1X2",
    "Astrobet",
    "Sportbet",
    "Mi Negocio Efectivo",
    "Bemovil",
]

DEFAULT_ACCOUNTS = [
    ("Efectivo", "efectivo"),
    ("Banco Pichincha", "banco"),
    ("Banco Guayaquil", "banco"),
    ("Banco Rumiñahui (BGR)", "banco"),
    ("Banco del Pacífico", "banco"),
    ("Cooperativa 29 de Octubre", "cooperativa"),
    ("COOPMEGO", "cooperativa"),
    ("Cooperativa JEP", "cooperativa"),
]

DEFAULT_MIN_BALANCE = 50.0
DEFAULT_WARNING_BALANCE = 150.0


def seed_defaults(db: Session) -> None:
    for name in DEFAULT_COLLABORATORS:
        if not db.query(Collaborator).filter_by(name=name).first():
            db.add(Collaborator(name=name, active=True))

    for name in DEFAULT_PLATFORMS:
        if not db.query(Platform).filter_by(name=name).first():
            db.add(
                Platform(
                    name=name,
                    balance=0.0,
                    min_balance=DEFAULT_MIN_BALANCE,
                    warning_balance=DEFAULT_WARNING_BALANCE,
                )
            )

    for name, kind in DEFAULT_ACCOUNTS:
        if not db.query(Account).filter_by(name=name).first():
            db.add(Account(name=name, kind=kind, balance=0.0))

    db.commit()
