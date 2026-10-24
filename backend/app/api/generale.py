"""Cruscotto, casella fatture SDI, registro attività, impostazioni e costanti per l'interfaccia."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..calcoli import avvisi, calc, eur, incassi_attesi
from ..config import oggi
from ..connettori import Record
from ..dominio import CATS, DOCS, FASI, ROLES, SEE, STATI, TRIG
from ..importazione import GESTORI, Scarta
from ..servizi import cfg_get, log, visibili
from .deps import DB, Utente, richiede, utente

router = APIRouter(prefix="/api", tags=["generale"])


@router.get("/meta")
def meta(db: Session = DB, u: Utente = Depends(utente)):
    return {"stati": STATI, "fasi": FASI, "cats": CATS, "docs": DOCS, "ruoli": ROLES, "trig": TRIG, "oggi": oggi(),
            "vede": sorted(SEE[u.ruolo]), "utente": u.nome, "username": u.username, "ruolo": u.ruolo, "cfg": cfg_get(db)}


@router.get("/cruscotto")
def cruscotto(db: Session = DB, u: Utente = Depends(richiede("admin", "direzione"))):
    cfg = cfg_get(db)
    tutte = visibili(db, u.ruolo, u.nome)
    ks = [(c, calc(c, cfg)) for c in tutte]
    attive = [(c, k) for c, k in ks if c.stato < 8]
    ordini = [o for c in tutte for o in c.ordini if o.stato not in ("Respinto", "Autorizzazione richiesta")]
    fatt = [p for c in tutte for p in c.piano if p.fattura_num]
    portafoglio = sum(k.ricavo for _, k in attive)
    return {
        "kpi": {
            "portafoglio": portafoglio, "n_attive": len(attive),
            "margine": sum(k.margine for _, k in attive), "marg_pct": (sum(k.margine for _, k in attive) / portafoglio) if portafoglio else 0,
            "da_fatturare": sum(k.ricavo - k.fatturato for _, k in attive),
            "credito": sum(k.credito for _, k in ks), "wip": sum(k.wip for _, k in attive),
            "scaduto": sum(p.importo for p in fatt if not p.incasso_data and p.fattura_scad and p.fattura_scad < oggi()),
        },
        "flusso": [
            {"k": "contratti", "l": "Contratti", "v": sum(k.ricavo for _, k in ks), "f": "eur", "s": f"{len(tutte)} commesse", "c": "--ph-avvio"},
            {"k": "ordini", "l": "Ordini fornitori", "v": sum(o.importo for o in ordini), "f": "eur", "s": f"{len(ordini)} ordini emessi", "c": "--ph-appr"},
            {"k": "consegne", "l": "Consegne", "v": sum(1 for o in ordini if o.stato == "Consegnato"), "f": "int", "s": f"su {len(ordini)} ordini", "c": "--ph-prog"},
            {"k": "cantiere", "l": "Cantiere", "v": sum(r.ore for c in tutte for r in c.rapportini), "f": "h",
             "s": f"{sum(len(c.rapportini) for c in tutte)} rapportini", "c": "--ph-cant"},
            {"k": "costi", "l": "Costi registrati", "v": sum(f.importo for c in tutte for f in c.fp), "f": "eur",
             "s": f"{sum(len(c.fp) for c in tutte)} fatture passive", "c": "--c-costi"},
            {"k": "fatturato", "l": "Fatturato", "v": sum(p.importo for p in fatt), "f": "eur", "s": f"{len(fatt)} fatture emesse", "c": "--c-fatt"},
            {"k": "incassato", "l": "Incassato", "v": sum(p.importo for p in fatt if p.incasso_data), "f": "eur",
             "s": f"{sum(1 for p in fatt if p.incasso_data)} incassi", "c": "--c-inc"},
        ],
        "commesse": [{"cod": c.cod, "cliente": c.cliente, "stato": c.stato, "ricavo": k.ricavo, "eac": k.eac, "fatturato": k.fatturato,
                      "incassato": k.incassato, "marg_pct": k.marg_pct} for c, k in attive],
        "avvisi": avvisi(db, tutte, cfg),
        "incassi": incassi_attesi(tutte, cfg),
    }


@router.get("/sdi")
def casella_sdi(db: Session = DB, u: Utente = Depends(richiede("admin"))):
    out = []
    for f in db.scalars(select(m.FatturaSdi).order_by(m.FatturaSdi.data.desc())):
        o = db.get(m.Ordine, f.rif_ordine) if f.rif_ordine else None
        out.append({"id": f.id, "sdi_id": f.sdi_id, "fornitore": f.fornitore, "piva": f.piva_fornitore, "num": f.num, "data": f.data,
                    "scadenza": f.scadenza, "importo": f.importo, "rif_ordine": f.rif_ordine, "rif_commessa": f.rif_commessa,
                    "descrizione": f.descrizione, "file": f.file_name, "fonte": f.fonte,
                    "ordine": {"commessa": o.commessa.cod, "categoria": o.categoria, "importo": o.importo, "fornitore": o.fornitore,
                               "fatturato": sum(x.importo for x in o.commessa.fp if x.ordine_id == o.id)} if o else None})
    return out


class Registrazione(BaseModel):
    commessa: str
    categoria: str | None = None
    ordine: str | None = None


@router.post("/sdi/{fid}/registra")
def registra_sdi(fid: int, body: Registrazione, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    f = db.get(m.FatturaSdi, fid)
    if not f:
        raise HTTPException(404, "Fattura non trovata")
    dati = {"commessa": body.commessa, "fornitore": f.fornitore, "numero": f.num, "data": f.data, "importo": f.importo,
            "ordine": body.ordine if body.ordine is not None else f.rif_ordine, "categoria": body.categoria,
            "piva_fornitore": f.piva_fornitore, "scadenza": f.scadenza}
    try:
        _, msg = GESTORI["fattura_passiva"](db, Record("fattura_passiva", dati, "sdi", rif_esterno=f.rif_esterno), f.fonte, u.nome)
    except Scarta as e:
        db.rollback()
        raise HTTPException(422, str(e))
    db.commit()
    return {"m": msg}


@router.delete("/sdi/{fid}")
def scarta_sdi(fid: int, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    f = db.get(m.FatturaSdi, fid)
    if not f:
        raise HTTPException(404, "Fattura non trovata")
    log(db, u.nome, f.rif_commessa, f"Scartata dalla casella SDI la fattura {f.num} di {f.fornitore} ({eur(f.importo)}): non di commessa", u.ruolo)
    db.delete(f)
    db.commit()
    return {"ok": True}


@router.get("/log")
def registro(cod: str | None = None, limit: int = 300, db: Session = DB, u: Utente = Depends(richiede("admin", "direzione", "commerciale", "tecnico", "cantiere"))):
    q = select(m.LogEvento).order_by(m.LogEvento.ts.desc(), m.LogEvento.id.desc()).limit(limit)
    if cod:
        q = q.where(m.LogEvento.cod == cod)
    return [{"id": x.id, "ts": x.ts, "chi": x.chi, "ruolo": x.ruolo, "cod": x.cod, "t": x.testo} for x in db.scalars(q)]


@router.get("/movimenti")
def movimenti(db: Session = DB, u: Utente = Depends(richiede("admin"))):
    return [{"id": x.id, "data": x.data, "importo": x.importo, "causale": x.causale, "controparte": x.controparte, "fonte": x.fonte,
             "abbinamento": x.abbinamento, "abbinato": bool(x.rata_id or x.fattura_passiva_id)}
            for x in db.scalars(select(m.MovimentoBanca).order_by(m.MovimentoBanca.data.desc()))]


@router.put("/impostazioni")
def salva_impostazioni(cfg: dict, db: Session = DB, u: Utente = Depends(richiede("admin"))):
    nuovo = {**cfg_get(db), **{k: v for k, v in cfg.items() if k in cfg_get(db)}}
    row = db.get(m.Impostazione, "cfg") or m.Impostazione(chiave="cfg")
    row.valore = nuovo
    db.add(row)
    log(db, u.nome, None, "Aggiornate le impostazioni", u.ruolo)
    db.commit()
    return nuovo
