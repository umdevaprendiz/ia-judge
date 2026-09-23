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
    CausaModificadora,
    CircunstanciaJudicial,
    CircunstanciaLegal,
    Direcao,
    DirecaoCausa,
    OrigemCausa,
    Valoracao,
)
from .fases import Composicao, ResultadoDosimetria, calcular_dosimetria_completa
from .quantum import EstrategiaQuantum, FracaoDoIntervalo, FracaoDoMinimo
from .valores import Faixa, Fracao, Pena

ESTRATEGIAS = {"fracao_do_intervalo": FracaoDoIntervalo, "fracao_do_minimo": FracaoDoMinimo}


@dataclass(frozen=True)
class EntradaDosimetria:
    """Tudo o que o motor precisa para calcular uma dosimetria completa."""

    faixa: Faixa
    circunstancias_judiciais: dict[CircunstanciaJudicial, Valoracao]
    agravantes_atenuantes: tuple[CircunstanciaLegal, ...]
    causas: tuple[CausaModificadora, ...]
    estrategia: EstrategiaQuantum
    composicao: Composicao

    def calcular(self) -> ResultadoDosimetria:
        return calcular_dosimetria_completa(
            self.faixa,
            self.circunstancias_judiciais,
            list(self.agravantes_atenuantes),
            list(self.causas),
            self.estrategia,
            self.composicao,
        )


def entrada_de_dict(dados: dict[str, Any]) -> EntradaDosimetria:
    faixa = _obrigatorio(dados, "faixa", "entrada")
    desfavoraveis = [
        _enum(CircunstanciaJudicial, nome, "circunstancias_desfavoraveis")
        for nome in dados.get("circunstancias_desfavoraveis", [])
    ]
    circunstancias = {
        c: Valoracao.DESFAVORAVEL if c in desfavoraveis else Valoracao.NEUTRA
        for c in CircunstanciaJudicial
    }
    estrategia = _obrigatorio(dados, "estrategia", "entrada")
    tipo = _obrigatorio(estrategia, "tipo", "estrategia")
    if tipo not in ESTRATEGIAS:
        raise ValueError(f"estrategia.tipo inválido: {tipo!r} (opções: {', '.join(ESTRATEGIAS)})")

    return EntradaDosimetria(
        faixa=Faixa(
            minimo=pena_de_dict(_obrigatorio(faixa, "minimo", "faixa")),
            maximo=pena_de_dict(_obrigatorio(faixa, "maximo", "faixa")),
            origem=_obrigatorio(faixa, "origem", "faixa"),
        ),
        circunstancias_judiciais=circunstancias,
        agravantes_atenuantes=tuple(
            CircunstanciaLegal(
                codigo=_obrigatorio(item, "codigo", "agravantes_atenuantes"),
                dispositivo=_obrigatorio(item, "dispositivo", "agravantes_atenuantes"),
                direcao=_enum(Direcao, _obrigatorio(item, "direcao", "agravantes_atenuantes"), "direcao"),
                preponderante=bool(item.get("preponderante", False)),
            )
            for item in dados.get("agravantes_atenuantes", [])
        ),
        causas=tuple(_causa_de_dict(item) for item in dados.get("causas", [])),
        estrategia=ESTRATEGIAS[tipo](fracao_de_texto(_obrigatorio(estrategia, "fracao", "estrategia"))),
        composicao=_enum(Composicao, _obrigatorio(dados, "composicao", "entrada"), "composicao"),
    )


def pena_de_dict(dados: dict[str, int]) -> Pena:
    desconhecidas = set(dados) - {"anos", "meses", "dias"}
    if desconhecidas:
        raise ValueError(f"pena com campos desconhecidos: {sorted(desconhecidas)} (use anos, meses, dias)")
    valores = {k: int(v) for k, v in dados.items()}
    negativos = [k for k, v in valores.items() if v < 0]
    if negativos:
        raise ValueError(f"pena com valores negativos: {negativos}")
    return Pena.de_anos_meses_dias(**valores)


def fracao_de_texto(texto: str) -> Fracao:
    numerador, barra, denominador = str(texto).partition("/")
    if not barra or not numerador.strip().isdigit() or not denominador.strip().isdigit():
        raise ValueError(f"fração inválida: {texto!r} (use o formato '1/3')")
    return Fracao(int(numerador), int(denominador))


def _causa_de_dict(item: dict[str, Any]) -> CausaModificadora:
    opcional = lambda chave: fracao_de_texto(item[chave]) if item.get(chave) else None
    return CausaModificadora(
        codigo=_obrigatorio(item, "codigo", "causas"),
        dispositivo=_obrigatorio(item, "dispositivo", "causas"),
        direcao=_enum(DirecaoCausa, _obrigatorio(item, "direcao", "causas"), "direcao"),
        origem=_enum(OrigemCausa, _obrigatorio(item, "origem", "causas"), "origem"),
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
