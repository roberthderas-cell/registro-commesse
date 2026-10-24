"""Validazione e salvataggio dei record arrivati da qualunque fonte.

L'anteprima esegue esattamente lo stesso codice del salvataggio dentro una transazione che poi viene
annullata: così ciò che si vede in anteprima è ciò che verrà scritto.
"""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .calcoli import calc, eur
from .connettori import Lettura, Record
from .connettori.base import nrm, p_data, p_num
from .dominio import CATS, STATI
from .servizi import cfg_get, log


class Scarta(Exception):
    pass


def _commessa(db: Session, cod) -> m.Commessa:
    cod = str(cod or "").strip()
    c = db.scalar(select(m.Commessa).where(m.Commessa.cod == cod))
    if not c:
        raise Scarta(f"Commessa «{cod}» inesistente")
    return c


def _aperta(c: m.Commessa):
    if c.stato >= 8:
        raise Scarta(f"Commessa {c.cod} chiusa")


def _importo(v, positivo=True) -> float:
    x = p_num(v)
    if x is None or (positivo and x <= 0):
        raise Scarta(f"Importo non valido «{v}»")
    return round(x, 2)


def _data(v, campo="data", obbl=True):
    x = p_data(v)
    if x is None and (obbl or v not in (None, "")):
        raise Scarta(f"Valore non valido per {campo} «{v}», usa gg/mm/aaaa")
    return x


def _categoria(v) -> str | None:
    return next((k for k in CATS if nrm(k) == nrm(v)), None)


# ---------- un gestore per tipo di record: restituisce (azione, messaggio) ----------

def _commessa_rec(db, r: Record, fonte, chi):
    d = r.dati
    cod = str(d["cod"]).strip()
    if not cod or not d.get("cliente"):
        raise Scarta("Codice commessa e cliente sono obbligatori")
    c = db.scalar(select(m.Commessa).where(m.Commessa.cod == cod))
    nuovo = c is None
    if nuovo:
        c = m.Commessa(cod=cod, cliente=str(d["cliente"]), fonte=fonte, rif_esterno=r.rif_esterno or cod)
        db.add(c)
    for campo in ("cliente", "oggetto", "sistema", "cantiere", "commerciale", "capo", "piva_cliente"):
        if d.get(campo) not in (None, ""):
            setattr(c, campo, str(d[campo]))
    if d.get("contratto") not in (None, ""):
        c.contratto = _data(d["contratto"], "contratto")
    if d.get("ricavo") not in (None, ""):
        c.ricavo = _importo(d["ricavo"])
    if d.get("stato") not in (None, ""):
        st = next((i for i, s in enumerate(STATI) if nrm(s) == nrm(d["stato"])), None)
        if st is None and str(d["stato"]).isdigit() and int(d["stato"]) < len(STATI):
            st = int(d["stato"])
        if st is None:
            raise Scarta(f"Stato non valido «{d['stato']}»")
        c.stato = st
    db.flush()
    return ("creata" if nuovo else "aggiornata"), f"Commessa {cod} {'creata' if nuovo else 'aggiornata'} ({c.cliente})"


