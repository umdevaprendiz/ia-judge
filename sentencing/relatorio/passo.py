from dataclasses import dataclass

from ..valores.pena import Penalty


@dataclass(frozen=True, slots=True)
class Step:
    """Um passo do cálculo, para compor o relatório explicativo (SentencingResult)."""

    fase: str
    regra: str
    dispositivo: str
    valor_antes: Penalty
    valor_depois: Penalty
    motivo: str
