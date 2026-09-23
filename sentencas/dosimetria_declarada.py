import re
from dataclasses import dataclass

from dosimetria import Penalty

from .leitor import CourtDecision

# "2 anos", "2 (dois) anos", "1 ano, 4 meses e 10 dias": número, extenso opcional, unidade
_QUANTIDADE = re.compile(r"(\d+)\s*(?:\([^)]*\)\s*)?(anos?|m[eê]s(?:es)?|dias?)\b(?!-multa)", re.IGNORECASE)
_PENA_BASE = re.compile(r"pena-base[^.]*?\bem\s+(.+?)\s+de\s+(?:reclusão|detenção)", re.IGNORECASE)
_PENA_DEFINITIVA = re.compile(r"pena definitiva\s+(?:em|de)\s+(.+?)\s+de\s+(?:reclusão|detenção)", re.IGNORECASE)
_DIAS_MULTA = re.compile(r"(\d+)\s*(?:\([^)]*\)\s*)?dias-multa", re.IGNORECASE)
_REGIME = re.compile(r"regime inicial\s+(\w+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DeclaredSentencing:
    """O que a própria sentença diz sobre a pena, para comparar com o cálculo do motor.

    Extração por regras, feita para o formato do conjunto de treinamento. Não substitui
    a etapa de extração com LLM do plano: serve de referência para testar o motor.
    """

    trecho: str
    pena_base: Penalty | None
    pena_definitiva: Penalty | None
    dias_multa: int | None
    regime_inicial: str | None


def eh_penal(sentenca: CourtDecision) -> bool:
    return sentenca.ramo.lower().startswith("direito penal")


def extrair_dosimetria_declarada(sentenca: CourtDecision) -> DeclaredSentencing | None:
    """Devolve a dosimetria escrita no dispositivo, ou None se a sentença não tiver uma."""
    inicio = sentenca.dispositivo.find("Dosimetria:")
    if not eh_penal(sentenca) or inicio == -1:
        return None
    trecho = sentenca.dispositivo[inicio:]

    dias_multa = _DIAS_MULTA.search(trecho)
    regime = _REGIME.search(trecho)
    return DeclaredSentencing(
        trecho=trecho,
        pena_base=_pena(_PENA_BASE.search(trecho)),
        pena_definitiva=_pena(_PENA_DEFINITIVA.search(trecho)),
        dias_multa=int(dias_multa.group(1)) if dias_multa else None,
        regime_inicial=regime.group(1).lower() if regime else None,
    )


def _pena(match: re.Match | None) -> Penalty | None:
    if match is None:
        return None
    anos = meses = dias = 0
    for numero, unidade in _QUANTIDADE.findall(match.group(1)):
        unidade = unidade.lower()
        if unidade.startswith("ano"):
            anos += int(numero)
        elif unidade.startswith("m"):
            meses += int(numero)
        else:
            dias += int(numero)
    if not (anos or meses or dias):
        return None
    return Penalty.de_anos_meses_dias(anos=anos, meses=meses, dias=dias)
