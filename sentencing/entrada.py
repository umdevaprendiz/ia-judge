"""Formato de entrada do motor em dicionário/JSON, o mesmo aceito pela API.

Exemplo:

    {
      "faixa": {"origem": "CP.art155", "minimo": {"anos": 1}, "maximo": {"anos": 4}},
      "circunstancias_desfavoraveis": ["culpabilidade"],
      "agravantes_atenuantes": [
        {"codigo": "reincidencia", "dispositivo": "CP.art61.I", "direcao": "agravante", "preponderante": true}
      ],
      "causas": [
        {"codigo": "repouso_noturno", "dispositivo": "CP.art155.§1", "direcao": "aumento",
         "origem": "parte_especial", "fracao_min": "1/3"}
      ],
      "estrategia": {"tipo": "fracao_do_intervalo", "fracao": "1/8"},
      "composicao": "cascata"
    }

Frações são textos "numerador/denominador"; penas são {"anos", "meses", "dias"} (todos
opcionais). Erros de formato viram `ValueError` com mensagem em português.
"""

from dataclasses import dataclass
from typing import Any

from .circunstancias import (
    ModifyingCause,
    JudicialCircumstance,
    LegalCircumstance,
    CircumstanceDirection,
    CauseDirection,
    CauseOrigin,
    Assessment,
)
from .fases import Composition, SentencingResult, calcular_dosimetria_completa
from .quantum import QuantumStrategy, IntervalFraction, MinimumFraction
from .valores import PenaltyRange, Fraction, Penalty

ESTRATEGIAS = {"fracao_do_intervalo": IntervalFraction, "fracao_do_minimo": MinimumFraction}


@dataclass(frozen=True)
class SentencingInput:
    """Tudo o que o motor precisa para calcular uma dosimetria completa."""

    faixa: PenaltyRange
    circunstancias_judiciais: dict[JudicialCircumstance, Assessment]
    agravantes_atenuantes: tuple[LegalCircumstance, ...]
    causas: tuple[ModifyingCause, ...]
    estrategia: QuantumStrategy
    composicao: Composition

    def calcular(self) -> SentencingResult:
        return calcular_dosimetria_completa(
            self.faixa,
            self.circunstancias_judiciais,
            list(self.agravantes_atenuantes),
            list(self.causas),
            self.estrategia,
            self.composicao,
        )


def entrada_de_dict(dados: dict[str, Any]) -> SentencingInput:
    faixa = _obrigatorio(dados, "faixa", "entrada")
    desfavoraveis = [
        _enum(JudicialCircumstance, nome, "circunstancias_desfavoraveis")
        for nome in dados.get("circunstancias_desfavoraveis", [])
    ]
    circunstancias = {
        c: Assessment.DESFAVORAVEL if c in desfavoraveis else Assessment.NEUTRA
        for c in JudicialCircumstance
    }
    estrategia = _obrigatorio(dados, "estrategia", "entrada")
    tipo = _obrigatorio(estrategia, "tipo", "estrategia")
    if tipo not in ESTRATEGIAS:
        raise ValueError(f"estrategia.tipo inválido: {tipo!r} (opções: {', '.join(ESTRATEGIAS)})")

    return SentencingInput(
        faixa=PenaltyRange(
            minimo=pena_de_dict(_obrigatorio(faixa, "minimo", "faixa")),
            maximo=pena_de_dict(_obrigatorio(faixa, "maximo", "faixa")),
            origem=_obrigatorio(faixa, "origem", "faixa"),
        ),
        circunstancias_judiciais=circunstancias,
        agravantes_atenuantes=tuple(
            LegalCircumstance(
                codigo=_obrigatorio(item, "codigo", "agravantes_atenuantes"),
                dispositivo=_obrigatorio(item, "dispositivo", "agravantes_atenuantes"),
                direcao=_enum(CircumstanceDirection, _obrigatorio(item, "direcao", "agravantes_atenuantes"), "direcao"),
                preponderante=bool(item.get("preponderante", False)),
            )
            for item in dados.get("agravantes_atenuantes", [])
        ),
        causas=tuple(_causa_de_dict(item) for item in dados.get("causas", [])),
        estrategia=ESTRATEGIAS[tipo](fracao_de_texto(_obrigatorio(estrategia, "fracao", "estrategia"))),
        composicao=_enum(Composition, _obrigatorio(dados, "composicao", "entrada"), "composicao"),
    )


def pena_de_dict(dados: dict[str, int]) -> Penalty:
    desconhecidas = set(dados) - {"anos", "meses", "dias"}
    if desconhecidas:
        raise ValueError(f"pena com campos desconhecidos: {sorted(desconhecidas)} (use anos, meses, dias)")
    valores = {k: int(v) for k, v in dados.items()}
    negativos = [k for k, v in valores.items() if v < 0]
    if negativos:
        raise ValueError(f"pena com valores negativos: {negativos}")
    return Penalty.de_anos_meses_dias(**valores)


def fracao_de_texto(texto: str) -> Fraction:
    numerador, barra, denominador = str(texto).partition("/")
    if not barra or not numerador.strip().isdigit() or not denominador.strip().isdigit():
        raise ValueError(f"fração inválida: {texto!r} (use o formato '1/3')")
    return Fraction(int(numerador), int(denominador))


def _causa_de_dict(item: dict[str, Any]) -> ModifyingCause:
    opcional = lambda chave: fracao_de_texto(item[chave]) if item.get(chave) else None
    return ModifyingCause(
        codigo=_obrigatorio(item, "codigo", "causas"),
        dispositivo=_obrigatorio(item, "dispositivo", "causas"),
        direcao=_enum(CauseDirection, _obrigatorio(item, "direcao", "causas"), "direcao"),
        origem=_enum(CauseOrigin, _obrigatorio(item, "origem", "causas"), "origem"),
        fracao_min=fracao_de_texto(_obrigatorio(item, "fracao_min", "causas")),
        fracao_max=opcional("fracao_max"),
        fracao_escolhida=opcional("fracao_escolhida"),
        justificativa=item.get("justificativa"),
    )


def _obrigatorio(dados: dict[str, Any], chave: str, onde: str) -> Any:
    if chave not in dados or dados[chave] is None:
        raise ValueError(f"campo obrigatório ausente em {onde}: {chave!r}")
    return dados[chave]


def _enum(tipo, valor, campo):
    try:
        return tipo(valor)
    except ValueError:
        opcoes = ", ".join(membro.value for membro in tipo)
        raise ValueError(f"{campo} inválido: {valor!r} (opções: {opcoes})") from None
