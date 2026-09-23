"""O que o caso traz para cada fase: circunstâncias judiciais (1ª), agravantes e atenuantes (2ª), causas de aumento e diminuição (3ª)."""

from .judiciais import CircunstanciaJudicial, Valoracao
from .legais import CircunstanciaLegal, Direcao
from .causas import CausaModificadora, DirecaoCausa, OrigemCausa

__all__ = [
    "CircunstanciaJudicial",
    "Valoracao",
    "CircunstanciaLegal",
    "Direcao",
    "CausaModificadora",
    "DirecaoCausa",
    "OrigemCausa",
]
