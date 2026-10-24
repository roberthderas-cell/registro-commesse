"""Registro dei connettori a file. Per aggiungere una fonte: scrivere una sottoclasse di Connettore e aggiungerla qui."""
from .banca import BancaConnettore
from .base import TIPI, Connettore, Lettura, Record
from .fatturapa import FatturaPAConnettore
from .tabelle import TabelleConnettore

CONNETTORI: dict[str, Connettore] = {c.nome: c for c in (TabelleConnettore(), FatturaPAConnettore(), BancaConnettore())}

__all__ = ["CONNETTORI", "TIPI", "Connettore", "Lettura", "Record"]
