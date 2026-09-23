"""Conexão com o MySQL (Aiven em produção, contêiner local nos testes).

Variáveis de ambiente:
- DATABASE_URL: a "Service URI" da Aiven (mysql://<usuario>:<senha>@<host>:<porta>/<banco>?ssl-mode=REQUIRED)
  ou uma URL do SQLAlchemy (mysql+pymysql://...). Sem ela, os recursos que usam banco ficam
  desligados e o resto do site continua funcionando.
- MYSQL_CA_CERT: conteúdo do certificado CA da Aiven (arquivo ca.pem). Com ele, a conexão SSL
  também verifica a identidade do servidor; sem ele, é criptografada mas não verificada.

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


def url_configurada() -> str | None:
    carregar_env_local()
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or None


def banco_configurado() -> bool:
    return url_configurada() is not None


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
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto


@cache
def obter_engine() -> Engine:
    url = url_configurada()
    if url is None:
        raise RuntimeError("DATABASE_URL não configurada")
    url_sqlalchemy, exige_ssl = normalizar_url(url)
    argumentos = {"ssl": _contexto_ssl()} if exige_ssl else {}
    return create_engine(
        url_sqlalchemy,
        connect_args=argumentos,
        pool_pre_ping=True,  # descarta conexões que o servidor fechou por inatividade
        pool_recycle=280,
    )


@cache
def fabrica_de_sessoes() -> sessionmaker:
    return sessionmaker(bind=obter_engine(), expire_on_commit=False)
