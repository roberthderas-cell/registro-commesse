# Mettere il Registro Commesse online (Oracle Cloud, gratis)

Alla fine avrai l'app su un indirizzo `https://…` apribile da qualunque computer, anche a portatile spento.
Il server è un **Oracle Cloud "Always Free"**: gratuito senza scadenza, finché si resta nelle risorse gratuite.

Tempo: circa un'ora la prima volta. Le parti 1-3 si fanno sul sito di Oracle, la 4 con un solo comando dal portatile.

---

## 1. Crea l'account Oracle Cloud

1. Vai su **https://www.oracle.com/it/cloud/free/** → *Inizia gratuitamente*.
2. Come **Home Region** scegli **Italy North (Milan)** (oppure *Germany Central (Frankfurt)*).
   Non si può cambiare dopo, e il server gratuito si crea solo lì.
3. Oracle chiede una **carta di credito per verificare l'identità**: non addebita nulla finché usi le risorse
   *Always Free* (vedi in fondo, "Da sapere").

## 2. Crea la chiave per collegarti al server (sul portatile)

È la "chiave di casa" con cui il portatile entra nel server, al posto della password. In un terminale:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/oracle_registro -C registro-commesse
```

Quando chiede una *passphrase* puoi lasciarla vuota (Invio due volte) o sceglierne una.
Poi mostra la parte pubblica, che servirà al punto 3:

```bash
cat ~/.ssh/oracle_registro.pub
```

## 3. Crea il server

Nella console di Oracle: menu ☰ → **Compute** → **Instances** → **Create instance**.

| Campo | Cosa scegliere |
|---|---|
| Name | `registro-commesse` |
| Image | **Change image** → *Canonical Ubuntu* → **24.04** |
| Shape | **Change shape** → *Ampere* → **VM.Standard.A1.Flex**, 1 OCPU e 6 GB di memoria (etichetta *Always Free-eligible*) |
| Networking | lascia *Create new virtual cloud network* e *Assign a public IPv4 address* |
| Add SSH keys | **Paste public keys** → incolla la riga mostrata da `cat ~/.ssh/oracle_registro.pub` |

Poi **Create**. Dopo un paio di minuti lo stato diventa *Running*: copia il **Public IP address**.

> **"Out of capacity"?** I server Ampere gratuiti a volte sono esauriti: riprova dopo qualche ora, oppure scegli
> lo shape **VM.Standard.E2.1.Micro** (AMD, 1 GB, anch'esso *Always Free*): funziona, è solo più lento la prima volta.

### Apri le porte web

Il server accetta solo collegamenti SSH: bisogna aprire HTTP (80) e HTTPS (443).
Nella pagina dell'istanza: **Primary VNIC** → clic sulla *Subnet* → **Security Lists** → *Default Security List* →
**Add Ingress Rules**, e aggiungi due regole:

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Il firewall interno del server lo apre da solo lo script del punto 4.)

## 4. Pubblica l'app (sul portatile, un comando)

Nella cartella del progetto, sostituendo `IP` con l'indirizzo del punto 3:

```bash
cd ~/registro-commesse
./deploy/pubblica.sh ubuntu@IP ~/.ssh/oracle_registro
```

Lo script copia l'app sul server, installa Docker e alla prima volta chiede:

- **Indirizzo web**: premi Invio per usare quello proposto, del tipo `152-70-1-2.sslip.io`
  (gratuito e immediato; si può cambiare dopo, vedi sotto).
- **Partita IVA** dell'azienda, con `IT` davanti.

La prima costruzione dura qualche minuto. Alla fine mostra l'indirizzo dell'app e la **password temporanea di `admin`**.

## 5. Primo accesso

1. Apri l'indirizzo `https://…` mostrato, entra come `admin` con la password temporanea e scegline una nuova.
2. Cancella le credenziali temporanee dal server:
   ```bash
   ssh -i ~/.ssh/oracle_registro ubuntu@IP 'cd ~/registro-commesse && sudo docker compose exec app rm data/primo_accesso.txt'
   ```
3. Da **Sistema → Utenti** crea gli altri utenti.

Il server parte **vuoto** (nessuna commessa di esempio). Se invece vuoi portarci i dati del portatile, compresi
utenti e password, usa `./deploy/porta-dati.sh ubuntu@IP ~/.ssh/oracle_registro` (sostituisce tutto ciò che c'è sul server).

---

## Uso quotidiano

**Aggiornare l'app** dopo una modifica: salva in git (commit), poi rilancia lo stesso comando del punto 4.
I dati non vengono toccati.

**Copie di sicurezza**: il server ne fa una ogni notte alle 2 (database e documenti caricati) e le tiene 30 giorni.
Ogni tanto scaricale sul portatile, così esistono anche fuori dal server:

```bash
./deploy/scarica-backup.sh ubuntu@IP ~/.ssh/oracle_registro
```

**Ripristinare una copia** (sostituisce i dati attuali):

```bash
ssh -i ~/.ssh/oracle_registro ubuntu@IP
cd ~/registro-commesse
sudo docker compose stop app
sudo docker compose exec -T db psql -U registro -d postgres -c "DROP DATABASE registro" -c "CREATE DATABASE registro OWNER registro"
gunzip -c backup/registro-AAAAMMGG-HHMM.sql.gz | sudo docker compose exec -T db psql -U registro -d registro
sudo docker compose start app
```

**Vedere cosa succede** (errori, avvio): `sudo docker compose logs -f app` sul server.

## Un indirizzo più bello (facoltativo)

1. Su **https://www.duckdns.org** accedi (con Google o GitHub), crea un sottodominio, es. `registro-bovema`,
   e nel campo *current ip* metti l'IP del server.
2. Sul server cambia l'indirizzo e riavvia:
   ```bash
   ssh -i ~/.ssh/oracle_registro ubuntu@IP
   cd ~/registro-commesse && sed -i 's/^DOMINIO=.*/DOMINIO=registro-bovema.duckdns.org/' .env && sudo docker compose up -d
   ```
   Il certificato HTTPS per il nuovo nome arriva da solo in un minuto.

---

## Da sapere

- **Server inattivo**: Oracle può recuperare i server *Always Free* poco usati. Per evitarlo si può passare l'account a
  **Pay As You Go** (Billing → Upgrade): resta gratuito entro i limiti *Always Free*; imposta un *Budget* con avviso a 1 €
  per stare tranquillo. In ogni caso, scarica regolarmente le copie di sicurezza.
- **Gestionale in ufficio**: il server su internet non vede il database del gestionale in ufficio, quindi la
  sincronizzazione ERP da `fonti.yaml` lì non funziona (l'importazione da file Excel, XML e CAMT sì).
- **Sicurezza attiva**: HTTPS obbligatorio, cookie di sessione solo cifrato, documentazione delle API spenta,
  blocco dopo tentativi sbagliati per utente e per indirizzo IP, porte del database e dell'app non raggiungibili da internet.

## Se qualcosa non va

| Problema | Cosa controllare |
|---|---|
| `Permission denied (publickey)` | Nel comando c'è `~/.ssh/oracle_registro`? La chiave incollata al punto 3 è quella `.pub`? |
| La pagina non si apre / certificato non valido | Regole 80 e 443 del punto 3; `sudo docker compose logs caddy` sul server |
| Lo script si ferma durante la costruzione | Rilancialo: riprende da dove si era fermato |
