"""Aplica as migrações pendentes: python -m banco.migrar

Roda na inicialização do contêiner da API. Sem DATABASE_URL, não faz nada (o site
funciona sem os recursos que dependem de banco). Depois das migrações, apaga os casos
que passaram do prazo de guarda (banco/repositorio.py).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import RAIZ, banco_configurado, bloqueio_de_seguranca, fabrica_de_sessoes, url_configurada
from .repositorio import apagar_casos_expirados


def migrar() -> bool:
    if url_configurada() is None:
        print("banco: DATABASE_URL não configurada; migrações não aplicadas")
        return False
    if not banco_configurado():
        # o site sobe mesmo assim, só sem os recursos que usam banco
        print(f"banco: DESLIGADO por segurança: {bloqueio_de_seguranca()}")
        return False
    configuracao = Config(str(Path(RAIZ) / "alembic.ini"))
    configuracao.set_main_option("script_location", str(Path(RAIZ) / "migracoes"))
    command.upgrade(configuracao, "head")
    print("banco: migrações aplicadas")
    with fabrica_de_sessoes()() as sessao:
        print(f"banco: {apagar_casos_expirados(sessao)} caso(s) apagado(s) por prazo de guarda")
    return True


if __name__ == "__main__":
    migrar()
