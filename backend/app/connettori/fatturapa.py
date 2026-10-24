"""Connettore FatturaPA: file XML dello SDI (anche firmati .p7m o raccolti in uno .zip).

Se il cedente è l'azienda (P.IVA in RC_PIVA_AZIENDA) la fattura è attiva e va abbinata a una rata
del piano di fatturazione; altrimenti è passiva e finisce nella casella "Fatture SDI" da registrare,
con ordine e commessa già suggeriti quando il fornitore li ha indicati.
"""
import base64
import io
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from ..config import settings
from .base import Connettore, Lettura, Record, p_data, p_num, trova_commessa, trova_ordine

NOTE_CREDITO = {"TD04", "TD08"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        el.tag = _local(el.tag)
    return root


def _t(el: ET.Element | None, path: str) -> str:
    if el is None:
        return ""
    x = el.find(path)
    return (x.text or "").strip() if x is not None and x.text else ""


def estrai_da_p7m(dati: bytes) -> bytes:
    """Restituisce l'XML contenuto in una busta CAdES (.p7m), anche se codificata in base64."""
    if not dati.lstrip().startswith(b"0") and re.fullmatch(rb"[A-Za-z0-9+/=\s]+", dati[:200] or b"x"):
        try:
            dati = base64.b64decode(dati)
        except ValueError:
            pass
    if shutil.which("openssl"):
        for cmd in (["openssl", "cms", "-verify", "-noverify", "-inform", "DER", "-binary"],
                    ["openssl", "smime", "-verify", "-noverify", "-inform", "DER"]):
            r = subprocess.run(cmd, input=dati, capture_output=True, timeout=20)
            if r.returncode == 0 and b"FatturaElettronica" in r.stdout:
                return r.stdout
    # Ripiego: l'XML è quasi sempre in chiaro dentro la busta
    i = dati.find(b"<?xml")
    if i < 0:
        i = dati.find(b"<")
    j = dati.rfind(b"FatturaElettronica>")
    if i < 0 or j < 0:
        raise ValueError("busta .p7m non leggibile")
    return dati[i:j + len(b"FatturaElettronica>")]


def _soggetto(el: ET.Element | None) -> tuple[str, str]:
    ana = el.find("DatiAnagrafici") if el is not None else None
    piva = _t(ana, "IdFiscaleIVA/IdPaese") + _t(ana, "IdFiscaleIVA/IdCodice")
    nome = _t(ana, "Anagrafica/Denominazione") or f"{_t(ana, 'Anagrafica/Nome')} {_t(ana, 'Anagrafica/Cognome')}".strip()
    return nome, piva


def _norm_piva(p: str) -> str:
    p = re.sub(r"\s", "", p.upper())
    return p if p[:2].isalpha() else "IT" + p


def leggi_fattura(xml: bytes, nome_file: str) -> list[Record]:
    root = _strip_ns(ET.fromstring(xml))
    if root.tag != "FatturaElettronica":
        raise ValueError("non è una FatturaPA")
    head = root.find("FatturaElettronicaHeader")
    sdi_id = _t(head, "DatiTrasmissione/ProgressivoInvio")
    ced_nome, ced_piva = _soggetto(head.find("CedentePrestatore") if head is not None else None)
    ces_nome, ces_piva = _soggetto(head.find("CessionarioCommittente") if head is not None else None)
    attiva = _norm_piva(ced_piva) == _norm_piva(settings.piva_azienda)
    out = []
    for n, body in enumerate(root.findall("FatturaElettronicaBody"), start=1):
        gen = body.find("DatiGenerali/DatiGeneraliDocumento")
        tipo_doc = _t(gen, "TipoDocumento")
        numero, data = _t(gen, "Numero"), p_data(_t(gen, "Data"))
        imponibile = sum(p_num(_t(r, "ImponibileImporto")) or 0 for r in body.findall("DatiBeniServizi/DatiRiepilogo"))
        if not imponibile:
            imponibile = p_num(_t(gen, "ImportoTotaleDocumento")) or 0
        if tipo_doc in NOTE_CREDITO:
            imponibile = -abs(imponibile)
        causale = " ".join(c.text or "" for c in gen.findall("Causale")) if gen is not None else ""
        righe = " ".join(_t(li, "Descrizione") for li in body.findall("DatiBeniServizi/DettaglioLinee"))
        oda = [(_t(o, "IdDocumento"), _t(o, "CodiceCommessaConvenzione")) for o in body.findall("DatiGenerali/DatiOrdineAcquisto")]
        rif_ordine = next((trova_ordine(i) or i for i, _ in oda if i), None) or trova_ordine(causale + " " + righe)
        rif_commessa = next((trova_commessa(c) or c for _, c in oda if c), None) or trova_commessa(causale + " " + righe)
        scad = p_data(_t(body, "DatiPagamento/DettaglioPagamento/DataScadenzaPagamento"))
        pos = nome_file + (f" (documento {n})" if n > 1 else "")
        if attiva:
            out.append(Record("fattura_attiva", {"numero": numero, "data": data, "importo": imponibile, "cliente": ces_nome,
                                                  "piva_cliente": ces_piva, "scadenza": scad, "commessa": rif_commessa,
                                                  "causale": causale}, pos, rif_esterno=f"{ced_piva}|{numero}|{data}"))
        else:
            out.append(Record("fattura_sdi", {"fornitore": ced_nome, "piva_fornitore": ced_piva, "numero": numero, "data": data,
                                               "importo": imponibile, "scadenza": scad, "ordine": rif_ordine, "commessa": rif_commessa,
                                               "descrizione": (causale + " " + righe).strip()[:2000], "sdi_id": sdi_id or None,
                                               "file": nome_file}, pos, rif_esterno=f"{ced_piva}|{numero}|{data}"))
    return out


class FatturaPAConnettore(Connettore):
    nome = "fatturapa"
    etichetta = "Fatture elettroniche SDI"
    descrizione = "File FatturaPA .xml o .xml.p7m (anche più file in uno .zip) scaricati dal cassetto fiscale o dall'intermediario."
    estensioni = [".xml", ".p7m", ".zip"]
    tipi = ["fattura_sdi", "fattura_attiva"]

    def leggi(self, contenuto: bytes, nome_file: str, tipo: str | None = None) -> Lettura:
        out = Lettura()
        file = []
        if nome_file.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(contenuto)) as z:
                    file = [(n, z.read(n)) for n in z.namelist() if n.lower().endswith((".xml", ".p7m")) and not n.startswith("__MACOSX")]
            except zipfile.BadZipFile:
                out.errore(nome_file, "Archivio .zip non valido")
                return out
        else:
            file = [(nome_file, contenuto)]
        for nome, dati in file:
            try:
                if nome.lower().endswith(".p7m"):
                    dati = estrai_da_p7m(dati)
                out.records.extend(leggi_fattura(dati, nome))
            except (ET.ParseError, ValueError, subprocess.SubprocessError) as e:
                out.errore(nome, f"File non leggibile come FatturaPA: {e}")
        return out
