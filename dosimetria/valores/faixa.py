from dataclasses import dataclass

from .pena import Pena


@dataclass(frozen=True, slots=True)
class Faixa:
    """Intervalo de pena em abstrato de um tipo penal (simples ou qualificado)."""

    minimo: Pena
    maximo: Pena
    origem: str  # rótulo do dispositivo, ex.: "CP.art155" ou "CP.art155.§4"

    def __post_init__(self) -> None:
        if self.minimo > self.maximo:
            raise ValueError("mínimo não pode ser maior que o máximo")

    def contem(self, pena: Pena) -> bool:
        return self.minimo <= pena <= self.maximo

    def limitar(self, pena: Pena) -> Pena:
        """Restringe a pena aos limites da faixa (regra das fases 1ª e 2ª: não sai da faixa)."""
        if pena < self.minimo:
            return self.minimo
        if pena > self.maximo:
            return self.maximo
        return pena
