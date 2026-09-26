"""Estratégias plugáveis de quanto pesa cada circunstância nas fases 1 e 2."""

from .estrategias import QuantumStrategy, IntervalFraction, MinimumFraction

__all__ = [
    "QuantumStrategy",
    "IntervalFraction",
    "MinimumFraction",
]
