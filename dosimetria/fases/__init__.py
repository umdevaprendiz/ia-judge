"""As três fases do art. 68 do CP e a dosimetria completa que as encadeia."""

from .fase1 import Phase1Result, calcular_pena_base
from .fase2 import Phase2Result, calcular_pena_intermediaria
from .fase3 import Composition, Phase3Option, Phase3Result, calcular_pena_definitiva
from .completa import SentencingResult, calcular_dosimetria_completa

__all__ = [
    "Phase1Result",
    "calcular_pena_base",
    "Phase2Result",
    "calcular_pena_intermediaria",
    "Composition",
    "Phase3Option",
    "Phase3Result",
    "calcular_pena_definitiva",
    "SentencingResult",
    "calcular_dosimetria_completa",
]
