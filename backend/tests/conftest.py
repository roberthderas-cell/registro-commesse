import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="rc-test-")
os.environ["RC_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["RC_OGGI"] = "2026-10-24"
os.environ["RC_FONTI_FILE"] = str(Path(__file__).resolve().parents[1] / "fonti.example.yaml")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import carica_esempio  # noqa: E402

ESEMPI = Path(__file__).resolve().parents[1] / "esempi"


@pytest.fixture(scope="session", autouse=True)
def erp_demo():
    from scripts.crea_erp_demo import main
    main()


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        carica_esempio(db)
    with TestClient(app) as c:
        yield c


def carica(client, connettore, file, tipo=None, salva=False):
    p = ESEMPI / file
    dati = {"salva": str(salva).lower()}
    if tipo:
        dati["tipo"] = tipo
    r = client.post(f"/api/fonti/file/{connettore}", files={"file": (p.name, p.read_bytes())}, data=dati)
    assert r.status_code == 200, r.text
    return r.json()
