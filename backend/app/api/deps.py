from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import COOKIE, utente_da_token
from ..db import get_db
from ..dominio import ROLES

DB = Depends(get_db)


@dataclass
class Utente:
    id: int
    username: str
    nome: str
    ruolo: str
    deve_cambiare_password: bool

    @property
    def etichetta(self) -> str:
        return ROLES[self.ruolo]["l"]


def utente_collegato(db: Session = DB, rc_sessione: str | None = Cookie(None)) -> Utente:
    """Utente della sessione, anche se deve ancora cambiare la password (serve alle API di accesso)."""
    u = utente_da_token(db, rc_sessione)
    if not u:
        raise HTTPException(401, "Accesso richiesto")
    return Utente(u.id, u.username, u.nome, u.ruolo, u.deve_cambiare_password)


def utente(u: Utente = Depends(utente_collegato)) -> Utente:
    if u.deve_cambiare_password:
        raise HTTPException(403, "Devi scegliere una nuova password prima di continuare")
    return u


def richiede(*ruoli: str):
    def dep(u: Utente = Depends(utente)) -> Utente:
        if u.ruolo not in ruoli:
            raise HTTPException(403, f"Operazione non consentita al ruolo {u.etichetta}")
        return u
    return dep


def commessa_o_404(db: Session, cod: str, u: Utente) -> m.Commessa:
    c = db.scalar(select(m.Commessa).where(m.Commessa.cod == cod))
    if not c or (u.ruolo == "capocantiere" and c.capo != u.nome):
        raise HTTPException(404, f"Commessa {cod} non trovata")
    return c


__all__ = ["COOKIE", "DB", "Utente", "commessa_o_404", "richiede", "utente", "utente_collegato"]
