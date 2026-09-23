"""Ambiente do Alembic: usa a mesma conexão do app (banco/config.py)."""

from alembic import context

from banco.config import obter_engine
from banco.modelos import Base

target_metadata = Base.metadata


def rodar_migracoes() -> None:
    with obter_engine().connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


rodar_migracoes()
