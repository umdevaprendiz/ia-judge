"""Leitura das sentenças do conjunto de treinamento (PDF) e da dosimetria que elas declaram.

Fica fora do pacote `dosimetria` de propósito: o motor continua sem depender de PDF.
"""

from .leitor import Sentenca, ler_sentencas
from .dosimetria_declarada import DosimetriaDeclarada, eh_penal, extrair_dosimetria_declarada

__all__ = [
    "Sentenca",
    "ler_sentencas",
    "DosimetriaDeclarada",
    "eh_penal",
    "extrair_dosimetria_declarada",
]
