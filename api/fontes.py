"""Rotas da base de legislação (a recuperação do RAG): busca, leis disponíveis e texto de um artigo."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from fontes.busca import LegalSearchIndex, base_de_fontes
from fontes.catalogo import LEIS_CONHECIDAS

from .seguranca import RateLimiter

# edições anteriores a esta data aparecem com aviso de que podem estar desatualizadas
DESATUALIZADA_ANTES_DE = "2020-01"

limite_fontes = RateLimiter("fontes", limite=60, janela=60, limite_global=3000)

roteador = APIRouter(prefix="/fontes", tags=["legislação"], dependencies=[Depends(limite_fontes)])

SIGLA = r"^[A-Z][A-Z0-9_]{0,11}$"
# "CP.art155", "CP.art157.§2-A.I", "CP.art14.parágrafo_único"
ROTULO = r"^[A-Z][A-Z0-9_]{0,11}\.art\d{1,4}(-[A-Z]{1,3})?(\.(§\d{1,3}(-[A-Z]{1,3})?|[IVXLC]{1,8}|[a-z]|parágrafo_único)){0,3}$"


class SourceOutput(BaseModel):
    titulo: str
    atualizado_ate: str
    desatualizada: bool


class ProvisionOutput(BaseModel):
    rotulo: str
    lei: str
    nome_lei: str
    norma: str
    artigo: str
    epigrafe: str
    estrutura: list[str]
    texto: str
    fonte: SourceOutput


class SearchResultOutput(ProvisionOutput):
    trecho: str
    pontuacao: float
    motivo: str


class SearchOutput(BaseModel):
    consulta: str
    resultados: list[SearchResultOutput]
    avisos: list[str]


class LawOutput(BaseModel):
    lei: str
    nome: str
    norma: str
    artigos: int
    fontes: list[SourceOutput]


class ExcerptOutput(BaseModel):
    rotulo: str
    encontrado: bool
    parte_encontrada: bool
    texto: str
    dispositivo: ProvisionOutput | None


def _fonte(base: LegalSearchIndex, fonte_id: str) -> dict:
    fonte = base.fontes[fonte_id]
    return {
        "titulo": fonte["titulo"],
        "atualizado_ate": fonte["atualizado_ate"],
        "desatualizada": fonte["atualizado_ate"] < DESATUALIZADA_ANTES_DE,
    }


def dispositivo_para_dict(base: LegalSearchIndex, dispositivo) -> dict:
    return {
        "rotulo": dispositivo.rotulo,
        "lei": dispositivo.lei,
        "nome_lei": dispositivo.nome_lei,
        "norma": dispositivo.norma,
        "artigo": dispositivo.artigo,
        "epigrafe": dispositivo.epigrafe,
        "estrutura": list(dispositivo.estrutura),
        "texto": dispositivo.texto,
        "fonte": _fonte(base, dispositivo.fonte),
    }


def citar(rotulo: str, base: LegalSearchIndex | None = None) -> dict:
    """O texto de um rótulo citado (CP.art155.§4.IV). Usado também nas citações do cálculo."""
    base = base or base_de_fontes()
    encontrado = base.trecho_do_rotulo(rotulo)
    if encontrado is None:
        return {"rotulo": rotulo, "encontrado": False, "parte_encontrada": False, "texto": "", "dispositivo": None}
    dispositivo, texto, achou_a_parte = encontrado
    return {
        "rotulo": rotulo,
        "encontrado": True,
        "parte_encontrada": achou_a_parte,
        "texto": texto,
        "dispositivo": dispositivo_para_dict(base, dispositivo),
    }


def com_fontes_citadas(resultado: dict, agravantes_atenuantes) -> dict:
    """Acrescenta ao resultado do motor o texto de cada dispositivo citado, conferido na base.

    Rótulo que não está na base volta com encontrado=false: a fundamentação nunca cita um
    texto que não existe (fase 4 do plano, verificador de citações). `agravantes_atenuantes`
    são os da entrada (objetos ou dicionários com "dispositivo"), que não aparecem nos passos.
    """
    passos = list(resultado["passos"])
    if resultado["alternativa_art68"]:
        passos += resultado["alternativa_art68"]["passos"]
    rotulos = [
        resultado["faixa_aplicada"]["origem"],
        "CP.art59",  # 1ª fase
        *(item["dispositivo"] if isinstance(item, dict) else item.dispositivo for item in agravantes_atenuantes),
        "CP.art68",  # o sistema trifásico e o concurso de causas
        *(passo["dispositivo"] for passo in passos),
    ]
    unicos = list(dict.fromkeys(r for r in rotulos if r and r != "-"))[:30]
    return {**resultado, "fontes_citadas": [citar(rotulo) for rotulo in unicos]}


def _nome_da_sigla(sigla: str) -> str:
    for norma, (sigla_conhecida, nome) in LEIS_CONHECIDAS.items():
        if sigla_conhecida == sigla:
            return f"{nome} ({norma})"
    return sigla


@roteador.get("/buscar", response_model=SearchOutput)
def buscar(
    q: str = Query(min_length=2, max_length=300, description="Pergunta ou termos, ex.: furto durante o repouso noturno"),
    lei: str | None = Query(None, pattern=SIGLA, description="Só nesta lei (sigla de GET /fontes/leis), ex.: CP"),
    limite: int = Query(5, ge=1, le=10),
) -> dict:
    """Os artigos de lei que mais respondem à pergunta, com o trecho mais relevante de cada um."""
    base = base_de_fontes()
    avisos = [
        f"{_nome_da_sigla(sigla)} não está na base de legislação; os resultados vêm das leis disponíveis."
        for sigla in base.leis_ausentes(q)
    ]
    resultados = base.buscar(q, lei=lei, limite=limite)
    if not resultados:
        avisos.append("Nenhum artigo encontrado. Tente outras palavras, ou os termos que a lei usa.")
    return {
        "consulta": q,
        "resultados": [
            {**dispositivo_para_dict(base, r.dispositivo), "trecho": r.trecho, "pontuacao": r.pontuacao, "motivo": r.motivo}
            for r in resultados
        ],
        "avisos": avisos,
    }


@roteador.get("/leis", response_model=list[LawOutput])
def leis() -> list[dict]:
    """As leis que estão na base, com a quantidade de artigos e a edição de onde vieram."""
    base = base_de_fontes()
    return [{**item, "fontes": [_fonte(base, fonte_id) for fonte_id in item["fontes"]]} for item in base.leis()]


@roteador.get("/dispositivo/{rotulo}", response_model=ExcerptOutput)
def dispositivo(rotulo: str = Path(pattern=ROTULO, description="Ex.: CP.art155, CP.art155.§4.IV")) -> dict:
    """O texto de um artigo, ou só do parágrafo, inciso ou alínea indicado."""
    citacao = citar(rotulo)
    if not citacao["encontrado"]:
        raise HTTPException(404, "Artigo não encontrado na base de legislação.")
    return citacao
