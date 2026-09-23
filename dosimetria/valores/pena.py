from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from .fracao import Fracao

DIAS_POR_ANO = 365
DIAS_POR_MES = 30


@total_ordering
@dataclass(frozen=True, slots=True)
class Pena:
    """Quantidade de pena privativa de liberdade, guardada internamente em dias inteiros."""

    dias: int

    def __post_init__(self) -> None:
        if self.dias < 0:
            raise ValueError("pena não pode ter dias negativos")

    @classmethod
    def de_anos_meses_dias(cls, anos: int = 0, meses: int = 0, dias: int = 0) -> "Pena":
        return cls(anos * DIAS_POR_ANO + meses * DIAS_POR_MES + dias)

    def mais(self, fracao: Fracao) -> "Pena":
        """Aumenta a pena em uma fração dela mesma (ex.: majorante de 1/3)."""
        return Pena(self.dias + fracao.aplicar(self.dias))

    def menos(self, fracao: Fracao) -> "Pena":
        """Diminui a pena em uma fração dela mesma (ex.: minorante de 1/6)."""
        return Pena(self.dias - fracao.aplicar(self.dias))

    def mais_dias(self, dias: int) -> "Pena":
        return Pena(self.dias + dias)

    def menos_dias(self, dias: int) -> "Pena":
        return Pena(self.dias - dias)

    def como_anos_meses_dias(self) -> tuple[int, int, int]:
        anos, resto = divmod(self.dias, DIAS_POR_ANO)
        meses, dias = divmod(resto, DIAS_POR_MES)
        return anos, meses, dias

    def __lt__(self, outra: "Pena") -> bool:
        return self.dias < outra.dias

    def __str__(self) -> str:
        anos, meses, dias = self.como_anos_meses_dias()
        partes = []
        if anos:
            partes.append(f"{anos} ano{'s' if anos != 1 else ''}")
        if meses:
            partes.append(f"{meses} {'mês' if meses == 1 else 'meses'}")
        if dias or not partes:
            partes.append(f"{dias} dia{'s' if dias != 1 else ''}")
        return ", ".join(partes)
