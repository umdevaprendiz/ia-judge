"""Estratégias plugáveis de quanto pesa cada circunstância nas fases 1 e 2."""

from .estrategias import EstrategiaQuantum, FracaoDoIntervalo, FracaoDoMinimo

__all__ = [
    "EstrategiaQuantum",
    "FracaoDoIntervalo",
    "FracaoDoMinimo",
]
