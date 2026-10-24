"""Modello dati del registro commesse.

Ogni dato che può arrivare da una fonte esterna porta con sé `fonte` (manuale, excel, fatturapa,
banca, erp:<nome>) e `rif_esterno` (l'identificativo nella fonte): così una seconda importazione
dello stesso file aggiorna i dati invece di duplicarli.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Provenienza:
    fonte: Mapped[str] = mapped_column(String(40), default="manuale")
    rif_esterno: Mapped[str | None] = mapped_column(String(120))


class Commessa(Provenienza, Base):
    __tablename__ = "commesse"
    id: Mapped[int] = mapped_column(primary_key=True)
    cod: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    cliente: Mapped[str] = mapped_column(String(200))
    piva_cliente: Mapped[str | None] = mapped_column(String(20))
    oggetto: Mapped[str] = mapped_column(String(300), default="")
    sistema: Mapped[str] = mapped_column(String(60), default="")
    cantiere: Mapped[str] = mapped_column(String(120), default="")
    commerciale: Mapped[str] = mapped_column(String(80), default="")
    capo: Mapped[str] = mapped_column(String(80), default="")
    contratto: Mapped[date | None] = mapped_column(Date)
    stato: Mapped[int] = mapped_column(Integer, default=0)
    collaudo_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    collaudo_data: Mapped[date | None] = mapped_column(Date)
    bloccata: Mapped[bool] = mapped_column(Boolean, default=False)
    ricavo: Mapped[float] = mapped_column(Float, default=0)

    budget: Mapped[list["VoceBudget"]] = relationship(back_populates="commessa", cascade="all, delete-orphan")
    varianti: Mapped[list["Variante"]] = relationship(back_populates="commessa", cascade="all, delete-orphan", order_by="Variante.id")
    piano: Mapped[list["Rata"]] = relationship(back_populates="commessa", cascade="all, delete-orphan", order_by="Rata.id")
    ordini: Mapped[list["Ordine"]] = relationship(back_populates="commessa", cascade="all, delete-orphan", order_by="Ordine.data")
    fp: Mapped[list["FatturaPassiva"]] = relationship(back_populates="commessa", cascade="all, delete-orphan", order_by="FatturaPassiva.data")
    rapportini: Mapped[list["Rapportino"]] = relationship(back_populates="commessa", cascade="all, delete-orphan", order_by="Rapportino.data")
    documenti: Mapped[list["Documento"]] = relationship(back_populates="commessa", cascade="all, delete-orphan")


class VoceBudget(Base):
    __tablename__ = "budget"
    __table_args__ = (UniqueConstraint("commessa_id", "categoria"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    categoria: Mapped[str] = mapped_column(String(60))
    importo: Mapped[float] = mapped_column(Float, default=0)
    commessa: Mapped[Commessa] = relationship(back_populates="budget")


class Variante(Base):
    __tablename__ = "varianti"
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    codice: Mapped[str] = mapped_column(String(20))
    descr: Mapped[str] = mapped_column(String(300))
    importo: Mapped[float] = mapped_column(Float)
    stato: Mapped[str] = mapped_column(String(20), default="proposta")  # proposta | approvata | respinta
    da: Mapped[str] = mapped_column(String(80), default="")
    data: Mapped[date | None] = mapped_column(Date)
    commessa: Mapped[Commessa] = relationship(back_populates="varianti")


class Rata(Base):
    """Rata del piano di fatturazione attiva, con la fattura emessa e l'incasso quando ci sono."""
    __tablename__ = "rate"
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    codice: Mapped[str] = mapped_column(String(20))
    descr: Mapped[str] = mapped_column(String(200))
    importo: Mapped[float] = mapped_column(Float)
    trigger: Mapped[str] = mapped_column(String(20))  # contratto | avanz50 | collaudo
    fattura_num: Mapped[str | None] = mapped_column(String(40), index=True)
    fattura_data: Mapped[date | None] = mapped_column(Date)
    fattura_scad: Mapped[date | None] = mapped_column(Date)
    fattura_fonte: Mapped[str | None] = mapped_column(String(40))
    incasso_data: Mapped[date | None] = mapped_column(Date)
    incasso_fonte: Mapped[str | None] = mapped_column(String(40))
    commessa: Mapped[Commessa] = relationship(back_populates="piano")


class Ordine(Provenienza, Base):
    __tablename__ = "ordini"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    fornitore: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(60))
    descr: Mapped[str] = mapped_column(String(300), default="")
    importo: Mapped[float] = mapped_column(Float)
    data: Mapped[date] = mapped_column(Date)
    stato: Mapped[str] = mapped_column(String(40), default="Ordinato")  # Ordinato | Consegnato | Autorizzazione richiesta | Respinto
    consegna: Mapped[date | None] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(300))
    commessa: Mapped[Commessa] = relationship(back_populates="ordini")