def _ordine(db, r: Record, fonte, chi):
    d = r.dati
    c = _commessa(db, d["commessa"])
    _aperta(c)
    forn = str(d.get("fornitore") or "").strip()
    if not forn:
        raise Scarta("Fornitore mancante")
    imp, dt = _importo(d["importo"]), _data(d["data"])
    cat = _categoria(d.get("categoria"))
    if not cat or cat == "Manodopera interna":
        raise Scarta(f"Categoria non valida «{d.get('categoria')}»")
    st_in = str(d.get("stato") or "").strip()
    st = next((x for x in ("Ordinato", "Consegnato") if nrm(x) == nrm(st_in)), None) if st_in else "Ordinato"
    if not st:
        raise Scarta(f"Stato non valido «{st_in}»")
    oid = str(d.get("id") or "").strip()
    o = db.get(m.Ordine, oid) if oid else None
    if o and o.fonte != fonte:
        raise Scarta(f"Ordine {oid} già presente (inserito da {o.fonte})")
    if o:  # stessa fonte: aggiornamento
        if o.commessa_id != c.id:
            raise Scarta(f"L'ordine {oid} è già registrato sulla commessa {o.commessa.cod}")
        o.fornitore, o.categoria, o.importo, o.data = forn, cat, imp, dt
        o.descr = str(d.get("descrizione") or o.descr)
        if o.stato in ("Ordinato", "Consegnato"):
            o.stato = st
        o.consegna = _data(d.get("consegna"), "consegna", obbl=False) or o.consegna
        db.flush()
        return "aggiornato", f"Ordine {oid} aggiornato"
    descr = str(d.get("descrizione") or "—")
    if not oid:
        # senza codice ordine si riconosce un doppione dagli stessi dati già importati dalla stessa fonte
        if db.scalar(select(m.Ordine.id).where(m.Ordine.commessa_id == c.id, m.Ordine.fonte == fonte, m.Ordine.fornitore == forn,
                                               m.Ordine.descr == descr, m.Ordine.importo == imp, m.Ordine.data == dt)):
            return "invariato", f"Ordine di {forn} da {eur(imp)} del {dt:%d/%m/%Y} già importato"
        oid = _nuovo_id_ordine(db, dt.year)
    k = calc(c, cfg_get(db))
    residuo = next(x.residuo for x in k.cats if x.k == cat)
    stato, nota = st, None
    if imp > residuo:
        stato, nota = "Autorizzazione richiesta", f"Supera il residuo della voce {cat} di {eur(imp - max(residuo, 0))}"
    o = m.Ordine(id=oid, commessa=c, fornitore=forn, categoria=cat, descr=descr, importo=imp, data=dt,
                 stato=stato, nota=nota, fonte=fonte, rif_esterno=r.rif_esterno or oid,
                 consegna=_data(d.get("consegna"), "consegna", obbl=False) or (dt + timedelta(days=21) if stato == "Consegnato" else None))
    db.add(o)
    db.flush()
    log(db, chi, c.cod, f"Importato ordine {oid} di {forn} ({eur(imp)})" + (" · in autorizzazione: oltre budget" if nota else ""))
    return "creato", f"Ordine {oid} su {c.cod}, {eur(imp)}" + (" · da autorizzare (oltre budget)" if nota else "")


def _nuovo_id_ordine(db, anno: int) -> str:
    pref = f"ODA-{anno % 100:02d}-"
    ultimo = db.scalar(select(func.max(m.Ordine.id)).where(m.Ordine.id.like(pref + "%")))
    n = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{pref}{n:04d}"


def _fattura_passiva(db, r: Record, fonte, chi):
    d = r.dati
    c = _commessa(db, d["commessa"])
    _aperta(c)
    forn, num = str(d.get("fornitore") or "").strip(), str(d.get("numero") or "").strip()
    if not forn or not num:
        raise Scarta("Fornitore e numero fattura sono obbligatori")
    imp, dt = _importo(d["importo"], positivo=False), _data(d["data"])
    esist = db.scalar(select(m.FatturaPassiva).where(m.FatturaPassiva.fornitore == forn, m.FatturaPassiva.num == num))
    if esist and esist.fonte != fonte:
        raise Scarta(f"Fattura {num} di {forn} già presente")
    cat, oid = _categoria(d.get("categoria")), str(d.get("ordine") or "").strip() or None
    if oid:
        o = db.get(m.Ordine, oid)
        if not o or o.commessa_id != c.id:
            raise Scarta(f"Ordine {oid} non trovato in {c.cod}")
        if nrm(o.fornitore) != nrm(forn):
            raise Scarta(f"L'ordine {oid} è di {o.fornitore}, non di {forn}")
        cat = o.categoria
    if not cat:
        raise Scarta("Categoria mancante o non valida (senza ordine è obbligatoria)")
    f = esist or m.FatturaPassiva(fornitore=forn, num=num, fonte=fonte, rif_esterno=r.rif_esterno)
    f.commessa, f.ordine_id, f.categoria, f.importo, f.data = c, oid, cat, imp, dt
    f.piva_fornitore = d.get("piva_fornitore") or f.piva_fornitore
    f.scadenza = _data(d.get("scadenza"), "scadenza", obbl=False) or f.scadenza
    f.pagamento = _data(d.get("pagamento"), "pagamento", obbl=False) or f.pagamento
    db.add(f)
    # se la stessa fattura era in attesa nella casella SDI, ora è registrata
    sdi = db.scalar(select(m.FatturaSdi).where(m.FatturaSdi.fornitore == forn, m.FatturaSdi.num == num))
    if sdi:
        db.delete(sdi)
    db.flush()
    if not esist:
        log(db, chi, c.cod, f"Importata fattura passiva {num} di {forn} ({eur(imp)})")
    return ("aggiornata" if esist else "creata"), f"Fattura {num} di {forn} su {c.cod}, {eur(imp)} · {cat}"


