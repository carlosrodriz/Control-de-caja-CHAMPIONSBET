import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Account, Collaborator, Platform
from app.seed import seed_defaults


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    seed_defaults(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def carlos(db) -> Collaborator:
    return db.query(Collaborator).filter_by(name="Carlos").one()


@pytest.fixture()
def ecuabet(db) -> Platform:
    platform = db.query(Platform).filter_by(name="Ecuabet").one()
    platform.balance = 500.0
    db.commit()
    return platform


@pytest.fixture()
def efectivo(db) -> Account:
    account = db.query(Account).filter_by(name="Efectivo").one()
    account.balance = 200.0
    db.commit()
    return account


@pytest.fixture()
def pichincha(db) -> Account:
    return db.query(Account).filter_by(name="Banco Pichincha").one()
