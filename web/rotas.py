"""Rotas das páginas para estudantes. As páginas usam a API JSON do próprio serviço."""

import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

PASTA = Path(__file__).resolve().parent
PASTA_ESTATICOS = PASTA / "static"

templates = Jinja2Templates(directory=PASTA / "templates")
# muda a cada deploy, para o navegador não usar CSS/JS antigos do cache
templates.env.globals["versao"] = (os.environ.get("RENDER_GIT_COMMIT") or "dev")[:12]
templates.env.globals["AUTOR"] = "Sérgio Souza"
# função, e não valor fixo, para o ano do rodapé virar sozinho sem precisar de deploy
templates.env.globals["ano_atual"] = lambda: date.today().year

roteador = APIRouter(include_in_schema=False)


def _pagina(request: Request, template: str, titulo: str, atual: str) -> HTMLResponse:
    return templates.TemplateResponse(request, template, {"titulo": titulo, "atual": atual})


@roteador.get("/", response_class=HTMLResponse)
def inicio(request: Request) -> HTMLResponse:
    return _pagina(request, "inicio.html", "Início", "inicio")


@roteador.get("/calcular", response_class=HTMLResponse)
def calcular(request: Request) -> HTMLResponse:
    return _pagina(request, "calcular.html", "Calcular", "calcular")


@roteador.get("/analisar", response_class=HTMLResponse)
def analisar(request: Request) -> HTMLResponse:
    return _pagina(request, "analisar.html", "Analisar caso", "analisar")


@roteador.get("/praticar", response_class=HTMLResponse)
def praticar(request: Request) -> HTMLResponse:
    return _pagina(request, "praticar.html", "Praticar", "praticar")


@roteador.get("/como-funciona", response_class=HTMLResponse)
def como_funciona(request: Request) -> HTMLResponse:
    return _pagina(request, "como_funciona.html", "Como funciona", "como-funciona")
