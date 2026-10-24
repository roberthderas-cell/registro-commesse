"""Accesso (login, uscita, cambio password) e gestione degli utenti da parte dell'amministrazione."""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import (COOKIE, apri_sessione, autentica, chiudi_sessione, chiudi_sessioni_utente, controlla_password_nuova,
                    hash_password, password_temporanea, verifica_password)
from ..config import settings
from ..dominio import ROLES
from ..servizi import log
from .deps import DB, Utente, richiede, utente_collegato

router = APIRouter(prefix="/api", tags=["accesso"])


def _me(u: m.Utente | Utente) -> dict:
    return {"id": u.id, "username": u.username, "nome": u.nome, "ruolo": u.ruolo, "deve_cambiare_password": u.deve_cambiare_password}


class Credenziali(BaseModel):
    username: str = Field(max_length=60)
    password: str = Field(max_length=200)


@router.post("/accesso/login")
def login(body: Credenziali, response: Response, db: Session = DB):
    u, errore = autentica(db, body.username, body.password)
    if not u:
        raise HTTPException(401, errore)
    token = apri_sessione(db, u)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure,
                        max_age=settings.durata_sessione_ore * 3600, path="/")
    return _me(u)


@router.post("/accesso/logout")
def logout(response: Response, db: Session = DB, rc_sessione: str | None = Cookie(None)):
    chiudi_sessione(db, rc_sessione)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/accesso/io")
def io(u: Utente = Depends(utente_collegato)):
    return _me(u)


class CambioPassword(BaseModel):
    attuale: str
    nuova: str = Field(max_length=200)


@router.post("/accesso/password")
def cambia_password(body: CambioPassword, db: Session = DB, u: Utente = Depends(utente_collegato), rc_sessione: str | None = Cookie(None)):
    row = db.get(m.Utente, u.id)
    if not verifica_password(body.attuale, row.password_hash):
        raise HTTPException(422, "La password attuale non è corretta")
    if body.nuova == body.attuale:
        raise HTTPException(422, "La nuova password deve essere diversa da quella attuale")
    if err := controlla_password_nuova(body.nuova, row.username):
        raise HTTPException(422, err)
    row.password_hash, row.deve_cambiare_password = hash_password(body.nuova), False
    chiudi_sessioni_utente(db, row.id, tranne=rc_sessione)  # esce dagli altri dispositivi
    log(db, row.nome, None, "Password cambiata", row.ruolo)
    db.commit()
    return _me(row)


# ---------- gestione utenti (solo amministrazione) ----------

def _riga(x: m.Utente) -> dict:
    return _me(x) | {"attivo": x.attivo, "creato": x.creato, "ultimo_accesso": x.ultimo_accesso, "bloccato_fino": x.bloccato_fino}


@router.get("/utenti")
def elenco_utenti(db: Session = DB, u: Utente = Depends(richiede("admin"))):
    return [_riga(x) for x in db.scalars(select(m.Utente).order_by(m.Utente.attivo.desc(), m.Utente.ruolo, m.Utente.nome))]


@router.get("/utenti/nomi")
def nomi_per_ruolo(ruolo: str, db: Session = DB, u: Utente = Depends(richiede("admin", "direzione", "commerciale", "tecnico", "cantiere"))):
    """Nomi degli utenti attivi di un ruolo, per esempio per scegliere il capocantiere di una commessa."""
    return list(db.scalars(select(m.Utente.nome).where(m.Utente.ruolo == ruolo, m.Utente.attivo).order_by(m.Utente.nome)))


class NuovoUtente(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    nome: str = Field(min_length=2, max_length=80)
    ruolo: str


@router.post("/utenti", status_code=201)
def crea_utente(body: NuovoUtente, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    if body.ruolo not in ROLES:
        raise HTTPException(422, "Ruolo sconosciuto")
    username = body.username.lower()
    if db.scalar(select(m.Utente.id).where(m.Utente.username == username)):
        raise HTTPException(409, f"Il nome utente {username} esiste già")
    pwd = password_temporanea()
    x = m.Utente(username=username, nome=body.nome.strip(), ruolo=body.ruolo, password_hash=hash_password(pwd), deve_cambiare_password=True)
    db.add(x)
    log(db, u.nome, None, f"Creato l'utente {username} ({x.nome}, {ROLES[body.ruolo]['l']})", u.ruolo)
    db.commit()
    return _riga(x) | {"password_temporanea": pwd}


class ModificaUtente(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=80)
    ruolo: str | None = None
    attivo: bool | None = None


def _admin_attivi(db: Session) -> int:
    return db.scalar(select(func.count(m.Utente.id)).where(m.Utente.ruolo == "admin", m.Utente.attivo)) or 0


@router.patch("/utenti/{uid}")
def modifica_utente(uid: int, body: ModificaUtente, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    x = db.get(m.Utente, uid)
    if not x:
        raise HTTPException(404, "Utente non trovato")
    if body.ruolo is not None and body.ruolo not in ROLES:
        raise HTTPException(422, "Ruolo sconosciuto")
    toglie_admin = x.ruolo == "admin" and x.attivo and ((body.ruolo and body.ruolo != "admin") or body.attivo is False)
    if toglie_admin and _admin_attivi(db) <= 1:
        raise HTTPException(409, "Deve restare almeno un utente di amministrazione attivo")
    cambi = []
    if body.nome and body.nome.strip() != x.nome:
        # i capocantiere sono collegati alle commesse per nome: si aggiornano insieme
        if x.ruolo == "capocantiere":
            for c in db.scalars(select(m.Commessa).where(m.Commessa.capo == x.nome)):
                c.capo = body.nome.strip()
        cambi.append(f"nome «{x.nome}» → «{body.nome.strip()}»")
        x.nome = body.nome.strip()
    if body.ruolo and body.ruolo != x.ruolo:
        cambi.append(f"ruolo {ROLES[x.ruolo]['l']} → {ROLES[body.ruolo]['l']}")
        x.ruolo = body.ruolo
        chiudi_sessioni_utente(db, x.id)  # i nuovi permessi valgono dal prossimo accesso
    if body.attivo is not None and body.attivo != x.attivo:
        cambi.append("riattivato" if body.attivo else "disattivato")
        x.attivo = body.attivo
        if not body.attivo:
            chiudi_sessioni_utente(db, x.id)
    if cambi:
        log(db, u.nome, None, f"Utente {x.username}: " + ", ".join(cambi), u.ruolo)
    db.commit()
    return _riga(x)


@router.post("/utenti/{uid}/reimposta-password")
def reimposta_password(uid: int, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    x = db.get(m.Utente, uid)
    if not x:
        raise HTTPException(404, "Utente non trovato")
    pwd = password_temporanea()
    x.password_hash, x.deve_cambiare_password, x.tentativi_falliti, x.bloccato_fino = hash_password(pwd), True, 0, None
    chiudi_sessioni_utente(db, x.id)
    log(db, u.nome, None, f"Reimpostata la password dell'utente {x.username}", u.ruolo)
    db.commit()
    return _riga(x) | {"password_temporanea": pwd}
