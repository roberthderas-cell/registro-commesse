"""Costanti di dominio: stati, fasi, categorie di costo, documenti, ruoli. Sono le stesse del prototipo."""

CATS = ["Materiali", "Quadri elettrici", "Trasporti", "Posa e subappalti", "Manodopera interna"]

STATI = [
    "Offerta accettata", "Contratto firmato", "Progettazione", "Approvvigionamento", "Posa in cantiere",
    "Collaudo e DICH.IMP.", "Fatturazione", "Incassata", "Chiusa",
]

FASI = [
    {"l": "Avvio", "st": [0, 1], "v": "--ph-avvio"},
    {"l": "Progettazione", "st": [2], "v": "--ph-prog"},
    {"l": "Approvvigionamento", "st": [3], "v": "--ph-appr"},
    {"l": "Cantiere e collaudo", "st": [4, 5], "v": "--ph-cant"},
    {"l": "Fatturazione e incasso", "st": [6, 7], "v": "--ph-fatt"},
    {"l": "Chiuse", "st": [8], "v": "--ph-chiusa"},
]

ROLES = {
    "admin": {"l": "Amministrazione", "i": "AM"},
    "direzione": {"l": "Direzione", "i": "DI"},
    "commerciale": {"l": "Commerciale", "i": "CO"},
    "tecnico": {"l": "Ufficio tecnico", "i": "UT"},
    "cantiere": {"l": "Ufficio cantiere", "i": "UC"},
    "capocantiere": {"l": "Capocantiere", "i": "MF"},
}

# Chi può far avanzare la commessa dallo stato i allo stato i+1
NEXT_BY = [["commerciale"], ["tecnico"], ["tecnico"], ["cantiere"], ["capocantiere", "cantiere"], ["tecnico"], ["admin"], ["admin"]]

# Cosa vede ogni ruolo: r = ricavi, c = costi, m = margini
SEE = {
    "admin": {"r", "c", "m"}, "direzione": {"r", "c", "m"}, "commerciale": {"r"},
    "tecnico": {"c"}, "cantiere": {"c"}, "capocantiere": set(),
}

TRIG = {"contratto": "Firma del contratto", "avanz50": "Avanzamento cantiere ≥ 50%", "collaudo": "Collaudo e DICH.IMP."}

DOCS = [
    {"k": "contratto", "l": "Contratto firmato", "fase": 1, "chi": "commerciale"},
    {"k": "progetto", "l": "Progetto esecutivo e calcoli", "fase": 2, "chi": "tecnico"},
    {"k": "pos", "l": "POS e piano di sicurezza del cantiere", "fase": 4, "chi": "cantiere"},
    {"k": "durc", "l": "DURC dei subappaltatori", "fase": 4, "chi": "cantiere"},
    {"k": "collaudo", "l": "Verbale di collaudo", "fase": 5, "chi": "tecnico"},
    {"k": "dichimp", "l": "DICH.IMP. (DM 37/2008)", "fase": 5, "chi": "tecnico"},
    {"k": "manuale", "l": "Manuale di uso e manutenzione", "fase": 5, "chi": "tecnico"},
]

STATI_ORDINE = ["Ordinato", "Consegnato", "Autorizzazione richiesta", "Respinto"]

CONFIG_DEFAULT = {"costoOra": 32, "sogliaMarg": 15, "sogliaGap": 15, "ggPag": 60, "ggForn": 60, "resp": "Roberth Deras"}


def fase_di(stato: int) -> dict:
    return next(f for f in FASI if stato in f["st"])


def doc_dovuto(d: dict, stato: int) -> bool:
    return d["fase"] <= stato if d["fase"] < 5 else stato >= 6
