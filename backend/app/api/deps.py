from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..dominio import ROLES


@dataclass
class Utente:
    ruolo: str
    nome: str

    @property
    def etichetta(self) -> str:
        return ROLES[self.ruolo]["l"]


# Provvisorio: il ruolo arriva dall'intestazione X-Ruolo scelta nell'interfaccia.
# Prima di andare in produzione va sostituito con un login vero (vedi README, "Prossimi passi").
def utente(x_ruolo: str = Header("admin"), x_utente: str = Header("")) -> Utente:
    if x_ruolo not in ROLES:
        raise HTTPException(400, f"Ruolo sconosciuto: {x_ruolo}")
    nome = x_utente or ("M. Ferrari" if x_ruolo == "capocantiere" else ROLES[x_ruolo]["l"])
    return Utente(x_ruolo, nome)


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


DB = Depends(get_db)
