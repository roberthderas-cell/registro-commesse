"""Fonti dati: caricamento di file (Excel/CSV, FatturaPA, estratti conto) e sincronizzazione con i gestionali."""
import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..connettori import CONNETTORI, TIPI
from ..connettori.erp import carica_fonti, fonte
from ..importazione import importa
from .deps import DB, Utente, richiede

router = APIRouter(prefix="/api/fonti", tags=["fonti"])
MAX_FILE = 30 * 1024 * 1024


@router.get("")
def elenco(u: Utente = Depends(richiede("admin"))):
    erp = []
    try:
        erp = [f.info() for f in carica_fonti()]
    except Exception as e:  # fonti.yaml scritto male: lo si segnala senza bloccare il resto
        erp = [{"nome": "_errore", "etichetta": "fonti.yaml non valido", "errore": str(e), "tipi": []}]
    return {"file": [c.info() for c in CONNETTORI.values()], "erp": erp,
            "tipi": {k: {"l": v["l"], "req": v["req"], "opt": v["opt"]} for k, v in TIPI.items()}}


@router.post("/file/{nome}")
async def carica_file(nome: str, file: UploadFile = File(...), tipo: str | None = Form(None), salva: bool = Form(False),
                      db: Session = DB, u: Utente = Depends(richiede("admin"))):
    conn = CONNETTORI.get(nome)
    if not conn:
        raise HTTPException(404, f"Connettore sconosciuto: {nome}")
    dati = await file.read()
    if len(dati) > MAX_FILE:
        raise HTTPException(413, "File troppo grande (massimo 30 MB)")
    lettura = conn.leggi(dati, file.filename or "file", tipo)
    fonte_nome = {"tabelle": "excel"}.get(nome, nome)
    return importa(db, lettura, connettore=nome, fonte=fonte_nome, origine=file.filename or nome, tipo=tipo or ",".join(conn.tipi),
                   chi=u.etichetta, salva=salva)


@router.post("/erp/{nome}")
def sincronizza(nome: str, salva: bool = False, tipi: str | None = None, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    f = fonte(nome)
    if not f:
        raise HTTPException(404, f"Fonte {nome} non configurata in fonti.yaml")
    # le commesse vanno lette per prime, così ordini e fatture trovano la commessa
    ordine = ["commessa", "ordine", "fattura_passiva", "rapportino", "fattura_attiva", "movimento"]
    scelti = sorted(tipi.split(",") if tipi else f.tipi, key=lambda t: ordine.index(t) if t in ordine else 99)
    lettura = f.leggi(scelti)
    return importa(db, lettura, connettore="erp", fonte=f"erp:{nome}", origine=f.etichetta, tipo=",".join(scelti), chi=u.etichetta, salva=salva)


@router.get("/storico")
def storico(db: Session = DB, u: Utente = Depends(richiede("admin", "direzione"))):
    return [{"id": x.id, "ts": x.ts, "connettore": x.connettore, "tipo": x.tipo, "origine": x.origine, "utente": x.utente,
             "ok": x.righe_ok, "errori": x.righe_err}
            for x in db.scalars(select(m.Importazione).order_by(m.Importazione.ts.desc()).limit(100))]


@router.get("/storico/{iid}")
def esito(iid: int, db: Session = DB, u: Utente = Depends(richiede("admin", "direzione"))):
    x = db.get(m.Importazione, iid)
    if not x:
        raise HTTPException(404, "Importazione non trovata")
    return x.esito


@router.get("/modello/{tipo}.csv")
def modello(tipo: str):
    """Modello CSV vuoto con le intestazioni giuste, da aprire in Excel."""
    if tipo not in TIPI or tipo == "fattura_sdi":
        raise HTTPException(404, "Tipo sconosciuto")
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerow(TIPI[tipo]["req"] + TIPI[tipo]["opt"])
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="modello_{tipo}.csv"'})
