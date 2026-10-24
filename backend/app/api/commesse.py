"""Commesse e operazioni sul fascicolo: avanzamento di stato, ordini, rapportini, varianti, fatture, incassi, documenti."""
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..calcoli import blocco_avanzamento, calc, eur, stato_rata
from ..config import BASE_DIR, oggi
from ..connettori import Record
from ..dominio import CATS, DOCS, STATI
from ..importazione import GESTORI, Scarta
from ..servizi import cfg_get, dettaglio, log, puo_avanzare, sintesi, visibili
from .deps import DB, Utente, commessa_o_404, richiede, utente

router = APIRouter(prefix="/api/commesse", tags=["commesse"])
DIR_DOC = BASE_DIR / "data" / "documenti"


@router.get("")
def elenco(db: Session = DB, u: Utente = Depends(utente)):
    cfg = cfg_get(db)
    return [sintesi(c, calc(c, cfg), u.ruolo) for c in visibili(db, u.ruolo, u.nome)]


@router.get("/{cod}")
def leggi(cod: str, db: Session = DB, u: Utente = Depends(utente)):
    return dettaglio(db, commessa_o_404(db, cod, u), cfg_get(db), u.ruolo, u.nome)


class NuovaCommessa(BaseModel):
    cliente: str
    oggetto: str = ""
    sistema: str = ""
    cantiere: str = ""
    commerciale: str = ""
    capo: str = ""
    ricavo: float = Field(gt=0)
    budget: dict[str, float] = {}
    piano: list[dict] = []  # [{descr, importo, trigger}]


@router.post("", status_code=201)
def crea(body: NuovaCommessa, db: Session = DB, u: Utente = Depends(richiede("admin", "commerciale", "direzione"))):
    anno = oggi().year
    ultimo = db.scalar(select(func.max(m.Commessa.cod)).where(m.Commessa.cod.like(f"C-{anno}-%")))
    cod = f"C-{anno}-{(int(ultimo.rsplit('-', 1)[1]) + 1 if ultimo else 1):03d}"
    c = m.Commessa(cod=cod, cliente=body.cliente, oggetto=body.oggetto, sistema=body.sistema, cantiere=body.cantiere,
                   commerciale=body.commerciale or u.nome, capo=body.capo, ricavo=body.ricavo, stato=0)
    c.budget = [m.VoceBudget(categoria=k, importo=body.budget.get(k, 0)) for k in CATS]
    piano = body.piano or [{"descr": "Saldo a collaudo", "importo": body.ricavo, "trigger": "collaudo"}]
    c.piano = [m.Rata(codice=f"R{i}", descr=p["descr"], importo=p["importo"], trigger=p.get("trigger", "collaudo")) for i, p in enumerate(piano, 1)]
    db.add(c)
    log(db, u.nome, cod, f"Creata commessa per {body.cliente} ({eur(body.ricavo)})", u.ruolo)
    db.commit()
    return {"cod": cod}


def _fine(db: Session, c: m.Commessa, u: Utente):
    db.commit()
    db.refresh(c)
    return dettaglio(db, c, cfg_get(db), u.ruolo, u.nome)


