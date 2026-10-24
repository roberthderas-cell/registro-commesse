"""Indicatori di commessa (margine, costo a finire, avanzamento economico, crediti) e avvisi.

È il porting fedele delle funzioni calc(), rata(), guard() e alerts() del prototipo HTML.
"""
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import oggi
from .dominio import CATS, DOCS, TRIG, doc_dovuto


@dataclass
class Voce:
    k: str
    budget: float
    imp: float
    sost: float
    eac: float
    residuo: float


@dataclass
class Kpi:
    var_appr: float
    ricavo: float
    ore: float
    mo: float
    avanz: int
    budget: float
    impegnato: float
    sostenuto: float
    eac: float
    margine: float
    marg_pct: float
    c2c: float
    maturato: float
    fatturato: float
    incassato: float
    wip: float
    credito: float
    cats: list[Voce] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def ordini_validi(c: m.Commessa) -> list[m.Ordine]:
    return [o for o in c.ordini if o.stato not in ("Autorizzazione richiesta", "Respinto")]


def calc(c: m.Commessa, cfg: dict) -> Kpi:
    var_appr = sum(v.importo for v in c.varianti if v.stato == "approvata")
    ricavo = c.ricavo + var_appr
    ore = sum(r.ore for r in c.rapportini)
    mo = ore * cfg["costoOra"]
    avanz = max(c.rapportini, key=lambda r: r.data).avanz if c.rapportini else 0
    valid = ordini_validi(c)
    budget_by = {b.categoria: b.importo for b in c.budget}
    cats = []
    for k in CATS:
        bud = budget_by.get(k, 0)
        if k == "Manodopera interna":
            imp = sost = mo
        else:
            imp = sum(o.importo for o in valid if o.categoria == k)
            sost = sum(f.importo for f in c.fp if f.categoria == k)
        eac = sost if c.collaudo_ok else max(bud, imp, sost)
        cats.append(Voce(k, bud, imp, sost, eac, bud - imp))
    budget = sum(x.budget for x in cats)
    impegnato = sum(x.imp for x in cats)
    sostenuto = sum(x.sost for x in cats)
    eac = sum(x.eac for x in cats)
    margine = ricavo - eac
    c2c = min(1, sostenuto / eac) if eac else 0
    maturato = ricavo * c2c
    fatturato = sum(p.importo for p in c.piano if p.fattura_num)
    incassato = sum(p.importo for p in c.piano if p.incasso_data)
    return Kpi(var_appr, ricavo, ore, mo, avanz, budget, impegnato, sostenuto, eac, margine,
               margine / ricavo if ricavo else 0, c2c, maturato, fatturato, incassato,
               maturato - fatturato, fatturato - incassato, cats)


def trigger_ok(c: m.Commessa, p: m.Rata, k: Kpi) -> bool:
    if p.trigger == "contratto":
        return c.stato >= 1
    if p.trigger == "avanz50":
        return k.avanz >= 50
    return c.collaudo_ok


def stato_rata(c: m.Commessa, p: m.Rata, k: Kpi) -> dict:
    if p.incasso_data:
        return {"t": "Incassata", "cls": "good"}
    if p.fattura_num:
        ritardo = (oggi() - p.fattura_scad).days if p.fattura_scad else 0
        if ritardo > 0:
            return {"t": f"Scaduta da {ritardo} gg", "cls": "bad", "late": ritardo}
        return {"t": "Fatturata, da incassare", "cls": "info"}
    if trigger_ok(c, p, k):
        return {"t": "Fatturabile", "cls": "warn", "fb": True}
    return {"t": "Da maturare", "cls": ""}


def documenti_mancanti(c: m.Commessa, stato: int) -> list[dict]:
    presenti = {d.tipo for d in c.documenti}
    return [d for d in DOCS if doc_dovuto(d, stato) and d["k"] not in presenti]


def blocco_avanzamento(db: Session, c: m.Commessa, k: Kpi) -> str | None:
    """Motivo per cui la commessa non può passare allo stato successivo, oppure None."""
    s = c.stato
    if c.bloccata:
        return "Commessa bloccata dall'amministrazione"
    if s == 4 and k.avanz < 100:
        return "Il cantiere deve dichiarare l'avanzamento al 100%"
    if s == 5 and not c.collaudo_ok:
        return "Collaudo e DICH.IMP. non ancora registrati"
    if s == 6 and any(not p.incasso_data for p in c.piano):
        return "Ci sono rate non fatturate o non incassate"
    if s == 7:
        ordini_ids = {o.id for o in c.ordini}
        aperti_sdi = db.scalars(select(m.FatturaSdi).where(m.FatturaSdi.rif_ordine.in_(ordini_ids))).first() if ordini_ids else None
        if any(o.stato == "Autorizzazione richiesta" for o in c.ordini) or aperti_sdi:
            return "Ci sono ordini o fatture passive ancora aperti"
    md = documenti_mancanti(c, s + 1)
    if md:
        return "Mancano documenti: " + ", ".join(d["l"] for d in md)
    return None