def _fattura_sdi(db, r: Record, fonte, chi):
    d = r.dati
    forn, num = str(d.get("fornitore") or "").strip(), str(d.get("numero") or "").strip()
    if not forn or not num:
        raise Scarta("Fornitore e numero fattura sono obbligatori")
    if db.scalar(select(m.FatturaPassiva.id).where(m.FatturaPassiva.fornitore == forn, m.FatturaPassiva.num == num)):
        return "invariata", f"Fattura {num} di {forn} già registrata su una commessa"
    f = db.scalar(select(m.FatturaSdi).where(m.FatturaSdi.fornitore == forn, m.FatturaSdi.num == num))
    nuova = f is None
    f = f or m.FatturaSdi(fornitore=forn, num=num, fonte=fonte, rif_esterno=r.rif_esterno)
    f.data, f.importo = _data(d["data"]), _importo(d["importo"], positivo=False)
    f.piva_fornitore, f.descrizione = d.get("piva_fornitore"), d.get("descrizione")
    f.scadenza = _data(d.get("scadenza"), "scadenza", obbl=False)
    f.sdi_id, f.file_name = d.get("sdi_id"), d.get("file")
    oid = d.get("ordine")
    f.rif_ordine = oid if oid and db.get(m.Ordine, oid) else None
    f.rif_commessa = d.get("commessa") or (db.get(m.Ordine, f.rif_ordine).commessa.cod if f.rif_ordine else None)
    db.add(f)
    db.flush()
    if nuova:
        log(db, "Sistema SDI", f.rif_commessa, f"Ricevuta fattura {num} di {forn} ({eur(f.importo)})"
            + (f", abbinata all'ordine {f.rif_ordine}" if f.rif_ordine else ", senza riferimento d'ordine"))
    dove = f"ordine {f.rif_ordine}" if f.rif_ordine else (f"commessa {f.rif_commessa}" if f.rif_commessa else "da abbinare")
    return ("creata" if nuova else "aggiornata"), f"Fattura {num} di {forn}, {eur(f.importo)} → casella SDI ({dove})"


def _rata_libera(c: m.Commessa, importo: float) -> m.Rata | None:
    libere = [p for p in c.piano if not p.fattura_num]
    return next((p for p in libere if abs(p.importo - importo) < 0.01), None)


