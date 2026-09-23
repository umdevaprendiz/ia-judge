"""API HTTP do sergius-ia-Judge.

Rodar localmente:  uvicorn api.app:app --reload
Páginas para estudantes: http://127.0.0.1:8000/
Documentação interativa da API: http://127.0.0.1:8000/docs
"""

import json
import os
from functools import cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dosimetria import (
    JudicialCircumstance,
    Composition,
    CircumstanceDirection,
    CauseDirection,
    CauseOrigin,
    comparar_resposta,
    entrada_de_dict,
    pena_para_dict,
    resultado_para_dict,
)
from dosimetria.entrada import ESTRATEGIAS, pena_de_dict

from banco import banco_configurado
from web.rotas import PASTA_ESTATICOS, roteador as rotas_das_paginas

from .casos import roteador as rotas_dos_casos
from .seguranca import RateLimiter, SecurityHeadersMiddleware, cabecalho_de_ip, protecao_de_ip

from .esquemas import (
    ComparisonOutput,
    SentencingRequest,
    Example,
    ExampleSummary,
    Options,
    ComparisonRequest,
    SentencingOutput,
)

ARQUIVO_EXEMPLOS = Path(__file__).resolve().parent.parent / "dados" / "casos" / "dosimetrias.json"

# cálculo e correção: folga para um estudante praticando, sem deixar um script ocupar o servidor
limite_calculo = RateLimiter("calculo", limite=60, janela=60, limite_global=3000)

app = FastAPI(
    title="sergius-ia-Judge",
    version="0.1.0",
    description=(
        "Motor de dosimetria penal (sistema trifásico do art. 68 do CP) para estudo. "
        "Calcula a pena-base, a intermediária e a definitiva com o passo a passo e a "
        "fundamentação, e corrige a dosimetria feita por estudantes.\n\n"
        "**Projeto educacional:** o resultado não substitui a análise de um profissional. "
        "Convenção: 1 ano = 365 dias, 1 mês = 30 dias; frações de dia são desprezadas (art. 11 do CP)."
    ),
)

# Outros sites só podem LER dados públicos (GET). Envios (POST/DELETE) só a partir das nossas
# próprias páginas: assim um site de terceiros não consegue gravar casos em nome de um visitante.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=[])
# adicionado por último = executa primeiro: cabeçalhos de segurança e limite de tamanho em tudo
app.add_middleware(SecurityHeadersMiddleware)

# páginas para estudantes (web/): /, /calcular, /praticar, /como-funciona, e seus CSS/JS
app.include_router(rotas_das_paginas)
app.include_router(rotas_dos_casos)
app.mount("/static", StaticFiles(directory=PASTA_ESTATICOS), name="static")


@app.exception_handler(ValueError)
async def erro_de_entrada(_: Request, erro: ValueError) -> JSONResponse:
    """Regras do motor violadas pela entrada (ex.: fração acima da mínima sem justificativa)."""
    return JSONResponse(status_code=422, content={"detail": str(erro)})


_MENSAGENS = {
    "missing": "campo obrigatório ausente",
    "extra_forbidden": "campo não permitido",
    "string_pattern_mismatch": "formato inválido (frações no formato '1/3')",
    "greater_than_equal": "não pode ser negativo",
    "int_parsing": "deve ser um número inteiro",
    "int_from_float": "deve ser um número inteiro",
    "bool_parsing": "deve ser true ou false",
    "string_type": "deve ser um texto",
    "string_too_short": "não pode ficar vazio",
    "list_type": "deve ser uma lista",
    "model_attributes_type": "deve ser um objeto",
    "json_invalid": "JSON inválido",
}


@app.exception_handler(StarletteHTTPException)
async def erro_http(request: Request, erro: StarletteHTTPException) -> JSONResponse:
    """Traduz a mensagem que o FastAPI dá quando o corpo não é um JSON legível."""
    if erro.status_code == 400 and erro.detail == "There was an error parsing the body":
        return JSONResponse(
            status_code=400,
            content={"detail": "O conteúdo enviado não é um JSON válido (confira a codificação UTF-8)."},
        )
    return await http_exception_handler(request, erro)


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """Erros de formato da requisição, com mensagens em português e o caminho do campo."""
    detalhes = []
    for item in erro.errors():
        campo = ".".join(str(parte) for parte in item["loc"] if parte != "body")
        contexto = item.get("ctx") or {}
        if item["type"] == "string_too_short" and contexto.get("min_length", 0) > 1:
            mensagem = f"precisa ter pelo menos {contexto['min_length']} caracteres"
        elif item["type"] == "string_too_long":
            mensagem = f"pode ter no máximo {contexto.get('max_length')} caracteres"
        elif item["type"] == "too_long":
            mensagem = f"pode ter no máximo {contexto.get('max_length')} itens"
        elif item["type"] == "less_than_equal":
            mensagem = f"não pode passar de {contexto.get('le')}"
        elif item["type"] == "enum":
            opcoes = item["ctx"]["expected"].replace(" or ", ", ")
            mensagem = f"valor inválido (opções: {opcoes})"
        else:
            mensagem = _MENSAGENS.get(item["type"], item["msg"])
        # em "campo ausente" o input é o objeto pai inteiro, que só polui a resposta
        recebido = None if item["type"] == "missing" else item.get("input")
        # não ecoa textos longos (podem trazer dados pessoais e só inflam a resposta)
        if isinstance(recebido, str) and len(recebido) > 60:
            recebido = recebido[:60] + "…"
        elif isinstance(recebido, (dict, list)):
            recebido = None
        detalhes.append({"campo": campo, "mensagem": mensagem, "valor_recebido": recebido})
    return JSONResponse(status_code=422, content={"detail": detalhes})


