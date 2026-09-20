from app.models import Account, Collaborator, Platform
from app.seed import DEFAULT_ACCOUNTS, DEFAULT_COLLABORATORS, DEFAULT_PLATFORMS, seed_defaults


def test_seed_creates_defaults(db):
    assert {c.name for c in db.query(Collaborator)} == set(DEFAULT_COLLABORATORS)
    assert {p.name for p in db.query(Platform)} == set(DEFAULT_PLATFORMS)
    assert {a.name for a in db.query(Account)} == {name for name, _ in DEFAULT_ACCOUNTS}


def test_seed_is_idempotent(db):
    seed_defaults(db)
    assert db.query(Platform).count() == len(DEFAULT_PLATFORMS)
    assert db.query(Account).count() == len(DEFAULT_ACCOUNTS)
