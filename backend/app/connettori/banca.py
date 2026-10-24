"""Connettore estratti conto: CAMT.053 (XML ISO 20022) o CSV/Excel esportato dall'home banking.

I movimenti in entrata vengono poi abbinati alle fatture emesse ancora da incassare, quelli in uscita
alle fatture passive da pagare (vedi app.importazione).
"""
import xml.etree.ElementTree as ET

from .base import Connettore, Lettura, Record, nrm, p_data, p_num
from .tabelle import leggi_righe, mappa_colonne


def _strip(root):
    for el in root.iter():
        el.tag = el.tag.rsplit("}", 1)[-1]
    return root


def _t(el, path):
    x = el.find(path) if el is not None else None
    return (x.text or "").strip() if x is not None and x.text else ""


def leggi_camt(xml: bytes, nome_file: str, out: Lettura):
    root = _strip(ET.fromstring(xml))
    stmts = root.findall(".//Stmt") or root.findall(".//Rpt")
    if not stmts:
        raise ValueError("nessun estratto conto (Stmt) nel file")
    for st in stmts:
        iban = _t(st, "Acct/Id/IBAN")
        for n, e in enumerate(st.findall("Ntry"), start=1):
            imp = p_num(_t(e, "Amt"))
            if imp is None:
                out.errore(f"{nome_file} movimento {n}", "Importo mancante")
                continue
            if _t(e, "CdtDbtInd") == "DBIT":
                imp = -imp
            data = p_data(_t(e, "BookgDt/Dt") or _t(e, "BookgDt/DtTm") or _t(e, "ValDt/Dt"))
            causale = " ".join(x.text or "" for x in e.findall(".//RmtInf/Ustrd")) or _t(e, "AddtlNtryInf")
            contro = _t(e, ".//RltdPties/Dbtr/Nm") if imp > 0 else _t(e, ".//RltdPties/Cdtr/Nm")
            rif = _t(e, "AcctSvcrRef") or _t(e, "NtryRef") or _t(e, ".//Refs/EndToEndId")
            out.records.append(Record("movimento", {"data": data, "importo": imp, "causale": causale.strip(), "controparte": contro or None, "iban": iban},
                                      f"{nome_file} movimento {n}", rif_esterno=rif or None))


def leggi_csv(contenuto: bytes, nome_file: str, out: Lettura):
    righe = leggi_righe(contenuto, nome_file)
    if len(righe) < 2:
        out.errore("file", "Servono la riga delle intestazioni e almeno un movimento")
        return
    ix = mappa_colonne(righe[0], ["data", "importo", "causale", "controparte", "rif"])
    hd = [nrm(h) for h in righe[0]]
    entrate = next((hd.index(x) for x in ("avere", "entrate", "accrediti") if x in hd), None)
    uscite = next((hd.index(x) for x in ("dare", "uscite", "addebiti") if x in hd), None)
    if "data" not in ix or ("importo" not in ix and entrate is None):
        out.errore("riga 1", "Servono almeno le colonne data e importo (oppure dare/avere)")
        return
    for n, r in enumerate(righe[1:], start=2):
        g = lambda i: r[i] if i is not None and i < len(r) else None  # noqa: E731
        if "importo" in ix:
            imp = p_num(g(ix["importo"]))
        else:
            imp = (p_num(g(entrate)) or 0) - abs(p_num(g(uscite)) or 0)
        out.records.append(Record("movimento", {"data": p_data(g(ix["data"])), "importo": imp, "causale": str(g(ix.get("causale")) or ""),
                                                "controparte": g(ix.get("controparte"))}, f"riga {n}",
                                  rif_esterno=str(g(ix["rif"])) if ix.get("rif") is not None and g(ix["rif"]) else None))


class BancaConnettore(Connettore):
    nome = "banca"
    etichetta = "Estratto conto bancario"
    descrizione = "CAMT.053 (.xml) o export CSV/Excel dell'home banking con data, importo (o dare/avere) e causale."
    estensioni = [".xml", ".csv", ".xlsx", ".txt"]
    tipi = ["movimento"]

    def leggi(self, contenuto: bytes, nome_file: str, tipo: str | None = None) -> Lettura:
        out = Lettura()
        try:
            if nome_file.lower().endswith(".xml") or contenuto.lstrip()[:5] == b"<?xml":
                leggi_camt(contenuto, nome_file, out)
            else:
                leggi_csv(contenuto, nome_file, out)
        except (ET.ParseError, ValueError) as e:
            out.errore(nome_file, f"Estratto conto non leggibile: {e}")
        return out
