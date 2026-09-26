"""Tipos de valor imutáveis: fração legal, pena em dias e faixa de pena em abstrato."""

from .fracao import Fraction
from .pena import Penalty
from .faixa import PenaltyRange

__all__ = [
    "Fraction",
    "Penalty",
    "PenaltyRange",
]
