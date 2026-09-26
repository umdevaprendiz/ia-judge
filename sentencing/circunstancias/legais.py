from dataclasses import dataclass
from enum import Enum


class CircumstanceDirection(Enum):
    AGRAVANTE = "agravante"
    ATENUANTE = "atenuante"


@dataclass(frozen=True, slots=True)
class LegalCircumstance:
    """Uma agravante ou atenuante concreta identificada no caso.

    O catálogo fechado de códigos e dispositivos (arts. 61 a 66 do CP) vive na
    camada de dados (seção 6 do plano); o motor só precisa da direção e de saber
    se a circunstância é preponderante (art. 67 do CP), para resolver o concurso.
    Checar bis in idem é responsabilidade do validador, não do motor.
    """

    codigo: str
    dispositivo: str
    direcao: CircumstanceDirection
    preponderante: bool = False
