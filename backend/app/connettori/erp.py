"""Connettore gestionale/ERP: legge direttamente dal database del gestionale (query SQL) o dalle sue API REST.

Le connessioni si descrivono in `backend/fonti.yaml` (vedi `fonti.example.yaml`). Ogni query o endpoint
deve restituire colonne con i nomi standard del tipo di record (es. per gli ordini: id, commessa,
fornitore, categoria, descrizione, importo, data, stato): si rinominano nella query con AS, oppure
con la sezione `campi` per le API. Le password non stanno nel file: si leggono da variabili d'ambiente.
"""
import os
import re
from dataclasses import dataclass, field

import httpx
import yaml
from sqlalchemy import create_engine, text

from ..config import BASE_DIR, settings
from .base import TIPI, Lettura, Record

RIF = {"ordine": "id", "commessa": "cod", "fattura_passiva": "numero", "fattura_attiva": "numero", "movimento": "rif", "rapportino": "id"}


def _env(s: str) -> str:
    """Sostituisce ${VAR} con il valore della variabile d'ambiente."""
    return re.sub(r"\$\{(\w+)\}", lambda mt: os.environ.get(mt[1], ""), s)


@dataclass
class FonteErp:
    nome: str
    etichetta: str
    tipo: str = "sql"  # sql | rest
    url: str = ""
    query: dict[str, str] = field(default_factory=dict)
    base_url: str = ""
    header: dict[str, str] = field(default_factory=dict)
    endpoint: dict[str, str] = field(default_factory=dict)
    campi: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def tipi(self) -> list[str]:
        return list(self.query or self.endpoint)

    def info(self) -> dict:
        dove = re.sub(r"//[^@/]*@", "//***@", self.url) if self.tipo == "sql" else self.base_url
        return {"nome": self.nome, "etichetta": self.etichetta, "tipo": self.tipo, "dove": dove, "tipi": self.tipi}

    def leggi(self, tipi: list[str] | None = None) -> Lettura:
        out = Lettura()
        for tipo in tipi or self.tipi:
            if tipo not in TIPI:
                out.errore(tipo, "Tipo di record sconosciuto")
                continue
            try:
                righe = self._sql(tipo) if self.tipo == "sql" else self._rest(tipo)
            except Exception as e:
                out.errore(tipo, f"Lettura da {self.etichetta} non riuscita: {e}")
                continue
            chiave = RIF.get(tipo)
            for n, r in enumerate(righe, start=1):
                r = {k.lower(): v for k, v in r.items()}
                rif = r.get(chiave) if chiave else None
                if tipo in ("fattura_passiva", "fattura_attiva") and rif:
                    rif = f"{r.get('fornitore') or r.get('cliente') or ''}|{rif}"
                out.records.append(Record(tipo, r, f"{tipo} {n}", rif_esterno=str(rif) if rif else None))
        return out

    def _sql(self, tipo: str) -> list[dict]:
        url = _env(self.url)
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            url = "sqlite:///" + str(BASE_DIR / url.removeprefix("sqlite:///"))
        eng = create_engine(url)
        try:
            with eng.connect() as cn:
                return [dict(r._mapping) for r in cn.execute(text(self.query[tipo]))]
        finally:
            eng.dispose()

    def _rest(self, tipo: str) -> list[dict]:
        h = {k: _env(v) for k, v in self.header.items()}
        r = httpx.get(_env(self.base_url).rstrip("/") + self.endpoint[tipo], headers=h, timeout=60)
        r.raise_for_status()
        dati = r.json()
        if isinstance(dati, dict):
            dati = next((v for v in dati.values() if isinstance(v, list)), [])
        mappa = self.campi.get(tipo, {})  # campo standard -> campo dell'API
        return [{std: x.get(src) for std, src in mappa.items()} | {k: v for k, v in x.items() if k not in mappa.values()} for x in dati]


def carica_fonti() -> list[FonteErp]:
    p = settings.fonti_file
    if not p.exists():
        return []
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return [FonteErp(**f) for f in cfg.get("erp", [])]


def fonte(nome: str) -> FonteErp | None:
    return next((f for f in carica_fonti() if f.nome == nome), None)
