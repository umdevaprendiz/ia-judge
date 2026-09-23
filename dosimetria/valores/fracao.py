from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fraction:
    """Fração legal (ex.: 1/3, 1/6), guardada como numerador/denominador para nunca perder precisão."""

    numerador: int
    denominador: int

    def __post_init__(self) -> None:
        if self.denominador <= 0:
            raise ValueError("denominador deve ser positivo")
        if self.numerador < 0:
            raise ValueError("numerador não pode ser negativo")

    def aplicar(self, dias: int) -> int:
        """Fração de um total de dias. Frações de dia são desprezadas (art. 11 do CP)."""
        return (dias * self.numerador) // self.denominador

    def __str__(self) -> str:
        return f"{self.numerador}/{self.denominador}"
