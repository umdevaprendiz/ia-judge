from dataclasses import dataclass

from .pena import Penalty


@dataclass(frozen=True, slots=True)
class PenaltyRange:
    """Intervalo de pena em abstrato de um tipo penal (simples ou qualificado)."""

    minimo: Penalty
    maximo: Penalty
    origem: str  # rótulo do dispositivo, ex.: "CP.art155" ou "CP.art155.§4"

    def __post_init__(self) -> None:
        if self.minimo > self.maximo:
            raise ValueError("mínimo não pode ser maior que o máximo")

    def contem(self, pena: Penalty) -> bool:
        return self.minimo <= pena <= self.maximo

    def limitar(self, pena: Penalty) -> Penalty:
        """Restringe a pena aos limites da faixa (regra das fases 1ª e 2ª: não sai da faixa)."""
        if pena < self.minimo:
            return self.minimo
        if pena > self.maximo:
            return self.maximo
        return pena
