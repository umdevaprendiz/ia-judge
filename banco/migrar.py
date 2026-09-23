"""Aplica as migrações pendentes: python -m banco.migrar

Roda na inicialização do contêiner da API. Sem DATABASE_URL, não faz nada (o site
funciona sem os recursos que dependem de banco).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import RAIZ, banco_configurado


def migrar() -> bool:
    if not banco_configurado():
        print("banco: DATABASE_URL não configurada; migrações não aplicadas")
        return False
    configuracao = Config(str(Path(RAIZ) / "alembic.ini"))
    configuracao.set_main_option("script_location", str(Path(RAIZ) / "migracoes"))
    command.upgrade(configuracao, "head")
    print("banco: migrações aplicadas")
    return True


if __name__ == "__main__":
    migrar()
