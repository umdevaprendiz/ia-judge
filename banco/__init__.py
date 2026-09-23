"""Persistência em MySQL: configuração, tabelas, migrações e operações sobre os casos."""

from .config import banco_configurado, fabrica_de_sessoes, obter_engine
from .modelos import Base, CaseRecord, CaseStatus
from .repositorio import obter_caso, salvar_caso

__all__ = [
    "banco_configurado",
    "fabrica_de_sessoes",
    "obter_engine",
    "Base",
    "CaseRecord",
    "CaseStatus",
    "obter_caso",
    "salvar_caso",
]
