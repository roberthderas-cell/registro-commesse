"""Impostazioni dell'applicazione, lette da variabili d'ambiente (prefisso RC_) o dal file .env."""
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RC_", env_file=BASE_DIR / ".env", extra="ignore")

    # SQLite in locale; in produzione per esempio postgresql+psycopg://utente:pwd@host/registro
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'registro.db'}"
    # Partita IVA dell'azienda: serve a capire se una FatturaPA è attiva (emessa) o passiva (ricevuta)
    piva_azienda: str = "IT01234560157"
    # Data di riferimento fissa (utile per i dati di esempio); vuota = oggi
    oggi: date | None = None
    # File con le connessioni ai gestionali/ERP
    fonti_file: Path = BASE_DIR / "fonti.yaml"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    carica_dati_esempio: bool = True


settings = Settings()


def oggi() -> date:
    return settings.oggi or date.today()
