"""Relatório explicativo: o passo a passo do cálculo, o texto da fundamentação e o JSON."""

from .passo import Step
from .fundamentacao import gerar_fundamentacao
from .serializacao import passo_para_dict, pena_para_dict, resultado_para_dict

__all__ = [
    "Step",
    "gerar_fundamentacao",
    "passo_para_dict",
    "pena_para_dict",
    "resultado_para_dict",
]
