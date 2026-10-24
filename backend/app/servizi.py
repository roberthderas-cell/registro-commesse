"""Funzioni condivise tra API e importazione: impostazioni, registro attività, serializzazione per ruolo."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .calcoli import Kpi, blocco_avanzamento, calc, documenti_mancanti, stato_rata
from .dominio import CONFIG_DEFAULT, DOCS, NEXT_BY, ROLES, SEE, fase_di


def cfg_get(db: Session) -> dict:
    row = db.get(m.Impostazione, "cfg")
    return {**CONFIG_DEFAULT, **(row.valore if row else {})}


def log(db: Session, chi: str, cod: str | None, testo: str, ruolo: str = ""):
    db.add(m.LogEvento(ts=datetime.now().replace(microsecond=0), chi=chi, ruolo=ruolo, cod=cod, testo=testo))


def visibili(db: Session, ruolo: str, utente: str) -> list[m.Commessa]:
    q = select(m.Commessa).order_by(m.Commessa.cod)
    if ruolo == "capocantiere":
        q = q.where(m.Commessa.capo == utente)
    return list(db.scalars(q))


def puo_avanzare(c: m.Commessa, ruolo: str, utente: str) -> bool:
    if c.stato >= 8:
        return False
    if ruolo == "admin":
        return True
    if ruolo not in NEXT_BY[c.stato]:
        return False
    return not (ruolo == "capocantiere" and c.capo != utente)


CAMPI_R = {"ricavo", "var_appr", "fatturato", "incassato", "credito", "maturato", "wip"}
CAMPI_C = {"budget", "impegnato", "sostenuto", "eac", "mo", "cats"}
CAMPI_M = {"margine", "marg_pct", "c2c"}


def kpi_per_ruolo(k: Kpi, ruolo: str) -> dict:
    vede = SEE[ruolo]
    d = k.dict()
    for campi, chiave in ((CAMPI_R, "r"), (CAMPI_C, "c"), (CAMPI_M, "m")):
        if chiave not in vede:
            for x in campi:
                d.pop(x, None)
    return d


def sintesi(c: m.Commessa, k: Kpi, ruolo: str) -> dict:
    return {"cod": c.cod, "cliente": c.cliente, "oggetto": c.oggetto, "sistema": c.sistema, "cantiere": c.cantiere,
            "commerciale": c.commerciale, "capo": c.capo, "contratto": c.contratto, "stato": c.stato, "fase": fase_di(c.stato)["l"],
            "bloccata": c.bloccata, "collaudo_ok": c.collaudo_ok, "fonte": c.fonte,
            "n_avvisi_doc": len(documenti_mancanti(c, c.stato)) if c.stato < 8 else 0,
            "n_ordini_aut": sum(1 for o in c.ordini if o.stato == "Autorizzazione richiesta"),
            "kpi": kpi_per_ruolo(k, ruolo)}


def dettaglio(db: Session, c: m.Commessa, cfg: dict, ruolo: str, utente: str) -> dict:
    k = calc(c, cfg)
    vede = SEE[ruolo]
    out = sintesi(c, k, ruolo) | {
        "collaudo_data": c.collaudo_data, "piva_cliente": c.piva_cliente,
        "blocco": blocco_avanzamento(db, c, k), "puo_avanzare": puo_avanzare(c, ruolo, utente),
        "varianti": [{"id": v.id, "codice": v.codice, "descr": v.descr, "importo": v.importo if "r" in vede else None,
                      "stato": v.stato, "da": v.da, "data": v.data} for v in c.varianti],
        "rapportini": [{"id": r.id, "data": r.data, "chi": r.chi, "ore": r.ore, "avanz": r.avanz, "nota": r.nota, "fonte": r.fonte} for r in c.rapportini],
        "documenti": [{"k": d["k"], "l": d["l"], "fase": d["fase"], "chi": ROLES[d["chi"]]["l"],
                       **({"file": x.file, "data": x.data, "caricato_da": x.chi} if (x := next((y for y in c.documenti if y.tipo == d["k"]), None)) else {})}
                      for d in DOCS],
    }
    if "c" in vede:
        out["ordini"] = [{"id": o.id, "fornitore": o.fornitore, "categoria": o.categoria, "descr": o.descr, "importo": o.importo, "data": o.data,
                          "stato": o.stato, "consegna": o.consegna, "nota": o.nota, "fonte": o.fonte,
                          "fatturato": sum(f.importo for f in c.fp if f.ordine_id == o.id)} for o in c.ordini]
        out["fp"] = [{"id": f.id, "num": f.num, "fornitore": f.fornitore, "ordine": f.ordine_id, "categoria": f.categoria, "importo": f.importo,
                      "data": f.data, "pagamento": f.pagamento, "fonte": f.fonte} for f in c.fp]
    else:  # chi non vede i costi vede comunque ordini e consegne, senza importi
        out["ordini"] = [{"id": o.id, "fornitore": o.fornitore, "categoria": o.categoria, "descr": o.descr, "data": o.data, "stato": o.stato,
                          "consegna": o.consegna} for o in c.ordini]
    if "r" in vede:
        out["piano"] = [{"id": p.id, "codice": p.codice, "descr": p.descr, "importo": p.importo, "trigger": p.trigger,
                         "fattura_num": p.fattura_num, "fattura_data": p.fattura_data, "fattura_scad": p.fattura_scad,
                         "incasso_data": p.incasso_data, "stato": stato_rata(c, p, k)} for p in c.piano]
    return out
