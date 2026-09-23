"""API HTTP do sergius-ia-Judge.

Rodar localmente:  uvicorn api.app:app --reload
Documentação interativa: http://127.0.0.1:8000/docs
"""

import json
from functools import cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

# API pública e sem login: qualquer site (ex.: uma página feita pelos estudantes) pode chamá-la
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


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
    "list_type": "deve ser uma lista",
    "model_attributes_type": "deve ser um objeto",
    "json_invalid": "JSON inválido",
}


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """Erros de formato da requisição, com mensagens em português e o caminho do campo."""
    detalhes = []
    for item in erro.errors():
        campo = ".".join(str(parte) for parte in item["loc"] if parte != "body")
        if item["type"] == "enum":
            opcoes = item["ctx"]["expected"].replace(" or ", ", ")
            mensagem = f"valor inválido (opções: {opcoes})"
        else:
            mensagem = _MENSAGENS.get(item["type"], item["msg"])
        # em "campo ausente" o input é o objeto pai inteiro, que só polui a resposta
        recebido = None if item["type"] == "missing" else item.get("input")
        detalhes.append({"campo": campo, "mensagem": mensagem, "valor_recebido": recebido})
    return JSONResponse(status_code=422, content={"detail": detalhes})


@app.get("/", tags=["geral"])
def inicio() -> dict:
    return {
        "nome": "sergius-ia-Judge",
        "descricao": "Motor de dosimetria penal para estudo",
        "documentacao": "/docs",
    }


@app.get("/saude", tags=["geral"])
def saude() -> dict:
    return {"status": "ok"}


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


@app.post("/dosimetria/calcular", response_model=SentencingOutput, tags=["dosimetria"])
def calcular(entrada: SentencingRequest) -> dict:
    """Calcula a dosimetria completa: as três fases, o passo a passo, os alertas e a fundamentação."""
    resultado = entrada_de_dict(entrada.model_dump(mode="json")).calcular()
    return resultado_para_dict(resultado)


@app.post("/ensino/comparar", response_model=ComparisonOutput, tags=["ensino"])
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