def _fattura_attiva(db, r: Record, fonte, chi):
    d = r.dati
    num = str(d.get("numero") or "").strip()
    if not num:
        raise Scarta("Numero fattura mancante")
    imp, dt = _importo(d["importo"]), _data(d["data"])
    scad = _data(d.get("scadenza"), "scadenza", obbl=False)
    p = db.scalar(select(m.Rata).where(m.Rata.fattura_num == num))
    if p:
        p.fattura_data, p.fattura_scad = dt, scad or p.fattura_scad
        db.flush()
        return "invariata", f"Fattura {num} già abbinata alla rata {p.codice} di {p.commessa.cod}"
    candidati: list[m.Commessa]
    if d.get("commessa"):
        candidati = [_commessa(db, d["commessa"])]
    else:
        q = select(m.Commessa).where(m.Commessa.stato < 8)
        if d.get("piva_cliente"):
            q = q.where(m.Commessa.piva_cliente == d["piva_cliente"])
        candidati = [c for c in db.scalars(q) if not d.get("cliente") or d.get("piva_cliente") or nrm(c.cliente) == nrm(d["cliente"])]
    abbinate = [(c, p) for c in candidati if (p := _rata_libera(c, imp))]
    if not abbinate:
        raise Scarta(f"Nessuna rata da fatturare di {eur(imp)}" + (f" su {candidati[0].cod}" if len(candidati) == 1 else " per questo cliente"))
    if len(abbinate) > 1:
        raise Scarta("Più rate compatibili: indica la commessa (" + ", ".join(c.cod for c, _ in abbinate) + ")")
    c, p = abbinate[0]
    p.fattura_num, p.fattura_data, p.fattura_fonte = num, dt, fonte
    p.fattura_scad = scad or dt + timedelta(days=cfg_get(db)["ggPag"])
    db.flush()
    log(db, chi, c.cod, f"Emessa fattura {num} ({p.descr}, {eur(imp)})")
    return "abbinata", f"Fattura {num} → {c.cod}, rata «{p.descr}»"


def _rapportino(db, r: Record, fonte, chi):
    d = r.dati
    c = _commessa(db, d["commessa"])
    _aperta(c)
    dt = _data(d["data"])
    ore = p_num(d.get("ore"))
    av = p_num(str(d.get("avanzamento") or "").replace("%", ""))
    if ore is None or ore < 0:
        raise Scarta(f"Ore non valide «{d.get('ore')}»")
    if av is None or not 0 <= av <= 100:
        raise Scarta(f"Avanzamento non valido «{d.get('avanzamento')}» (0-100)")
    chi_r = str(d.get("chi") or c.capo or "")
    esist = db.scalar(select(m.Rapportino).where(m.Rapportino.commessa_id == c.id, m.Rapportino.data == dt, m.Rapportino.chi == chi_r))
    rp = esist or m.Rapportino(commessa=c, data=dt, chi=chi_r, fonte=fonte, rif_esterno=r.rif_esterno)
    rp.ore, rp.avanz, rp.nota = ore, int(av), str(d.get("nota") or "")
    db.add(rp)
    db.flush()
    if not esist:
        log(db, chi, c.cod, f"Rapportino del {dt:%d/%m/%Y}: {ore:g} h, avanzamento {int(av)}%")
    return ("aggiornato" if esist else "creato"), f"Rapportino {c.cod} del {dt:%d/%m/%Y}: {ore:g} h, {int(av)}%"


