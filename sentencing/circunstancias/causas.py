from dataclasses import dataclass
from enum import Enum
import fractions

from ..valores.fracao import Fraction


class CauseDirection(Enum):
    AUMENTO = "aumento"
    DIMINUICAO = "diminuicao"


class CauseOrigin(Enum):
    """Onde a causa está prevista. Só as da Parte Especial entram no concurso do art. 68, parágrafo único."""

    PARTE_GERAL = "parte_geral"
    PARTE_ESPECIAL = "parte_especial"


@dataclass(frozen=True, slots=True)
class ModifyingCause:
    """Causa de aumento ou de diminuição de pena (3ª fase), com a fração que o caso aplica.

    `fracao_min`/`fracao_max` vêm do dispositivo (ex.: "de um terço até metade");
    causa de fração fixa deixa `fracao_max` vazio. A fração aplicada é a mínima, a
    menos que `fracao_escolhida` indique outra dentro do intervalo legal — e nesse
    caso a `justificativa` é obrigatória (seção 3.3 do plano; Súmula 443 do STJ).
    """

    codigo: str
    dispositivo: str
    direcao: CauseDirection
    origem: CauseOrigin
    fracao_min: Fraction
    fracao_max: Fraction | None = None
    fracao_escolhida: Fraction | None = None
    justificativa: str | None = None

    def __post_init__(self) -> None:
        minima = racional(self.fracao_min)
        maxima = racional(self.fracao_max or self.fracao_min)
        if minima > maxima:
            raise ValueError(f"{self.codigo}: fração mínima maior que a máxima")
        if self.fracao_escolhida is None:
            return
        escolhida = racional(self.fracao_escolhida)
        if not minima <= escolhida <= maxima:
            raise ValueError(
                f"{self.codigo}: fração escolhida {self.fracao_escolhida} fora do intervalo legal "
                f"({self.fracao_min} a {self.fracao_max or self.fracao_min})"
            )
        if escolhida != minima and not (self.justificativa and self.justificativa.strip()):
            raise ValueError(
                f"{self.codigo}: fração {self.fracao_escolhida} acima da mínima exige justificativa"
            )

    @property
    def fracao_aplicada(self) -> Fraction:
        return self.fracao_escolhida or self.fracao_min

    @property
    def acima_da_minima(self) -> bool:
        return racional(self.fracao_aplicada) != racional(self.fracao_min)


def racional(fracao: Fraction) -> fractions.Fraction:
    """Valor exato da fração, para comparar e compor sem arredondar no meio do cálculo."""
    return fractions.Fraction(fracao.numerador, fracao.denominador)
