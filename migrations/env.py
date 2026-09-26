"""Ambiente do Alembic: conexão das migrações (DATABASE_URL_MIGRACAO, ou DATABASE_URL; banco/config.py)."""

from alembic import context

from database.config import obter_engine
from database.modelos import Base

target_metadata = Base.metadata


def rodar_migracoes() -> None:
    with obter_engine(migracao=True).connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


rodar_migracoes()