def eur(n: float) -> str:
    r = round(n)
    return ("−" if r < 0 else "") + f"{abs(r):,}".replace(",", ".") + " €"


def pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


def avvisi(db: Session, commesse: list[m.Commessa], cfg: dict) -> list[dict]:
    out: list[dict] = []
    ordini = {o.id: c for c in commesse for o in c.ordini}
    for f in db.scalars(select(m.FatturaSdi)):
        c = ordini.get(f.rif_ordine) if f.rif_ordine else None
        out.append({"sev": "warn", "cod": c.cod if c else f.rif_commessa, "tit": f"Fattura passiva SDI da registrare: {f.fornitore}",
                    "det": f"n. {f.num} · {eur(f.importo)}" + (f" · rif. {f.rif_ordine}" if f.rif_ordine else " · senza riferimento ordine"),
                    "go": {"view": "sdi"}})
    for c in commesse:
        k = calc(c, cfg)
        for o in c.ordini:
            if o.stato == "Autorizzazione richiesta":
                out.append({"sev": "warn", "cod": c.cod, "tit": f"Ordine {o.id} oltre budget da autorizzare", "det": f"{o.fornitore} · {eur(o.importo)}", "go": {"tab": "ordini"}})
        for v in c.varianti:
            if v.stato == "proposta":
                out.append({"sev": "info", "cod": c.cod, "tit": f"Variante da approvare: {v.descr}", "det": f"{eur(v.importo)} · proposta da {v.da}", "go": {"tab": "riepilogo"}})
        for p in c.piano:
            r = stato_rata(c, p, k)
            if r.get("fb"):
                out.append({"sev": "info", "cod": c.cod, "tit": f"Rata fatturabile: {p.descr}", "det": f"{eur(p.importo)} · {TRIG[p.trigger]}", "go": {"tab": "fatturazione"}})
            if r.get("late"):
                out.append({"sev": "bad", "cod": c.cod, "tit": f"Incasso scaduto da {r['late']} giorni", "det": f"{p.fattura_num} · {eur(p.importo)}", "go": {"tab": "fatturazione"}})
        if c.stato < 8:
            md = documenti_mancanti(c, c.stato)
            if md:
                out.append({"sev": "warn", "cod": c.cod, "tit": "Documenti di fase mancanti", "det": ", ".join(d["l"] for d in md), "go": {"tab": "documenti"}})
            if k.budget and k.sostenuto > k.budget:
                out.append({"sev": "warn", "cod": c.cod, "tit": f"Costi oltre budget (+{pct(k.sostenuto / k.budget - 1)})", "det": f"{eur(k.sostenuto)} su {eur(k.budget)}", "go": {"tab": "riepilogo"}})
            if k.marg_pct < cfg["sogliaMarg"] / 100:
                out.append({"sev": "bad", "cod": c.cod, "tit": f"Margine previsto sotto il {cfg['sogliaMarg']}% ({pct(k.marg_pct)})", "det": "Verificare costi e varianti", "go": {"tab": "riepilogo"}})
        if 4 <= c.stato < 6 and k.avanz - k.c2c * 100 >= cfg["sogliaGap"]:
            out.append({"sev": "warn", "cod": c.cod, "tit": "Cantiere più avanti dei costi registrati",
                        "det": f"Cantiere {k.avanz}% · costi {pct(k.c2c)}: possibili fatture non registrate", "go": {"tab": "riepilogo"}})
    ordine = {"bad": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda a: ordine[a["sev"]])


MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def incassi_attesi(commesse: list[m.Commessa], cfg: dict) -> list[dict]:
    """Incassi attesi per mese: scaduto + sei mesi; le rate fatturabili sono stimate a ggPag giorni."""
    oggi_ = oggi()
    mesi = []
    y, mo = oggi_.year, oggi_.month
    for _ in range(6):
        mesi.append(f"{y:04d}-{mo:02d}")
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
    bk = [{"k": "s", "l": "Scaduto", "a": 0.0, "b": 0.0}] + [{"k": x, "l": f"{MESI[int(x[5:]) - 1]} {x[2:4]}", "a": 0.0, "b": 0.0} for x in mesi]
    bk[-1]["l"] += "+"

    def put(due: date, v: float, key: str):
        if due < oggi_:
            b = bk[0]
        else:
            b = next((x for x in bk if x["k"] == due.isoformat()[:7]), bk[-1])
        b[key] += v

    for c in commesse:
        k = calc(c, cfg)
        for p in c.piano:
            if p.incasso_data:
                continue
            if p.fattura_num:
                put(p.fattura_scad or oggi_, p.importo, "a")
            elif stato_rata(c, p, k).get("fb"):
                put(oggi_ + timedelta(days=cfg["ggPag"]), p.importo, "b")
    return bk
