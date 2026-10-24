import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="rc-test-")
# Per provare su PostgreSQL: RC_DATABASE_URL=postgresql+psycopg://... pytest
os.environ.setdefault("RC_DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ["RC_OGGI"] = "2026-10-24"
os.environ["RC_FONTI_FILE"] = str(Path(__file__).resolve().parents[1] / "fonti.example.yaml")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import _falliti_ip, hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Utente  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import carica_esempio  # noqa: E402

ESEMPI = Path(__file__).resolve().parents[1] / "esempi"


@pytest.fixture(scope="session", autouse=True)
def erp_demo():
    from scripts.crea_erp_demo import main
    main()


PASSWORD = "Prova-della-suite-1"
NOMI = {"admin": "Amministrazione", "direzione": "Direzione", "commerciale": "L. Bianchi", "tecnico": "Ufficio tecnico",
        "cantiere": "Ufficio cantiere", "capocantiere": "M. Ferrari"}


@pytest.fixture
def anonimo():
    """Client senza accesso, con database di esempio e un utente per ruolo (username = ruolo)."""
    _falliti_ip.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        carica_esempio(db)
        for ruolo, nome in NOMI.items():
            db.add(Utente(username=ruolo, nome=nome, ruolo=ruolo, password_hash=hash_password(PASSWORD), deve_cambiare_password=False))
        db.commit()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anonimo):
    accedi(anonimo, "admin")
    return anonimo


def accedi(client, username, password=PASSWORD):
    r = client.post("/api/accesso/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def carica(client, connettore, file, tipo=None, salva=False):
    p = ESEMPI / file
    dati = {"salva": str(salva).lower()}
    if tipo:
        dati["tipo"] = tipo
    r = client.post(f"/api/fonti/file/{connettore}", files={"file": (p.name, p.read_bytes())}, data=dati)
    assert r.status_code == 200, r.text
    return r.json()