@app.get("/saude", tags=["geral"])
def saude(request: Request) -> dict:
    """Verificação de funcionamento. `commit` é o commit publicado (definido pelo Render).

    `protecao_ip` diz de onde vem o IP usado no limite de requisições, e se o cabeçalho
    esperado chegou nesta requisição. Não expõe nenhum IP. `banco` diz se a gravação de casos
    está ligada (o motivo, quando desligada, fica só no log do servidor).
    """
    cabecalho = cabecalho_de_ip()
    return {
        "status": "ok",
        "commit": os.environ.get("RENDER_GIT_COMMIT"),
        "banco": "ligado" if banco_configurado() else "desligado",
        "protecao_ip": {
            "origem": protecao_de_ip(),
            "cabecalho_presente": bool(cabecalho and request.headers.get(cabecalho)),
        },
    }


@app.get("/opcoes", response_model=Options, tags=["referência"])
def opcoes() -> Options:
    """Valores aceitos nos campos de escolha da entrada."""
    return Options(
        circunstancias_judiciais=[c.value for c in JudicialCircumstance],
        direcoes_agravante_atenuante=[d.value for d in CircumstanceDirection],
        direcoes_causa=[d.value for d in CauseDirection],
        origens_causa=[o.value for o in CauseOrigin],
        estrategias=list(ESTRATEGIAS),
        composicoes=[c.value for c in Composition],
    )


@app.get("/exemplos", response_model=list[ExampleSummary], tags=["referência"])
def listar_exemplos() -> list[dict]:
    """Casos prontos para testar. Use GET /exemplos/{id} para pegar a entrada de um deles."""
    return [{k: caso[k] for k in ("id", "descricao", "fonte")} for caso in _exemplos().values()]


@app.get("/exemplos/{id_exemplo}", response_model=Example, tags=["referência"])
def obter_exemplo(id_exemplo: str) -> dict:
    """A entrada de um caso de exemplo, pronta para colar em POST /dosimetria/calcular."""
    caso = _exemplos().get(id_exemplo)
    if caso is None:
        raise HTTPException(404, f"exemplo {id_exemplo!r} não existe; veja GET /exemplos")
    return {k: caso[k] for k in ("id", "descricao", "fonte", "entrada")}


@app.post(
    "/dosimetria/calcular", response_model=SentencingOutput, tags=["dosimetria"], dependencies=[Depends(limite_calculo)]
)
def calcular(entrada: SentencingRequest) -> dict:
    """Calcula a dosimetria completa: as três fases, o passo a passo, os alertas e a fundamentação."""
    resultado = entrada_de_dict(entrada.model_dump(mode="json")).calcular()
    return resultado_para_dict(resultado)


@app.post("/ensino/comparar", response_model=ComparisonOutput, tags=["ensino"], dependencies=[Depends(limite_calculo)])
def comparar(pedido: ComparisonRequest) -> dict:
    """Corrige a dosimetria de um estudante, fase a fase, e devolve o gabarito completo."""
    resultado = entrada_de_dict(pedido.entrada.model_dump(mode="json")).calcular()
    resposta = pedido.resposta
    comparacao = comparar_resposta(
        resultado,
        **{
            fase: pena_de_dict(pena.model_dump())
            for fase in ("pena_base", "pena_intermediaria", "pena_definitiva")
            if (pena := getattr(resposta, fase)) is not None
        },
    )
    if comparacao.total == 0:
        raise HTTPException(422, "preencha ao menos uma fase em 'resposta'")
    return {
        "acertos": comparacao.acertos,
        "total": comparacao.total,
        "fases": [
            {
                "fase": fase.fase,
                "correta": fase.correta,
                "esperado": pena_para_dict(fase.esperado),
                "resposta": pena_para_dict(fase.resposta),
                "diferenca_dias": fase.diferenca_dias,
                "explicacao": list(fase.explicacao),
                "observacao": fase.observacao,
            }
            for fase in comparacao.fases
        ],
        "gabarito": resultado_para_dict(resultado),
    }


@cache
def _exemplos() -> dict[str, dict]:
    casos = json.loads(ARQUIVO_EXEMPLOS.read_text(encoding="utf-8"))["casos"]
    return {caso["id"]: caso for caso in casos}