class FatturaPassiva(Provenienza, Base):
    __tablename__ = "fatture_passive"
    __table_args__ = (UniqueConstraint("fornitore", "num"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    num: Mapped[str] = mapped_column(String(40))
    fornitore: Mapped[str] = mapped_column(String(200))
    piva_fornitore: Mapped[str | None] = mapped_column(String(20))
    ordine_id: Mapped[str | None] = mapped_column(ForeignKey("ordini.id", ondelete="SET NULL"))
    categoria: Mapped[str] = mapped_column(String(60))
    importo: Mapped[float] = mapped_column(Float)
    data: Mapped[date] = mapped_column(Date)
    scadenza: Mapped[date | None] = mapped_column(Date)
    pagamento: Mapped[date | None] = mapped_column(Date)
    commessa: Mapped[Commessa] = relationship(back_populates="fp")
    ordine: Mapped["Ordine | None"] = relationship()


class Rapportino(Provenienza, Base):
    __tablename__ = "rapportini"
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    data: Mapped[date] = mapped_column(Date)
    chi: Mapped[str] = mapped_column(String(80))
    ore: Mapped[float] = mapped_column(Float)
    avanz: Mapped[int] = mapped_column(Integer)
    nota: Mapped[str] = mapped_column(String(300), default="")
    commessa: Mapped[Commessa] = relationship(back_populates="rapportini")


class Documento(Base):
    __tablename__ = "documenti"
    __table_args__ = (UniqueConstraint("commessa_id", "tipo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey("commesse.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(30))
    file: Mapped[str] = mapped_column(String(300))
    data: Mapped[date | None] = mapped_column(Date)
    chi: Mapped[str] = mapped_column(String(80), default="")
    commessa: Mapped[Commessa] = relationship(back_populates="documenti")


class FatturaSdi(Provenienza, Base):
    """Fattura passiva arrivata dallo SDI (o da un file XML) e non ancora registrata su una commessa."""
    __tablename__ = "sdi_inbox"
    __table_args__ = (UniqueConstraint("fornitore", "num"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sdi_id: Mapped[str | None] = mapped_column(String(60))
    fornitore: Mapped[str] = mapped_column(String(200))
    piva_fornitore: Mapped[str | None] = mapped_column(String(20))
    num: Mapped[str] = mapped_column(String(40))
    data: Mapped[date] = mapped_column(Date)
    scadenza: Mapped[date | None] = mapped_column(Date)
    importo: Mapped[float] = mapped_column(Float)
    rif_ordine: Mapped[str | None] = mapped_column(String(40))
    rif_commessa: Mapped[str | None] = mapped_column(String(30))
    descrizione: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(200))


class MovimentoBanca(Provenienza, Base):
    __tablename__ = "movimenti_banca"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date)
    importo: Mapped[float] = mapped_column(Float)  # positivo = accredito, negativo = addebito
    causale: Mapped[str] = mapped_column(Text, default="")
    controparte: Mapped[str | None] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(40))
    rata_id: Mapped[int | None] = mapped_column(ForeignKey("rate.id", ondelete="SET NULL"))
    fattura_passiva_id: Mapped[int | None] = mapped_column(ForeignKey("fatture_passive.id", ondelete="SET NULL"))
    abbinamento: Mapped[str | None] = mapped_column(String(200))  # come è stato abbinato, o perché no


class LogEvento(Base):
    __tablename__ = "log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    chi: Mapped[str] = mapped_column(String(80))
    ruolo: Mapped[str] = mapped_column(String(30), default="")
    cod: Mapped[str | None] = mapped_column(String(30))
    testo: Mapped[str] = mapped_column(Text)


class Importazione(Base):
    """Storico delle importazioni da ogni fonte, con l'esito riga per riga."""
    __tablename__ = "importazioni"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    connettore: Mapped[str] = mapped_column(String(40))
    tipo: Mapped[str] = mapped_column(String(40))
    origine: Mapped[str] = mapped_column(String(300))  # nome del file o della connessione
    utente: Mapped[str] = mapped_column(String(80), default="")
    righe_ok: Mapped[int] = mapped_column(Integer, default=0)
    righe_err: Mapped[int] = mapped_column(Integer, default=0)
    esito: Mapped[dict] = mapped_column(JSON, default=dict)


class Impostazione(Base):
    __tablename__ = "impostazioni"
    chiave: Mapped[str] = mapped_column(String(40), primary_key=True)
    valore: Mapped[dict | float | str | int] = mapped_column(JSON)
