"""Copia tutti i dati da un database a un altro, per esempio dal SQLite del portatile al PostgreSQL del server.

Uso (sul server, dentro il container):
    python scripts/trasferisci_dati.py --da sqlite:////import/registro.db
La destinazione è il database dell'applicazione (RC_DATABASE_URL), oppure --a <url>.
Se la destinazione contiene già dati si ferma, a meno di --sovrascrivi (che li cancella).
"""
import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import models  # noqa: E402,F401  (registra le tabelle)
from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--da", required=True, help="database di origine, es. sqlite:////import/registro.db")
    ap.add_argument("--a", default=settings.database_url, help="database di destinazione (default: quello dell'app)")
    ap.add_argument("--sovrascrivi", action="store_true", help="cancella i dati già presenti nella destinazione")
    a = ap.parse_args()

    src, dst = create_engine(a.da), create_engine(a.a)
    tabelle_src = set(inspect(src).get_table_names())
    Base.metadata.create_all(dst)
    ordinate = [t for t in Base.metadata.sorted_tables if t.name in tabelle_src and t.name != "sessioni"]

    with dst.begin() as cd:
        piene = [t.name for t in ordinate if cd.execute(select(func.count()).select_from(t)).scalar()]
        if piene and not a.sovrascrivi:
            sys.exit(f"La destinazione contiene già dati ({', '.join(piene)}). Usa --sovrascrivi per sostituirli.")
        for t in reversed(Base.metadata.sorted_tables):
            cd.execute(t.delete())
        with src.connect() as cs:
            for t in ordinate:
                colonne_src = {c["name"] for c in inspect(src).get_columns(t.name)}
                cols = [c for c in t.columns if c.name in colonne_src]
                righe = [dict(r._mapping) for r in cs.execute(select(*[t.c[c.name] for c in cols]))]
                if righe:
                    cd.execute(t.insert(), righe)
                print(f"  {t.name:<18} {len(righe):>6} righe")
        if dst.dialect.name == "postgresql":  # i contatori degli id ripartono dopo l'ultimo copiato
            for t in ordinate:
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and pk[0].autoincrement is not False and str(pk[0].type) == "INTEGER":
                    cd.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', '{pk[0].name}'), "
                                    f"COALESCE((SELECT MAX({pk[0].name}) FROM {t.name}), 0) + 1, false)"))
    print("Trasferimento completato. Gli utenti dovranno rifare l'accesso.")


if __name__ == "__main__":
    main()
