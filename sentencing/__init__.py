"""Motor de dosimetria penal (sistema trifásico do art. 68 do CP), em Python puro.

A API pública é reexportada aqui: `from dosimetria import Penalty, calcular_dosimetria_completa`.
"""

from .valores import PenaltyRange, Fraction, Penalty
from .circunstancias import (
    ModifyingCause,
    JudicialCircumstance,
    LegalCircumstance,
    CircumstanceDirection,
    CauseDirection,
    CauseOrigin,
    Assessment,
)
from .quantum import QuantumStrategy, IntervalFraction, MinimumFraction
from .relatorio import Step, gerar_fundamentacao, pena_para_dict, resultado_para_dict
from .fases import (
    Composition,
    Phase3Option,
    SentencingResult,
    Phase1Result,
    Phase2Result,
    Phase3Result,
    calcular_dosimetria_completa,
    calcular_pena_base,
    calcular_pena_definitiva,
    calcular_pena_intermediaria,
)
from .entrada import SentencingInput, entrada_de_dict
from .ensino import PhaseComparison, AnswerComparison, comparar_resposta

__all__ = [
    "Fraction",
    "Penalty",
    "PenaltyRange",
    "JudicialCircumstance",
    "Assessment",
    "Step",
    "QuantumStrategy",
    "IntervalFraction",
    "MinimumFraction",
    "Phase1Result",
    "calcular_pena_base",
    "LegalCircumstance",
    "CircumstanceDirection",
    "Phase2Result",
    "calcular_pena_intermediaria",
    "ModifyingCause",
    "CauseDirection",
    "CauseOrigin",
    "Composition",
    "Phase3Option",
    "Phase3Result",
    "calcular_pena_definitiva",
    "SentencingResult",
    "calcular_dosimetria_completa",
    "gerar_fundamentacao",
    "pena_para_dict",
    "resultado_para_dict",
    "SentencingInput",
    "entrada_de_dict",
    "PhaseComparison",
    "AnswerComparison",
    "comparar_resposta",
]
