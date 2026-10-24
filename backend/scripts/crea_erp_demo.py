"""Crea data/erp_demo.db, un finto database di gestionale per provare il connettore ERP.

Le tabelle hanno di proposito nomi e colonne "da gestionale" (non quelli del registro):
è la query in fonti.yaml a rinominarle.  Uso:  python scripts/crea_erp_demo.py
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "erp_demo.db"


def main():
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    cn = sqlite3.connect(DB)
    cn.executescript("""
    CREATE TABLE MG_ORDFOR (NUMORD TEXT PRIMARY KEY, CDC TEXT, RAGSOC_FOR TEXT, CLASSE TEXT, DESART TEXT, IMPNETTO REAL, DTORD TEXT, STATO_EVAS TEXT);
    INSERT INTO MG_ORDFOR VALUES
      ('ODA-26-0170','C-2026-027','Elettro Quadri Brianza S.r.l.','QE','Quadro comando SEFFC 6 zone',13200,'2026-10-21','A'),
      ('ODA-26-0171','C-2026-027','Trasporti Ghezzi S.n.c.','TR','Trasporto quadro',650,'2026-10-21','A'),
      ('ODA-26-0172','C-2026-031','Elettro Quadri Brianza S.r.l.','QE','Centrale di controllo hotel',10900,'2026-10-22','E');
    CREATE TABLE CO_FATFOR (PROT INTEGER PRIMARY KEY, NUMDOC TEXT, RAGSOC_FOR TEXT, PIVA TEXT, CDC TEXT, NUMORD TEXT, IMPONIBILE REAL, DTDOC TEXT, DTSCAD TEXT);
    INSERT INTO CO_FATFOR VALUES
      (9001,'FT 2026/470','Elettro Quadri Brianza S.r.l.','IT03332220966','C-2026-031','ODA-26-0172',10900,'2026-10-23','2026-12-22');
    CREATE TABLE TAB_CLASSI (CLASSE TEXT PRIMARY KEY, DESCR TEXT);
    INSERT INTO TAB_CLASSI VALUES ('MAT','Materiali'),('QE','Quadri elettrici'),('TR','Trasporti'),('SUB','Posa e subappalti');
    """)
    cn.commit()
    cn.close()
    print(f"Creato {DB}")


if __name__ == "__main__":
    main()