@router.post("/{cod}/avanza")
def avanza(cod: str, db: Session = DB, u: Utente = Depends(utente)):
    c = commessa_o_404(db, cod, u)
    if not puo_avanzare(c, u.ruolo, u.nome):
        raise HTTPException(403, f"Il ruolo {u.etichetta} non può far avanzare la commessa da «{STATI[c.stato]}»")
    motivo = blocco_avanzamento(db, c, calc(c, cfg_get(db)))
    if motivo:
        raise HTTPException(409, motivo)
    c.stato += 1
    if c.stato == 1 and not c.contratto:
        c.contratto = oggi()
    log(db, u.nome, cod, f"Stato: {STATI[c.stato]}", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/blocca")
def blocca(cod: str, bloccata: bool, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    c = commessa_o_404(db, cod, u)
    c.bloccata = bloccata
    log(db, u.nome, cod, "Commessa bloccata" if bloccata else "Commessa sbloccata", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/collaudo")
def collaudo(cod: str, db: Session = DB, u: Utente = Depends(richiede("admin", "tecnico"))):
    c = commessa_o_404(db, cod, u)
    if c.stato != 5:
        raise HTTPException(409, "Il collaudo si registra quando la commessa è in «Collaudo e DICH.IMP.»")
    c.collaudo_ok, c.collaudo_data = True, oggi()
    log(db, u.nome, cod, "Collaudo superato e DICH.IMP. rilasciata", u.ruolo)
    return _fine(db, c, u)


def _manuale(db: Session, tipo: str, dati: dict, u: Utente):
    try:
        _, msg = GESTORI[tipo](db, Record(tipo, dati, "manuale"), "manuale", u.nome)
        return msg
    except Scarta as e:
        db.rollback()
        raise HTTPException(422, str(e))


class NuovoOrdine(BaseModel):
    fornitore: str
    categoria: str
    descrizione: str = ""
    importo: float = Field(gt=0)
    data: date | None = None


@router.post("/{cod}/ordini")
def nuovo_ordine(cod: str, body: NuovoOrdine, db: Session = DB, u: Utente = Depends(richiede("admin", "tecnico", "cantiere"))):
    c = commessa_o_404(db, cod, u)
    _manuale(db, "ordine", {"commessa": cod, **body.model_dump(), "data": body.data or oggi()}, u)
    return _fine(db, c, u)


@router.post("/{cod}/ordini/{oid}/{azione}")
def azione_ordine(cod: str, oid: str, azione: str, db: Session = DB, u: Utente = Depends(utente)):
    c = commessa_o_404(db, cod, u)
    o = db.get(m.Ordine, oid)
    if not o or o.commessa_id != c.id:
        raise HTTPException(404, "Ordine non trovato")
    if azione in ("autorizza", "respingi"):
        if u.ruolo not in ("admin", "direzione"):
            raise HTTPException(403, "Solo amministrazione e direzione autorizzano gli ordini oltre budget")
        if o.stato != "Autorizzazione richiesta":
            raise HTTPException(409, "L'ordine non è in attesa di autorizzazione")
        o.stato = "Ordinato" if azione == "autorizza" else "Respinto"
        o.nota = f"{'Autorizzato oltre budget' if azione == 'autorizza' else 'Respinto'} il {oggi():%d/%m/%Y}"
        log(db, u.nome, cod, f"Ordine {oid} {'autorizzato' if azione == 'autorizza' else 'respinto'}", u.ruolo)
    elif azione == "consegna":
        if u.ruolo not in ("admin", "cantiere", "capocantiere", "tecnico"):
            raise HTTPException(403, "Operazione non consentita")
        if o.stato != "Ordinato":
            raise HTTPException(409, "Si possono segnare consegnati solo gli ordini emessi")
        o.stato, o.consegna = "Consegnato", oggi()
        log(db, u.nome, cod, f"Consegnato ordine {oid} di {o.fornitore}", u.ruolo)
    else:
        raise HTTPException(404, "Azione sconosciuta")
    return _fine(db, c, u)


class NuovoRapportino(BaseModel):
    ore: float = Field(ge=0)
    avanzamento: int = Field(ge=0, le=100)
    nota: str = ""
    data: date | None = None


@router.post("/{cod}/rapportini")
def nuovo_rapportino(cod: str, body: NuovoRapportino, db: Session = DB, u: Utente = Depends(richiede("admin", "cantiere", "capocantiere"))):
    c = commessa_o_404(db, cod, u)
    if c.stato != 4:
        raise HTTPException(409, "I rapportini si inseriscono quando la commessa è in «Posa in cantiere»")
    k = calc(c, cfg_get(db))
    if body.avanzamento < k.avanz:
        raise HTTPException(422, f"L'avanzamento non può scendere sotto il {k.avanz}% già dichiarato")
    _manuale(db, "rapportino", {"commessa": cod, "data": body.data or oggi(), "ore": body.ore, "avanzamento": body.avanzamento,
                                "nota": body.nota, "chi": u.nome}, u)
    return _fine(db, c, u)


class NuovaVariante(BaseModel):
    descr: str
    importo: float = Field(gt=0)


@router.post("/{cod}/varianti")
def nuova_variante(cod: str, body: NuovaVariante, db: Session = DB, u: Utente = Depends(richiede("admin", "commerciale"))):
    c = commessa_o_404(db, cod, u)
    n = len(c.varianti) + 1
    c.varianti.append(m.Variante(codice=f"V{n}", descr=body.descr, importo=body.importo, stato="proposta", da=u.nome, data=oggi()))
    log(db, u.nome, cod, f"Proposta variante V{n} da {eur(body.importo)}", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/varianti/{vid}/{azione}")
def decidi_variante(cod: str, vid: int, azione: str, db: Session = DB, u: Utente = Depends(richiede("admin", "direzione"))):
    c = commessa_o_404(db, cod, u)
    v = next((x for x in c.varianti if x.id == vid), None)
    if not v or v.stato != "proposta" or azione not in ("approva", "respingi"):
        raise HTTPException(409, "Variante non trovata o già decisa")
    v.stato = "approvata" if azione == "approva" else "respinta"
    if v.stato == "approvata":
        c.piano.append(m.Rata(codice=f"R{v.codice}", descr=f"Variante {v.codice}, {v.descr}", importo=v.importo, trigger="collaudo"))
    log(db, u.nome, cod, f"Variante {v.codice} {v.stato}", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/rate/{rid}/fattura")
def emetti_fattura(cod: str, rid: int, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    c = commessa_o_404(db, cod, u)
    p = next((x for x in c.piano if x.id == rid), None)
    if not p:
        raise HTTPException(404, "Rata non trovata")
    if not stato_rata(c, p, calc(c, cfg_get(db))).get("fb"):
        raise HTTPException(409, "La rata non è ancora fatturabile")
    anno = oggi().year
    nums = [x for x in db.scalars(select(m.Rata.fattura_num).where(m.Rata.fattura_num.like(f"FA {anno}/%")))]
    n = max((int(x.rsplit("/", 1)[1]) for x in nums), default=0) + 1
    p.fattura_num, p.fattura_data, p.fattura_fonte = f"FA {anno}/{n:03d}", oggi(), "manuale"
    p.fattura_scad = oggi() + timedelta(days=cfg_get(db)["ggPag"])
    log(db, u.nome, cod, f"Emessa fattura {p.fattura_num} ({p.descr}, {eur(p.importo)})", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/rate/{rid}/incasso")
def registra_incasso(cod: str, rid: int, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    c = commessa_o_404(db, cod, u)
    p = next((x for x in c.piano if x.id == rid), None)
    if not p or not p.fattura_num or p.incasso_data:
        raise HTTPException(409, "Rata non fatturata o già incassata")
    p.incasso_data, p.incasso_fonte = oggi(), "manuale"
    log(db, u.nome, cod, f"Incassata fattura {p.fattura_num} ({eur(p.importo)})", u.ruolo)
    return _fine(db, c, u)


@router.post("/{cod}/documenti/{tipo}")
async def carica_documento(cod: str, tipo: str, file: UploadFile = File(...), db: Session = DB, u: Utente = Depends(utente)):
    c = commessa_o_404(db, cod, u)
    spec = next((d for d in DOCS if d["k"] == tipo), None)
    if not spec:
        raise HTTPException(404, "Tipo di documento sconosciuto")
    if u.ruolo not in ("admin", spec["chi"]):
        raise HTTPException(403, f"Il documento «{spec['l']}» lo carica il ruolo responsabile")
    cartella = DIR_DOC / cod
    cartella.mkdir(parents=True, exist_ok=True)
    nome = Path(file.filename or f"{tipo}.pdf").name
    (cartella / nome).write_bytes(await file.read())
    doc = next((d for d in c.documenti if d.tipo == tipo), None) or m.Documento(tipo=tipo)
    doc.file, doc.data, doc.chi = nome, oggi(), u.nome
    if doc not in c.documenti:
        c.documenti.append(doc)
    log(db, u.nome, cod, f"Caricato documento: {spec['l']} ({nome})", u.ruolo)
    return _fine(db, c, u)
