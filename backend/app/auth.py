"""Password, sessioni e primo accesso.

Le password sono salvate con scrypt (libreria standard, sale casuale per utente). Le sessioni sono
token casuali in un cookie HttpOnly; nel database c'è solo l'impronta del token, così chi legge il
database non può impersonare nessuno.
"""
import hashlib
import hmac
import secrets
import string
import time
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings

COOKIE = "rc_sessione"
N, R, P = 2**14, 8, 1
MAX_TENTATIVI, BLOCCO = 5, timedelta(minutes=10)
LUNGHEZZA_MINIMA = 10


def hash_password(pwd: str) -> str:
    sale = secrets.token_bytes(16)
    h = hashlib.scrypt(pwd.encode(), salt=sale, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${sale.hex()}${h.hex()}"


def verifica_password(pwd: str, salvato: str) -> bool:
    try:
        _, n, r, p, sale, h = salvato.split("$")
        calc = hashlib.scrypt(pwd.encode(), salt=bytes.fromhex(sale), n=int(n), r=int(r), p=int(p), dklen=len(h) // 2)
    except ValueError:
        return False
    return hmac.compare_digest(calc.hex(), h)


# Hash di una password qualsiasi: si verifica anche quando l'utente non esiste, così i tempi di
# risposta non rivelano quali nomi utente sono validi
_HASH_FINTO = hash_password(secrets.token_urlsafe(16))


def password_temporanea() -> str:
    alfabeto = string.ascii_letters + string.digits
    return "-".join("".join(secrets.choice(alfabeto) for _ in range(4)) for _ in range(3))


def controlla_password_nuova(pwd: str, username: str) -> str | None:
    if len(pwd) < LUNGHEZZA_MINIMA:
        return f"La password deve avere almeno {LUNGHEZZA_MINIMA} caratteri"
    if pwd.lower() == username.lower() or username.lower() in pwd.lower():
        return "La password non può contenere il nome utente"
    if len(set(pwd)) < 5:
        return "La password è troppo ripetitiva"
    return None


# Freno per indirizzo IP, oltre al blocco per utente: chi prova molti nomi utente diversi
# dallo stesso indirizzo viene fermato per un quarto d'ora (memoria del processo, si azzera al riavvio)
MAX_FALLITI_IP, FINESTRA_IP = 20, 15 * 60
_falliti_ip: dict[str, list[float]] = {}


def ip_frenato(ip: str) -> bool:
    adesso = time.monotonic()
    recenti = [t for t in _falliti_ip.get(ip, []) if adesso - t < FINESTRA_IP]
    _falliti_ip[ip] = recenti
    return len(recenti) >= MAX_FALLITI_IP


def segna_fallimento_ip(ip: str):
    _falliti_ip.setdefault(ip, []).append(time.monotonic())
    if len(_falliti_ip) > 10_000:  # non far crescere la memoria all'infinito
        _falliti_ip.clear()


def _impronta(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def autentica(db: Session, username: str, pwd: str) -> tuple[m.Utente | None, str | None]:
    """Restituisce (utente, None) se le credenziali sono giuste, altrimenti (None, messaggio)."""
    u = db.scalar(select(m.Utente).where(m.Utente.username == username.strip().lower()))
    adesso = datetime.now()
    if not u:
        verifica_password(pwd, _HASH_FINTO)
        return None, "Nome utente o password non corretti"
    if u.bloccato_fino and u.bloccato_fino > adesso:
        minuti = int((u.bloccato_fino - adesso).total_seconds() // 60) + 1
        return None, f"Troppi tentativi sbagliati: riprova tra {minuti} minuti"
    if not verifica_password(pwd, u.password_hash):
        u.tentativi_falliti += 1
        if u.tentativi_falliti >= MAX_TENTATIVI:
            u.bloccato_fino, u.tentativi_falliti = adesso + BLOCCO, 0
        db.commit()
        return None, "Nome utente o password non corretti"
    if not u.attivo:
        return None, "Utente disattivato: rivolgiti all'amministrazione"
    u.tentativi_falliti, u.bloccato_fino, u.ultimo_accesso = 0, None, adesso
    return u, None


def apri_sessione(db: Session, u: m.Utente) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(delete(m.Sessione).where(m.Sessione.scadenza < datetime.now()))
    db.add(m.Sessione(token_hash=_impronta(token), utente_id=u.id, scadenza=datetime.now() + timedelta(hours=settings.durata_sessione_ore)))
    db.commit()
    return token


def utente_da_token(db: Session, token: str | None) -> m.Utente | None:
    if not token:
        return None
    s = db.scalar(select(m.Sessione).where(m.Sessione.token_hash == _impronta(token)))
    adesso = datetime.now()
    if not s or s.scadenza < adesso or not s.utente.attivo:
        return None
    durata = timedelta(hours=settings.durata_sessione_ore)
    if s.scadenza - adesso < durata / 2:  # la sessione si rinnova finché la si usa
        s.scadenza = adesso + durata
        db.commit()
    return s.utente


def chiudi_sessione(db: Session, token: str | None):
    if token:
        db.execute(delete(m.Sessione).where(m.Sessione.token_hash == _impronta(token)))
        db.commit()


def chiudi_sessioni_utente(db: Session, utente_id: int, tranne: str | None = None):
    q = delete(m.Sessione).where(m.Sessione.utente_id == utente_id)
    if tranne:
        q = q.where(m.Sessione.token_hash != _impronta(tranne))
    db.execute(q)


# Utenti dimostrativi, uno per ruolo, con i nomi delle commesse di esempio
UTENTI_DEMO = [("direzione", "Direzione", "direzione"),("l.bianchi", "L. Bianchi", "commerciale"), ("s.galli", "S. Galli", "commerciale"),
               ("tecnico", "Ufficio tecnico", "tecnico"), ("cantiere", "Ufficio cantiere", "cantiere"),
               ("m.ferrari", "M. Ferrari", "capocantiere"), ("d.colombo", "D. Colombo", "capocantiere")]
FILE_PRIMO_ACCESSO = settings.data_dir / "primo_accesso.txt"


def crea_utenti_iniziali(db: Session, demo: bool) -> list[tuple[str, str, str]]:
    """Al primo avvio crea l'amministratore (e, con i dati di esempio, un utente per ruolo).

    Le password temporanee finiscono in data/primo_accesso.txt (fuori da git): al primo accesso
    ognuno deve sceglierne una nuova.
    """
    if db.scalar(select(m.Utente.id).limit(1)):
        return []
    nuovi = [("admin", "Amministrazione", "admin")]
    if demo:
        nuovi += UTENTI_DEMO
    righe = []
    for username, nome, ruolo in nuovi:
        pwd = settings.admin_password if username == "admin" and settings.admin_password else password_temporanea()
        db.add(m.Utente(username=username, nome=nome, ruolo=ruolo, password_hash=hash_password(pwd), deve_cambiare_password=True))
        righe.append((username, ruolo, pwd))
    db.commit()
    FILE_PRIMO_ACCESSO.parent.mkdir(parents=True, exist_ok=True)
    FILE_PRIMO_ACCESSO.write_text(
        "Credenziali di primo accesso al Registro Commesse.\n"
        "Al primo accesso ogni utente deve cambiare la password. Cancella questo file dopo averle consegnate.\n\n"
        + "\n".join(f"{u:<12} {r:<14} {p}" for u, r, p in righe) + "\n", encoding="utf-8")
    FILE_PRIMO_ACCESSO.chmod(0o600)
    print(f"\n  Creati {len(righe)} utenti. Credenziali di primo accesso in {FILE_PRIMO_ACCESSO}\n", flush=True)
    return righe
