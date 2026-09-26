"""Conexão com o MySQL (Aiven em produção, contêiner local nos testes).

Variáveis de ambiente:
- DATABASE_URL: a "Service URI" da Aiven (mysql://<usuario>:<senha>@<host>:<porta>/<banco>?ssl-mode=REQUIRED)
  ou uma URL do SQLAlchemy (mysql+pymysql://...). Sem ela, os recursos que usam banco ficam
  desligados e o resto do site continua funcionando.
- MYSQL_CA_CERT: conteúdo do certificado CA da Aiven (arquivo ca.pem). Com ele, a conexão SSL
  também verifica a identidade do servidor. Em produção ele é obrigatório: sem ele, os
  recursos que usam banco ficam desligados (veja bloqueio_de_seguranca).
- DATABASE_URL_MIGRACAO (opcional): usuário com permissão para criar e alterar tabelas, usado
  só pelas migrações. Assim o usuário de DATABASE_URL, que o site usa, pode ter só
  SELECT/INSERT/UPDATE/DELETE. Sem ela, as migrações usam DATABASE_URL.

Localmente, essas variáveis podem vir do arquivo .env na raiz (fora do git; veja
scripts/preparar_ambiente.py). Nenhuma senha fica no código.
"""

import os
import ssl
from functools import cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

RAIZ = Path(__file__).resolve().parent.parent


def carregar_env_local(arquivo: Path = RAIZ / ".env") -> None:
    """Lê o .env local (se existir) sem sobrescrever variáveis já definidas no ambiente."""
    if not arquivo.is_file():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def url_configurada(migracao: bool = False) -> str | None:
    carregar_env_local()
    url = os.environ.get("DATABASE_URL_MIGRACAO", "").strip() if migracao else ""
    url = url or os.environ.get("DATABASE_URL", "").strip()
    return url or None


def em_producao() -> bool:
    """No Render (que sempre define RENDER=true), ou quando EXIGIR_TLS_VERIFICADO=1."""
    return os.environ.get("RENDER") == "true" or os.environ.get("EXIGIR_TLS_VERIFICADO") == "1"


def bloqueio_de_seguranca() -> str | None:
    """Motivo para não usar o banco com a configuração atual, ou None se ela é segura.

    Em produção, a conexão precisa ser TLS com verificação do servidor. Sem o certificado
    CA, alguém no caminho da rede poderia se passar pelo banco e receber a senha e os
    casos. Nesse caso o site continua no ar, mas sem os recursos que usam banco.
    """
    if not em_producao():
        return None
    certificado = os.environ.get("MYSQL_CA_CERT", "").strip()
    if not certificado:
        return "MYSQL_CA_CERT não definido: em produção a conexão com o banco precisa verificar o servidor"
    try:
        ssl.create_default_context(cadata=certificado)
    except (ssl.SSLError, ValueError, TypeError):  # TypeError: texto com caracteres fora do ASCII
        return "MYSQL_CA_CERT inválido: cole o conteúdo completo do ca.pem da Aiven"
    return None


def banco_configurado() -> bool:
    return url_configurada() is not None and bloqueio_de_seguranca() is None


def normalizar_url(url: str) -> tuple[str, bool]:
    """Converte a URI da Aiven para o SQLAlchemy/PyMySQL. Devolve (url, exige_ssl)."""
    partes = urlsplit(url)
    esquema = "mysql+pymysql" if partes.scheme in {"mysql", "mysql+pymysql"} else partes.scheme
    parametros = dict(parse_qsl(partes.query))
    modo_ssl = (parametros.pop("ssl-mode", None) or parametros.pop("ssl_mode", None) or "").upper()
    parametros.setdefault("charset", "utf8mb4")
    exige_ssl = modo_ssl in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}
    return urlunsplit((esquema, partes.netloc, partes.path, urlencode(parametros), "")), exige_ssl


def _contexto_ssl() -> ssl.SSLContext:
    certificado = os.environ.get("MYSQL_CA_CERT", "").strip()
    if certificado:
        return ssl.create_default_context(cadata=certificado)
    if em_producao():
        raise RuntimeError("MYSQL_CA_CERT é obrigatório em produção")
    # só fora de produção: criptografa, mas não confere quem é o servidor
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto


@cache
def obter_engine(migracao: bool = False) -> Engine:
    """Conexão do site ou, com migracao=True, a das migrações (DATABASE_URL_MIGRACAO)."""
    url = url_configurada(migracao)
    if url is None:
        raise RuntimeError("DATABASE_URL não configurada")
    if (motivo := bloqueio_de_seguranca()) is not None:
        raise RuntimeError(motivo)
    url_sqlalchemy, exige_ssl = normalizar_url(url)
    # em produção, TLS sempre, mesmo que a URL não traga ssl-mode
    argumentos = {"ssl": _contexto_ssl()} if exige_ssl or em_producao() else {}
    return create_engine(
        url_sqlalchemy,
        connect_args=argumentos,
        pool_pre_ping=True,  # descarta conexões que o servidor fechou por inatividade
        pool_recycle=280,
    )


@cache
def fabrica_de_sessoes() -> sessionmaker:
    return sessionmaker(bind=obter_engine(), expire_on_commit=False)
