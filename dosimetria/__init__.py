"""Motor de dosimetria penal (sistema trifásico do art. 68 do CP), em Python puro.

A API pública é reexportada aqui: `from dosimetria import Pena, calcular_dosimetria_completa`.
"""

from .valores import Faixa, Fracao, Pena
from .circunstancias import (
    CausaModificadora,
    CircunstanciaJudicial,
    CircunstanciaLegal,
    Direcao,
    DirecaoCausa,
    OrigemCausa,
    Valoracao,
)
from .quantum import EstrategiaQuantum, FracaoDoIntervalo, FracaoDoMinimo
from .relatorio import Passo, gerar_fundamentacao, pena_para_dict, resultado_para_dict
from .fases import (
    Composicao,
    OpcaoFase3,
    ResultadoDosimetria,
    ResultadoFase1,
    ResultadoFase2,
    ResultadoFase3,
    calcular_dosimetria_completa,
    calcular_pena_base,
    calcular_pena_definitiva,
    calcular_pena_intermediaria,
)
from .entrada import EntradaDosimetria, entrada_de_dict

__all__ = [
    "Fracao",
    "Pena",
    "Faixa",
    "CircunstanciaJudicial",
    "Valoracao",
    "Passo",
    "EstrategiaQuantum",
    "FracaoDoIntervalo",
    "FracaoDoMinimo",
    "ResultadoFase1",
    "calcular_pena_base",
    "CircunstanciaLegal",
    "Direcao",
    "ResultadoFase2",
    "calcular_pena_intermediaria",
    "CausaModificadora",
    "DirecaoCausa",
    "OrigemCausa",
    "Composicao",
    "OpcaoFase3",
    "ResultadoFase3",
    "calcular_pena_definitiva",
    "ResultadoDosimetria",
    "calcular_dosimetria_completa",
    "gerar_fundamentacao",
    "pena_para_dict",
    "resultado_para_dict",
    "EntradaDosimetria",
    "entrada_de_dict",
]
