# Registro Commesse

Controllo delle commesse dal contratto all'incasso: margini a finire, budget per voce di costo, ordini fornitori,
rapportini di cantiere, piano di fatturazione, crediti e documenti di fase. Ruoli: amministrazione, direzione,
commerciale, ufficio tecnico, ufficio cantiere, capocantiere.

Nasce dal prototipo HTML (`docs/prototipo/registro-commesse.html`) ed è diventato un'applicazione vera:
**backend** Python (FastAPI + SQLAlchemy) con database, **frontend** React, e **connettori** per alimentarlo da più fonti.

## Avvio in locale

Servono Python 3.11+ e Node 18+.

```bash
./avvia.sh
```

Al primo avvio installa le dipendenze e carica i dati di esempio del prototipo. Poi:

- applicazione: http://127.0.0.1:5173
- documentazione delle API (interattiva): http://127.0.0.1:8000/docs

## Accesso e utenti

Ogni persona entra con nome utente e password; il ruolo è quello assegnato al suo utente e lo decide il server
(non si può cambiare dal browser).

- **Primo avvio**: viene creato l'utente `admin` e, con i dati di esempio, un utente per ruolo
  (`direzione`, `l.bianchi`, `s.galli`, `tecnico`, `cantiere`, `m.ferrari`, `d.colombo`).
  Le password temporanee sono in `backend/data/primo_accesso.txt` (fuori da git, leggibile solo dal tuo utente):
  al primo accesso ognuno deve sceglierne una nuova. Cancella il file dopo averle consegnate.
- **Utenti** (menu Sistema, solo amministrazione): crea utenti, cambia ruolo o nome, disattiva, reimposta la password.
  Le password temporanee si vedono una volta sola, al momento della creazione o del reset.
- **Capocantiere**: vede le commesse il cui campo «Capocantiere» è uguale al suo nome mostrato; se l'amministrazione
  rinomina l'utente, le commesse vengono aggiornate.
- **Sicurezza**: password salvate con scrypt; sessione in cookie HttpOnly che dura 10 ore e si rinnova con l'uso;
  dopo 5 tentativi sbagliati l'utente è bloccato per 10 minuti; cambio ruolo, disattivazione e reset della password
  scollegano subito l'utente. Deve restare sempre almeno un amministratore attivo.

Test del backend: `cd backend && .venv/bin/python -m pytest`

## Fonti dati

Ogni fonte ha un connettore che legge i dati e li trasforma in record standard
(commessa, ordine, fattura passiva, fattura emessa, rapportino, movimento bancario).
Validazione e salvataggio sono comuni a tutte le fonti (`backend/app/importazione.py`), quindi le regole sono le stesse
ovunque: ordini oltre il budget in autorizzazione, fatture abbinate all'ordine, niente doppioni.
Ogni importazione si vede prima **in anteprima** (stesso codice, transazione annullata) e resta nello **storico** con l'esito riga per riga.
Ogni dato registra da quale fonte è arrivato.

| Fonte | Formati | Cosa fa |
|---|---|---|
| Excel / CSV | `.xlsx`, `.csv` | Commesse, ordini, fatture passive ed emesse, rapportini, movimenti. Riconosce i nomi di colonna più comuni dei gestionali. Modelli CSV scaricabili dall'app. |
| Fatture elettroniche SDI | FatturaPA `.xml`, `.xml.p7m`, `.zip` | Passive → casella "Fatture SDI" con ordine e commessa già suggeriti (da `DatiOrdineAcquisto` o dal testo). Attive (cedente = `RC_PIVA_AZIENDA`) → abbinate alla rata del piano di fatturazione. |
| Estratto conto | CAMT.053 `.xml`, CSV/Excel con importo o dare/avere | Accrediti → incasso della fattura (numero in causale o importo univoco). Addebiti → pagamento della fattura passiva. |
| Gestionale / ERP | query SQL su qualunque database supportato da SQLAlchemy, oppure API REST | Configurato in `backend/fonti.yaml` (vedi `fonti.example.yaml`); sincronizzazione con anteprima dalla sezione Fonti dati. |

In `backend/esempi/` c'è un file di prova per ogni formato. `scripts/crea_erp_demo.py` crea un finto database
di gestionale, già collegato in `fonti.yaml`.

**Aggiungere una fonte**: una sottoclasse di `Connettore` in `backend/app/connettori/` che restituisce `Record`,
registrata in `connettori/__init__.py`. Per un nuovo gestionale di solito basta una voce in `fonti.yaml`.

## Struttura

```
backend/
  app/
    models.py          tabelle del database
    calcoli.py         margine, costo a finire, avanzamento economico, avvisi, incassi attesi
    importazione.py    validazione e salvataggio comuni a tutte le fonti
    connettori/        tabelle (Excel/CSV), fatturapa, banca, erp
    api/               commesse, cruscotto e SDI, fonti dati
  esempi/              file di prova per ogni fonte
  tests/
frontend/src/
  views/               Cruscotto, Pipeline, Commesse (fascicolo), Fatture SDI, Fonti dati, Registro, Impostazioni
docs/prototipo/        il prototipo HTML originale, come riferimento
```

## Configurazione

Variabili d'ambiente (o file `backend/.env`), tutte con prefisso `RC_`:

| Variabile | Default | |
|---|---|---|
| `RC_DATABASE_URL` | SQLite in `backend/data/registro.db` | es. `postgresql+psycopg://utente:pwd@host/registro` |
| `RC_PIVA_AZIENDA` | `IT01234560157` | **da impostare**: distingue fatture emesse e ricevute |
| `RC_OGGI` | oggi | data fissa, utile per demo |
| `RC_CARICA_DATI_ESEMPIO` | `true` | carica le commesse di esempio (e gli utenti dimostrativi) se il database è vuoto |
| `RC_ADMIN_PASSWORD` | generata | password iniziale di `admin` al primo avvio (da cambiare al primo accesso) |
| `RC_DURATA_SESSIONE_ORE` | `10` | durata della sessione senza attività |
| `RC_COOKIE_SECURE` | `false` | `true` quando l'app è servita in HTTPS |

## Su un server

`docker compose up -d` (con `DB_PASSWORD` nel file `.env`) avvia PostgreSQL e l'applicazione su http://server:8000.
Il backend serve anche il frontend compilato. Senza dati di esempio viene creato solo `admin`, con la password
di `ADMIN_PASSWORD` (nel `.env`) oppure, se manca, una generata: si legge con
`docker compose exec app cat data/primo_accesso.txt`.

## Prossimi passi

- HTTPS davanti all'applicazione (es. reverse proxy con certificato) prima di renderla raggiungibile fuori dall'ufficio, con `RC_COOKIE_SECURE=true`.
- Schermate del prototipo non ancora portate: Business intelligence, Per periodo, Scadenzario, Anagrafiche, Report e scheda stampabile, demo guidata.
- Migrazioni del database con Alembic, quando lo schema inizierà a cambiare con dati veri dentro.
- Scarico automatico delle fatture dal cassetto fiscale o dall'intermediario SDI (oggi si caricano i file).
