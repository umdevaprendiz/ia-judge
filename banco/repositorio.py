"""Operações sobre os casos salvos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from privacidade import anonimizar

from .modelos import CaseRecord


def salvar_caso(sessao: Session, descricao: str, consentimento: bool) -> CaseRecord:
    """Anonimiza a descrição e grava só a versão anonimizada. O texto original é descartado."""
    if not consentimento:
        raise ValueError("é preciso consentir com o armazenamento para salvar o caso")
    anonimizada = anonimizar(descricao)
    caso = CaseRecord(
        descricao=anonimizada.texto,
        anonimizacao=anonimizada.contagem_por_tipo(),
        consentimento=True,
    )
    sessao.add(caso)
    sessao.commit()
    return caso


def obter_caso(sessao: Session, codigo: str) -> CaseRecord | None:
    return sessao.scalar(select(CaseRecord).where(CaseRecord.codigo == codigo))
