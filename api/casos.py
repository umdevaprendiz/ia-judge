"""Rotas dos casos descritos pelos estudantes (aba "Analisar caso")."""

import logging
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import banco_configurado, fabrica_de_sessoes, obter_caso, salvar_caso
from privacy import anonimizar

from .seguranca import RateLimiter

log = logging.getLogger(__name__)

TAMANHO_MINIMO = 50
TAMANHO_MAXIMO = 20_000
CODIGO = Path(pattern=r"^[A-Za-z0-9_-]{8,16}$", description="Código recebido ao salvar o caso.")

limite_previa = RateLimiter("previa", limite=30, janela=600, limite_global=1000)
limite_salvar = RateLimiter("salvar", limite=5, janela=600, limite_global=200)
limite_consulta = RateLimiter("consulta", limite=60, janela=60, limite_global=2000)
limite_exclusao = RateLimiter("exclusao", limite=10, janela=600, limite_global=300)

roteador = APIRouter(prefix="/casos", tags=["casos"])


class CaseDescription(BaseModel):
    descricao: str = Field(
        min_length=TAMANHO_MINIMO,
        max_length=TAMANHO_MAXIMO,
        description="Descrição detalhada do caso. Nomes e documentos são anonimizados antes de gravar.",
    )


class CaseSubmission(CaseDescription):
    consentimento: bool = Field(
        description="Concordância com a gravação da descrição anonimizada e, depois de validada, com o uso para ensinar o agente."
    )


class ReplacementOutput(BaseModel):
    tipo: str
    original: str
    marcador: str


class PreviewOutput(BaseModel):
    descricao_anonimizada: str
    substituicoes: list[ReplacementOutput]
    contagem: dict[str, int]


class CaseOutput(BaseModel):
    codigo: str
    criado_em: datetime
    status: str
    descricao: str
    anonimizacao: dict[str, int]


def obter_sessao() -> Iterator[Session]:
    if not banco_configurado():
        raise HTTPException(503, "O armazenamento de casos não está disponível neste servidor no momento.")
    sessao = fabrica_de_sessoes()()
    try:
        yield sessao
    except SQLAlchemyError as erro:
        sessao.rollback()
        # registra só o tipo do erro: a mensagem pode conter detalhes da conexão
        log.error("falha no banco de dados: %s", type(erro).__name__)
        raise HTTPException(503, "O banco de dados está indisponível. Tente de novo em instantes.") from None
    finally:
        sessao.close()


def _saida(caso) -> dict:
    return {
        "codigo": caso.codigo,
        "criado_em": caso.criado_em,
        "status": caso.status,
        "descricao": caso.descricao,
        "anonimizacao": caso.anonimizacao,
    }


@roteador.post("/previa", response_model=PreviewOutput, dependencies=[Depends(limite_previa)])
def previa(entrada: CaseDescription) -> dict:
    """Mostra como a descrição ficaria depois de anonimizada. Não grava nada."""
    resultado = anonimizar(entrada.descricao)
    return {
        "descricao_anonimizada": resultado.texto,
        "substituicoes": [
            {"tipo": s.tipo, "original": s.original, "marcador": s.marcador} for s in resultado.substituicoes
        ],
        "contagem": resultado.contagem_por_tipo(),
    }


@roteador.post("", response_model=CaseOutput, status_code=201, dependencies=[Depends(limite_salvar)])
def salvar(entrada: CaseSubmission, sessao: Session = Depends(obter_sessao)) -> dict:
    """Anonimiza e grava o caso. O texto original é descartado e nunca chega ao banco."""
    if not entrada.consentimento:
        raise HTTPException(422, "Para salvar o caso, é preciso marcar a concordância com o armazenamento.")
    return _saida(salvar_caso(sessao, entrada.descricao, consentimento=True))


@roteador.get("/{codigo}", response_model=CaseOutput, dependencies=[Depends(limite_consulta)])
def consultar(codigo: str = CODIGO, sessao: Session = Depends(obter_sessao)) -> dict:
    caso = obter_caso(sessao, codigo)
    if caso is None:
        raise HTTPException(404, "Caso não encontrado.")
    return _saida(caso)


@roteador.delete("/{codigo}", status_code=204, dependencies=[Depends(limite_exclusao)])
def excluir(codigo: str = CODIGO, sessao: Session = Depends(obter_sessao)) -> Response:
    """Apaga o caso (direito de exclusão, LGPD). Quem tem o código é quem enviou o caso."""
    caso = obter_caso(sessao, codigo)
    if caso is None:
        raise HTTPException(404, "Caso não encontrado.")
    sessao.delete(caso)
    sessao.commit()
    return Response(status_code=204)
