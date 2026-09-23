"""Operações sobre os casos salvos."""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from privacidade import anonimizar

from .modelos import CaseRecord, CaseStatus, _agora

# LGPD (necessidade): casos que não foram validados não ensinam o agente, então não há
# motivo para guardá-los indefinidamente. Os validados ficam até o autor excluí-los.
PRAZO_SEM_VALIDACAO = timedelta(days=90)


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
    # aproveita o envio para aplicar o prazo de guarda (usa o índice status + criado_em)
    apagar_casos_expirados(sessao, confirmar=False)
    sessao.commit()
    return caso


def apagar_casos_expirados(sessao: Session, agora: datetime | None = None, confirmar: bool = True) -> int:
    """Apaga os casos recebidos ou rejeitados há mais de PRAZO_SEM_VALIDACAO. Devolve quantos."""
    limite = (agora or _agora()) - PRAZO_SEM_VALIDACAO
    resultado = sessao.execute(
        delete(CaseRecord).where(
            CaseRecord.status.in_([CaseStatus.RECEBIDO.value, CaseStatus.REJEITADO.value]),
            CaseRecord.criado_em < limite,
        )
    )
    if confirmar:
        sessao.commit()
    return resultado.rowcount


def obter_caso(sessao: Session, codigo: str) -> CaseRecord | None:
    return sessao.scalar(select(CaseRecord).where(CaseRecord.codigo == codigo))
