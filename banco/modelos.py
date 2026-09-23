"""Tabelas do banco (SQLAlchemy). Mudanças de esquema entram por migração em migracoes/."""

import secrets
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CaseStatus(str, Enum):
    """Ciclo de vida de um caso enviado. Só casos validados ensinam o agente."""

    RECEBIDO = "recebido"
    VALIDADO = "validado"
    REJEITADO = "rejeitado"


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gerar_codigo() -> str:
    """Código público do caso: aleatório (não sequencial), para não dar para adivinhar outros."""
    return secrets.token_urlsafe(9)


class CaseRecord(Base):
    """Um caso descrito por um estudante. Guarda só o texto já anonimizado."""

    __tablename__ = "casos"
    __table_args__ = (
        Index("ix_casos_status_criado_em", "status", "criado_em"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, default=gerar_codigo)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_agora)
    descricao: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    # só a contagem por tipo ({"PESSOA": 2, "CPF": 1}); os valores originais nunca são guardados
    anonimizacao: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    consentimento: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CaseStatus.RECEBIDO.value)
    validado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # preenchidos pelo agente nas próximas etapas
    fatos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resultado: Mapped[dict | None] = mapped_column(JSON, nullable=True)
