"""Contratto comune dei connettori.

Un connettore legge una fonte (file, database, servizio) e restituisce `Record` normalizzati.
Non scrive mai nel database: validazione e salvataggio li fa `app.importazione`, uguali per tutte le fonti.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

# Tipi di record che l'importazione sa trattare, con i campi obbligatori
TIPI = {
    "commessa": {"l": "Commesse", "req": ["cod", "cliente"],
                 "opt": ["oggetto", "sistema", "cantiere", "commerciale", "capo", "contratto", "ricavo", "piva_cliente", "stato"]},
    "ordine": {"l": "Ordini fornitori", "req": ["commessa", "fornitore", "categoria", "importo", "data"],
               "opt": ["descrizione", "stato", "id", "consegna"]},
    "fattura_passiva": {"l": "Fatture passive", "req": ["commessa", "fornitore", "numero", "data", "importo"],
                        "opt": ["ordine", "categoria", "piva_fornitore", "scadenza", "pagamento"]},
    "fattura_attiva": {"l": "Fatture emesse", "req": ["numero", "data", "importo"],
                       "opt": ["commessa", "cliente", "piva_cliente", "scadenza", "rata", "causale"]},
    "rapportino": {"l": "Rapportini di cantiere", "req": ["commessa", "data", "ore", "avanzamento"], "opt": ["chi", "nota"]},
    "movimento": {"l": "Movimenti bancari", "req": ["data", "importo"], "opt": ["causale", "controparte", "iban", "rif"]},
    "fattura_sdi": {"l": "Fatture ricevute da SDI", "req": ["fornitore", "numero", "data", "importo"],
                    "opt": ["piva_fornitore", "scadenza", "ordine", "commessa", "descrizione", "sdi_id", "file"]},
}


@dataclass
class Record:
    tipo: str
    dati: dict
    riga: str  # posizione nella fonte, per i messaggi d'errore (es. "riga 4", "fattura.xml")
    rif_esterno: str | None = None


@dataclass
class Lettura:
    records: list[Record] = field(default_factory=list)
    errori: list[dict] = field(default_factory=list)  # errori di lettura della fonte: {"riga":..., "m":...}

    def errore(self, riga: str, msg: str):
        self.errori.append({"riga": riga, "m": msg})


class Connettore:
    nome: str = ""
    etichetta: str = ""
    descrizione: str = ""
    estensioni: list[str] = []
    tipi: list[str] = []  # tipi di record che produce
    serve_tipo: bool = False  # True se l'utente deve dire che cosa contiene il file

    def leggi(self, contenuto: bytes, nome_file: str, tipo: str | None = None) -> Lettura:  # pragma: no cover
        raise NotImplementedError

    def info(self) -> dict:
        return {"nome": self.nome, "etichetta": self.etichetta, "descrizione": self.descrizione,
                "estensioni": self.estensioni, "tipi": self.tipi, "serve_tipo": self.serve_tipo}


# ---------- utilità di normalizzazione condivise ----------

def nrm(x) -> str:
    s = unicodedata.normalize("NFD", str(x or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(ch for ch in s if not unicodedata.combining(ch)))


def p_data(x) -> date | None:
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    s = str(x).strip()
    mt = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", s)
    if mt:
        s = f"{mt[3]}-{int(mt[2]):02d}-{int(mt[1]):02d}"
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def p_num(x) -> float | None:
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = re.sub(r"[€\s]", "", str(x))
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


RE_ODA = re.compile(r"\bODA[-\s]?\d{2}[-\s]?\d{4}\b", re.I)
RE_COMMESSA = re.compile(r"\bC[-\s]?\d{4}[-\s]?\d{3}\b", re.I)


def trova_ordine(testo: str) -> str | None:
    mt = RE_ODA.search(testo or "")
    if not mt:
        return None
    digits = re.sub(r"\D", "", mt[0])
    return f"ODA-{digits[:2]}-{digits[2:]}"


def trova_commessa(testo: str) -> str | None:
    mt = RE_COMMESSA.search(testo or "")
    if not mt:
        return None
    digits = re.sub(r"\D", "", mt[0])
    return f"C-{digits[:4]}-{digits[4:]}"
