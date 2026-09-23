"""Rotas do agente da aba "Analisar caso". Nada é gravado: a descrição é anonimizada, analisada
e descartada ao fim da requisição."""

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agente.analise import agente
from agente.calculo import montar_entrada
from dosimetria import Composition, JudicialCircumstance, entrada_de_dict, resultado_para_dict
from privacidade import anonimizar

from .esquemas import PADRAO_FRACAO, TEXTO_LONGO, SentencingOutput, SentencingRequest, StrategyInput
from .fontes import ROTULO, com_fontes_citadas
from .seguranca import RateLimiter

limite_agente = RateLimiter("agente", limite=30, janela=60, limite_global=1500)

roteador = APIRouter(prefix="/agente", tags=["agente"], dependencies=[Depends(limite_agente)])

ROTULO_DO_CRIME = r"^[A-Z][A-Z0-9_]{0,11}\.art\d{1,4}(-[A-Z]{1,3})?$"
CODIGO = r"^[a-z_]{2,40}$"
_DROGAS = re.compile(r"tr[áa]fico|drogas?\b|entorpecente|maconha|coca[íi]na|\bcrack\b", re.IGNORECASE)

AVISO_GERAL = (
    "Sugestões do agente, a partir das palavras da descrição: confira cada item antes de calcular. "
    "Ferramenta de estudo; não substitui a análise de um profissional."
)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao: str = Field(min_length=50, max_length=20_000, description="Descrição do caso. Não é gravada.")


class StructureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crime: str = Field(pattern=ROTULO_DO_CRIME, examples=["CP.art155"])
    descricao: str | None = Field(None, max_length=20_000, description="Se enviada, os itens com indício vêm sugeridos.")


class ChosenFraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fracao: str = Field(pattern=PADRAO_FRACAO)
    justificativa: str | None = Field(None, max_length=TEXTO_LONGO)


class AgentCalculationRequest(BaseModel):
    """O que o estudante confirmou: rótulos das formas e causas, códigos das circunstâncias."""

    model_config = ConfigDict(extra="forbid")

    crime: str = Field(pattern=ROTULO_DO_CRIME)
    formas: list[str] = Field(default_factory=list, max_length=20)
    causas: list[str] = Field(default_factory=list, max_length=30)
    fracoes_escolhidas: dict[str, ChosenFraction] = Field(default_factory=dict, max_length=30)
    agravantes: list[str] = Field(default_factory=list, max_length=20)
    atenuantes: list[str] = Field(default_factory=list, max_length=20)
    circunstancias_desfavoraveis: list[JudicialCircumstance] = Field(default_factory=list, max_length=8)
    estrategia: StrategyInput | None = None
    composicao: Composition | None = None

    def validar_formatos(self) -> None:
        for rotulo in [*self.formas, *self.causas, *self.fracoes_escolhidas]:
            if not re.match(ROTULO, rotulo):
                raise ValueError(f"rótulo inválido: {rotulo[:60]!r}")
        for codigo in [*self.agravantes, *self.atenuantes]:
            if not re.match(CODIGO, codigo):
                raise ValueError(f"código inválido: {codigo[:60]!r}")


class AgentCalculationOutput(BaseModel):
    entrada: SentencingRequest
    resultado: SentencingOutput
    alertas: list[str]


def _avisos(descricao: str, crimes: list[dict]) -> list[str]:
    avisos = [AVISO_GERAL]
    if _DROGAS.search(descricao):
        avisos.append(
            "A Lei de Drogas (Lei 11.343/2006) ainda não está na base de legislação: o agente não analisa tráfico."
        )
    if not crimes:
        avisos.append("Não foi possível identificar o crime. Escolha-o na lista ou descreva a conduta com mais detalhes.")
    return avisos


@roteador.post("/analisar")
def analisar(pedido: AnalysisRequest) -> dict:
    """Identifica o crime e devolve a estrutura do mais provável, com os itens sugeridos e a frase de cada sugestão."""
    texto = anonimizar(pedido.descricao).texto
    o_agente = agente()
    crimes = o_agente.identificar(texto)
    return {
        "descricao_anonimizada": texto,
        "crimes": crimes,
        "estrutura": o_agente.estrutura(crimes[0]["rotulo"], texto) if crimes else None,
        "informacoes_ausentes": o_agente.informacoes_ausentes(texto),
        "avisos": _avisos(texto, crimes),
    }


@roteador.post("/estrutura")
def estrutura(pedido: StructureRequest) -> dict:
    """A estrutura de outro crime (quando o estudante troca o crime sugerido)."""
    texto = anonimizar(pedido.descricao).texto if pedido.descricao else ""
    return agente().estrutura(pedido.crime, texto)


@roteador.get("/crimes")
def crimes() -> list[dict]:
    """Todos os crimes que o agente conhece (artigos com pena no caput), para escolher à mão."""
    return [
        {"rotulo": c.rotulo, "nome": c.nome, "lei": c.lei, "nome_lei": c.nome_lei}
        for c in agente().crimes.values()
    ]


@roteador.post("/calcular", response_model=AgentCalculationOutput)
def calcular(escolhas: AgentCalculationRequest) -> dict:
    """Monta a dosimetria com o que o estudante confirmou e calcula as três fases."""
    escolhas.validar_formatos()
    entrada, alertas = montar_entrada(agente(), escolhas.model_dump(mode="json"))
    try:
        validada = SentencingRequest.model_validate(entrada)
    except ValidationError as erro:
        raise ValueError(f"não foi possível montar a dosimetria: {erro.errors()[0]['msg']}") from None
    resultado = entrada_de_dict(validada.model_dump(mode="json")).calcular()
    return {
        "entrada": validada.model_dump(mode="json"),
        "resultado": com_fontes_citadas(resultado_para_dict(resultado), entrada["agravantes_atenuantes"]),
        "alertas": alertas,
    }
