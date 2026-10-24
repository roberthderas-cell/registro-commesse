"""Dati di esempio del prototipo, caricati al primo avvio se il database è vuoto."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .dominio import CATS, CONFIG_DEFAULT, DOCS, ROLES, doc_dovuto

DOCF = {"contratto": "Contratto_firmato", "progetto": "Progetto_esecutivo", "pos": "POS_cantiere", "durc": "DURC_subappaltatori",
        "collaudo": "Verbale_collaudo", "dichimp": "DICH_IMP_DM37-08", "manuale": "Manuale_uso_manutenzione"}
OGGI_DEMO = date(2026, 10, 19)


def d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def B(mat, qua, tra, pos, mo):
    return dict(zip(CATS, (mat, qua, tra, pos, mo)))


def F(num, data, scad, inc=None):
    return {"fattura_num": num, "fattura_data": d(data), "fattura_scad": d(scad), "incasso_data": d(inc)}


COMMESSE = [
    dict(cod="C-2026-018", cliente="Logistica Padana S.p.A.", oggetto="Evacuazione naturale di fumo e calore, magazzino", sistema="ENFC", cantiere="Lodi (LO)",
         commerciale="L. Bianchi", capo="M. Ferrari", contratto="2026-03-12", stato=4, ricavo=186400, budget=B(62000, 19000, 3000, 26000, 18000),
         varianti=[("V1", "4 evacuatori aggiuntivi zona carico", 14200, "proposta", "L. Bianchi", "2026-10-13")],
         piano=[("R1", "Anticipo 30% alla firma", 55920, "contratto", F("FA 2026/112", "2026-03-20", "2026-04-30", "2026-04-15")),
                ("R2", "SAL 1, 40%", 74560, "avanz50", {}), ("R3", "Saldo 30% a collaudo", 55920, "collaudo", {})],
         ordini=[("ODA-26-0138", "Elettro Quadri Brianza S.r.l.", "Quadri elettrici", "Centrale di comando e controllo 8 linee", 18600, "2026-05-06", "Consegnato", None),
                 ("ODA-26-0139", "Trasporti Ghezzi S.n.c.", "Trasporti", "Trasporto evacuatori in cantiere", 2400, "2026-05-08", "Consegnato", None),
                 ("ODA-26-0141", "Metalfer Lombarda S.r.l.", "Materiali", "24 evacuatori naturali EFC 2,0 × 1,5 m", 54200, "2026-05-14", "Consegnato", None),
                 ("ODA-26-0144", "Montaggi Adda S.r.l.", "Posa e subappalti", "Posa in copertura, subappalto a SAL", 22000, "2026-07-01", "Ordinato", None)],
         fp=[("FT 2026/388", "Elettro Quadri Brianza S.r.l.", "ODA-26-0138", "Quadri elettrici", 18600, "2026-06-30"),
             ("FT-812", "Trasporti Ghezzi S.n.c.", "ODA-26-0139", "Trasporti", 2400, "2026-06-12"),
             ("27/26", "Montaggi Adda S.r.l.", "ODA-26-0144", "Posa e subappalti", 11000, "2026-09-30")],
         rapportini=[("2026-09-18", "M. Ferrari", 120, 20, "Tracciamento e posa telai"), ("2026-09-25", "M. Ferrari", 110, 35, "Posa 6 evacuatori"),
                     ("2026-10-02", "M. Ferrari", 100, 48, "Posa 6 evacuatori, cablaggio linea 1"), ("2026-10-09", "M. Ferrari", 90, 60, "Posa 14 evacuatori su 24 completata")]),
    dict(cod="C-2026-022", cliente="Impresa Costruzioni Brera S.r.l.", oggetto="Sistema a pressione differenziale vani scala, residenza", sistema="PDS", cantiere="Milano, Isola",
         commerciale="L. Bianchi", capo="D. Colombo", contratto="2026-05-28", stato=3, ricavo=94800, budget=B(26000, 15000, 2000, 14000, 9500), varianti=[],
         piano=[("R1", "Anticipo 20% alla firma", 18960, "contratto", F("FA 2026/131", "2026-06-05", "2026-07-31", "2026-07-29")),
                ("R2", "SAL 1, 50%", 47400, "avanz50", {}), ("R3", "Saldo 30% a collaudo", 28440, "collaudo", {})],
         ordini=[("ODA-26-0149", "Elettro Quadri Brianza S.r.l.", "Quadri elettrici", "Quadro PDS con inverter", 14200, "2026-09-22", "Ordinato", None),
                 ("ODA-26-0150", "Aria Tecnica Veneta S.p.A.", "Materiali", "Ventilatori di pressurizzazione e serrande", 31900, "2026-10-15", "Autorizzazione richiesta",
                  "Supera il residuo della voce Materiali di 5.900 €"),
                 ("ODA-26-0152", "Trasporti Ghezzi S.n.c.", "Trasporti", "Trasporto quadro e ventilatori", 1100, "2026-10-01", "Ordinato", None)],
         fp=[], rapportini=[]),
    dict(cod="C-2026-009", cliente="Polo Fieristico Emiliano S.p.A.", oggetto="Barriere al fumo e al fuoco, padiglione 4", sistema="Barriere", cantiere="Bologna (BO)",
         commerciale="S. Galli", capo="M. Ferrari", contratto="2026-01-20", stato=5, ricavo=241000, budget=B(98000, 12000, 5000, 34000, 23000),
         varianti=[("V1", "Barriere aggiuntive campata 4C", 18500, "approvata", "S. Galli", "2026-06-10")],
         piano=[("R1", "Anticipo 20% alla firma", 48200, "contratto", F("FA 2026/041", "2026-01-30", "2026-03-31", "2026-03-27")),
                ("R2", "SAL 1, 50%", 120500, "avanz50", F("FA 2026/158", "2026-07-30", "2026-09-28")),
                ("R3", "Saldo 30% a collaudo", 72300, "collaudo", {}), ("RV1", "Variante V1, campata 4C", 18500, "collaudo", {})],
         ordini=[("ODA-26-0102", "Tessili Tecnici Ignifughi S.r.l.", "Materiali", "Barriere al fumo DH60 su misura", 104300, "2026-02-12", "Consegnato", "Autorizzato oltre budget il 13/02/2026"),
                 ("ODA-26-0103", "Elettro Quadri Brianza S.r.l.", "Quadri elettrici", "Centrale barriere e alimentatori", 11800, "2026-02-14", "Consegnato", None),
                 ("ODA-26-0104", "Trasporti Ghezzi S.n.c.", "Trasporti", "Trasporti in tre consegne", 5600, "2026-02-20", "Consegnato", None),
                 ("ODA-26-0110", "Montaggi Adda S.r.l.", "Posa e subappalti", "Montaggio barriere, subappalto", 36500, "2026-03-15", "Consegnato", None)],
         fp=[("2026/0211", "Tessili Tecnici Ignifughi S.r.l.", "ODA-26-0102", "Materiali", 104300, "2026-04-10"),
             ("FT 2026/201", "Elettro Quadri Brianza S.r.l.", "ODA-26-0103", "Quadri elettrici", 11800, "2026-04-02"),
             ("FT-640", "Trasporti Ghezzi S.n.c.", "ODA-26-0104", "Trasporti", 5600, "2026-05-05"),
             ("14/26", "Montaggi Adda S.r.l.", "ODA-26-0110", "Posa e subappalti", 36500, "2026-08-31")],
         rapportini=[("2026-05-29", "M. Ferrari", 180, 25, "Montaggio guide e cassonetti"), ("2026-06-26", "M. Ferrari", 200, 55, "Barriere campate 1-3"),
                     ("2026-07-31", "M. Ferrari", 210, 85, "Campata 4C in variante"), ("2026-09-11", "M. Ferrari", 170, 100, "Fine lavori, prove di discesa eseguite")]),
    dict(cod="C-2026-027", cliente="Retail Nord S.p.A.", oggetto="Evacuazione forzata di fumo e calore, galleria commerciale", sistema="SEFFC", cantiere="Brescia (BS)",
         commerciale="S. Galli", capo="", contratto="2026-09-30", stato=2, ricavo=132600, budget=B(44000, 14000, 2500, 18000, 12500), varianti=[],
         piano=[("R1", "Anticipo 20% alla firma", 26520, "contratto", {}), ("R2", "SAL 1, 50%", 66300, "avanz50", {}), ("R3", "Saldo 30% a collaudo", 39780, "collaudo", {})],
         ordini=[], fp=[], rapportini=[]),
    dict(cod="C-2026-004", cliente="Farmaceutica Ticino S.r.l.", oggetto="Ventilazione naturale reparto produzione", sistema="Ventilazione", cantiere="Varese (VA)",
         commerciale="L. Bianchi", capo="D. Colombo", contratto="2026-01-08", stato=7, collaudo_ok=True, collaudo_data="2026-07-08", ricavo=78300,
         budget=B(25000, 8000, 1500, 10000, 7500), varianti=[],
         piano=[("R1", "Anticipo 30% alla firma", 23490, "contratto", F("FA 2026/012", "2026-01-15", "2026-02-28", "2026-02-26")),
                ("R2", "Saldo 70% a collaudo", 54810, "collaudo", F("FA 2026/149", "2026-07-10", "2026-09-08", "2026-09-05"))],
         ordini=[("ODA-26-0088", "Metalfer Lombarda S.r.l.", "Materiali", "Aeratori a lamelle", 24100, "2026-02-02", "Consegnato", None),
                 ("ODA-26-0089", "Elettro Quadri Brianza S.r.l.", "Quadri elettrici", "Centrale ventilazione con sensori meteo", 7600, "2026-02-03", "Consegnato", None),
                 ("ODA-26-0091", "Trasporti Ghezzi S.n.c.", "Trasporti", "Trasporto aeratori", 1300, "2026-02-10", "Consegnato", None),
                 ("ODA-26-0097", "Montaggi Adda S.r.l.", "Posa e subappalti", "Posa in copertura", 9800, "2026-03-01", "Consegnato", None)],
         fp=[("188/26", "Metalfer Lombarda S.r.l.", "ODA-26-0088", "Materiali", 24100, "2026-03-15"),
             ("FT 2026/150", "Elettro Quadri Brianza S.r.l.", "ODA-26-0089", "Quadri elettrici", 7600, "2026-03-20"),
             ("FT-522", "Trasporti Ghezzi S.n.c.", "ODA-26-0091", "Trasporti", 1300, "2026-03-02"),
             ("09/26", "Montaggi Adda S.r.l.", "ODA-26-0097", "Posa e subappalti", 9800, "2026-06-30")],
         rapportini=[("2026-04-24", "D. Colombo", 120, 50, "Posa aeratori lato nord"), ("2026-06-12", "D. Colombo", 110, 100, "Posa completata, centrale collegata")]),
    dict(cod="C-2026-031", cliente="Hotel Darsena S.r.l.", oggetto="Centrale di comando e controllo con manutenzione", sistema="Centrale", cantiere="Milano, Navigli",
         commerciale="L. Bianchi", capo="", contratto="2026-10-02", stato=1, ricavo=26900, budget=B(0, 11200, 400, 2200, 4000), varianti=[],
         piano=[("R1", "Anticipo 40% alla firma", 10760, "contratto", F("FA 2026/201", "2026-10-06", "2026-11-15")), ("R2", "Saldo 60% a collaudo", 16140, "collaudo", {})],
         ordini=[], fp=[], rapportini=[]),
]

SDI = [("SDI-77412", "Metalfer Lombarda S.r.l.", "412/26", "2026-10-14", 54200, "ODA-26-0141"),
       ("SDI-77430", "Trasporti Ghezzi S.n.c.", "FT-889", "2026-10-15", 1100, "ODA-26-0152"),
       ("SDI-77436", "Ferramenta Industriale Rho S.r.l.", "2026/1577", "2026-10-16", 1840, None)]

LOG = [("2026-10-16 17:42", "Ufficio cantiere", "C-2026-022", "Ordine ODA-26-0150 inviato in autorizzazione: supera il budget Materiali"),
       ("2026-10-13 10:05", "Commerciale", "C-2026-018", "Proposta variante V1 da 14.200 €"),
       ("2026-10-09 18:10", "Capocantiere", "C-2026-018", "Rapportino: 90 h, avanzamento 60%"),
       ("2026-10-06 09:30", "Amministrazione", "C-2026-031", "Emessa fattura FA 2026/201 (anticipo 40%)"),
       ("2026-10-02 11:00", "Commerciale", "C-2026-031", "Contratto firmato e caricato"),
       ("2026-09-30 15:20", "Commerciale", "C-2026-027", "Contratto firmato e caricato")]


def carica_esempio(db: Session) -> bool:
    if db.scalar(select(m.Commessa.id).limit(1)):
        return False
    for x in COMMESSE:
        c = m.Commessa(cod=x["cod"], cliente=x["cliente"], oggetto=x["oggetto"], sistema=x["sistema"], cantiere=x["cantiere"],
                       commerciale=x["commerciale"], capo=x["capo"], contratto=d(x["contratto"]), stato=x["stato"],
                       collaudo_ok=x.get("collaudo_ok", False), collaudo_data=d(x.get("collaudo_data")), ricavo=x["ricavo"], fonte="esempio")
        c.budget = [m.VoceBudget(categoria=k, importo=v) for k, v in x["budget"].items()]
        c.varianti = [m.Variante(codice=a, descr=b, importo=i, stato=s, da=da, data=d(dt)) for a, b, i, s, da, dt in x["varianti"]]
        c.piano = [m.Rata(codice=a, descr=b, importo=i, trigger=t, **f) for a, b, i, t, f in x["piano"]]
        c.ordini = [m.Ordine(id=i, fornitore=fo, categoria=ca, descr=de, importo=im, data=d(dt), stato=st, nota=no, fonte="esempio",
                             consegna=d(dt) + timedelta(days=21) if st == "Consegnato" else None)
                    for i, fo, ca, de, im, dt, st, no in x["ordini"]]
        c.fp = [m.FatturaPassiva(num=n, fornitore=fo, ordine_id=o, categoria=ca, importo=im, data=d(dt), fonte="esempio",
                                 pagamento=d(dt) + timedelta(days=60) if d(dt) + timedelta(days=60) < date(2026, 9, 1) else None)
                for n, fo, o, ca, im, dt in x["fp"]]
        c.rapportini = [m.Rapportino(data=d(dt), chi=ch, ore=o, avanz=a, nota=n, fonte="esempio") for dt, ch, o, a, n in x["rapportini"]]
        for doc in DOCS:
            if not doc_dovuto(doc, c.stato) or (c.cod == "C-2026-018" and doc["k"] == "durc"):
                continue
            if doc["fase"] == 1:
                dt = c.contratto
            elif doc["fase"] == 5 and c.collaudo_data:
                dt = c.collaudo_data
            else:
                dt = min(c.contratto + timedelta(days=18 * doc["fase"]), OGGI_DEMO)
            c.documenti.append(m.Documento(tipo=doc["k"], file=f"{DOCF[doc['k']]}_{c.cod}.pdf", data=dt, chi=ROLES[doc["chi"]]["l"]))
        db.add(c)
    for sid, fo, n, dt, im, rif in SDI:
        db.add(m.FatturaSdi(sdi_id=sid, fornitore=fo, num=n, data=d(dt), importo=im, rif_ordine=rif, fonte="esempio"))
    for ts, chi, cod, t in LOG:
        db.add(m.LogEvento(ts=datetime.fromisoformat(ts), chi=chi, cod=cod, testo=t))
    db.add(m.Impostazione(chiave="cfg", valore=CONFIG_DEFAULT))
    db.commit()
    return True
