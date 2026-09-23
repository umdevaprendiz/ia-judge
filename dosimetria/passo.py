from dataclasses import dataclass

from .pena import Pena


@dataclass(frozen=True, slots=True)
class Passo:
    """Um passo do cálculo, para compor o relatório explicativo (ResultadoDosimetria)."""

    fase: str
    regra: str
    dispositivo: str
    valor_antes: Pena
    valor_depois: Pena
    motivo: str
