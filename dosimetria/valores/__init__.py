"""Tipos de valor imutáveis: fração legal, pena em dias e faixa de pena em abstrato."""

from .fracao import Fracao
from .pena import Pena
from .faixa import Faixa

__all__ = [
    "Fracao",
    "Pena",
    "Faixa",
]