def _movimento(db, r: Record, fonte, chi):
    d = r.dati
    dt = _data(d["data"])
    imp = p_num(d.get("importo"))
    if not imp:
        raise Scarta(f"Importo non valido «{d.get('importo')}»")
    causale = str(d.get("causale") or "")
    rif = r.rif_esterno or f"{dt}|{imp:.2f}|{causale[:80]}"
    if db.scalar(select(m.MovimentoBanca.id).where(m.MovimentoBanca.fonte == fonte, m.MovimentoBanca.rif_esterno == rif)):
        return "invariato", f"Movimento del {dt:%d/%m/%Y} di {eur(imp)} già importato"
    mv = m.MovimentoBanca(data=dt, importo=imp, causale=causale, controparte=d.get("controparte"), iban=d.get("iban"), fonte=fonte, rif_esterno=rif)
    db.add(mv)
    cn = nrm(causale)
    if imp > 0:
        aperte = list(db.scalars(select(m.Rata).where(m.Rata.fattura_num.is_not(None), m.Rata.incasso_data.is_(None))))
        per_num = [p for p in aperte if nrm(p.fattura_num) and nrm(p.fattura_num) in cn]
        per_imp = [p for p in aperte if abs(p.importo - imp) < 0.01]
        p = per_num[0] if len(per_num) == 1 else (per_imp[0] if len(per_imp) == 1 else None)
        if p and abs(p.importo - imp) >= 0.01:
            mv.abbinamento = f"Causale cita {p.fattura_num} ma l'importo è diverso ({eur(p.importo)}): da verificare"
            db.flush()
            return "da verificare", f"Accredito {eur(imp)} del {dt:%d/%m/%Y}: {mv.abbinamento}"
        if p:
            p.incasso_data, p.incasso_fonte, mv.rata_id = dt, fonte, p.id
            mv.abbinamento = f"Incasso fattura {p.fattura_num} ({'numero in causale' if per_num else 'stesso importo'})"
            db.flush()
            log(db, "Banca", p.commessa.cod, f"Incassata fattura {p.fattura_num} ({eur(imp)})")
            return "abbinato", f"Accredito {eur(imp)} → incasso {p.fattura_num} di {p.commessa.cod}"
        mv.abbinamento = "Nessuna fattura aperta corrispondente" if not per_imp else "Più fatture con lo stesso importo"
        db.flush()
        return "non abbinato", f"Accredito {eur(imp)} del {dt:%d/%m/%Y}: {mv.abbinamento.lower()}"
    da_pagare = [f for f in db.scalars(select(m.FatturaPassiva).where(m.FatturaPassiva.pagamento.is_(None))) if nrm(f.num) and nrm(f.num) in cn]
    if len(da_pagare) == 1 and abs(da_pagare[0].importo + imp) < 0.01:
        f = da_pagare[0]
        f.pagamento, mv.fattura_passiva_id = dt, f.id
        mv.abbinamento = f"Pagamento fattura {f.num} di {f.fornitore}"
        db.flush()
        return "abbinato", f"Addebito {eur(imp)} → pagata {f.num} di {f.fornitore}"
    mv.abbinamento = "Nessuna fattura passiva corrispondente"
    db.flush()
    return "non abbinato", f"Addebito {eur(imp)} del {dt:%d/%m/%Y}: nessuna fattura passiva corrispondente"


GESTORI = {"commessa": _commessa_rec, "ordine": _ordine, "fattura_passiva": _fattura_passiva, "fattura_sdi": _fattura_sdi,
           "fattura_attiva": _fattura_attiva, "rapportino": _rapportino, "movimento": _movimento}


def importa(db: Session, lettura: Lettura, *, connettore: str, fonte: str, origine: str, tipo: str, chi: str, salva: bool) -> dict:
    righe = [{"riga": e["riga"], "esito": "errore", "m": e["m"]} for e in lettura.errori]
    tx = db.begin_nested()
    try:
        for r in lettura.records:
            sp = db.begin_nested()
            try:
                azione, msg = GESTORI[r.tipo](db, r, fonte, chi)
                sp.commit()
                righe.append({"riga": r.riga, "tipo": r.tipo, "esito": azione, "m": msg})
            except Scarta as e:
                sp.rollback()
                righe.append({"riga": r.riga, "tipo": r.tipo, "esito": "errore", "m": str(e)})
        n_err = sum(1 for x in righe if x["esito"] == "errore")
        esito = {"righe": righe, "ok": len(righe) - n_err, "errori": n_err,
                 "riepilogo": {k: sum(1 for x in righe if x["esito"] == k) for k in sorted({x["esito"] for x in righe})}}
        if salva:
            db.add(m.Importazione(connettore=connettore, tipo=tipo, origine=origine, utente=chi,
                                  righe_ok=esito["ok"], righe_err=n_err, esito=esito))
            log(db, chi, None, f"Importazione da {origine}: {esito['ok']} righe acquisite, {n_err} scartate")
            tx.commit()
            db.commit()
        else:
            tx.rollback()
            db.rollback()
        return esito
    except Exception:
        tx.rollback()
        db.rollback()
        raise
