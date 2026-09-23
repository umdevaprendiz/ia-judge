"""As três fases do art. 68 do CP e a dosimetria completa que as encadeia."""

from .fase1 import ResultadoFase1, calcular_pena_base
from .fase2 import ResultadoFase2, calcular_pena_intermediaria
from .fase3 import Composicao, OpcaoFase3, ResultadoFase3, calcular_pena_definitiva
from .completa import ResultadoDosimetria, calcular_dosimetria_completa

__all__ = [
    "ResultadoFase1",
    "calcular_pena_base",
    "ResultadoFase2",
    "calcular_pena_intermediaria",
    "Composicao",
    "OpcaoFase3",
    "ResultadoFase3",
    "calcular_pena_definitiva",
    "ResultadoDosimetria",
    "calcular_dosimetria_completa",
]
