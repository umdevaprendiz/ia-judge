"""Modelos de entrada e saída da API. Geram a documentação interativa em /docs."""

from pydantic import BaseModel, ConfigDict, Field

from dosimetria import (
    CircunstanciaJudicial,
    Composicao,
    Direcao,
    DirecaoCausa,
    OrigemCausa,
)
from dosimetria.entrada import ESTRATEGIAS

PADRAO_FRACAO = r"^\s*\d+\s*/\s*\d+\s*$"  # ex.: "1/3"

EXEMPLO_ENTRADA = {
    "faixa": {"origem": "CP.art155", "minimo": {"anos": 1}, "maximo": {"anos": 4}},
    "circunstancias_desfavoraveis": ["culpabilidade"],
    "agravantes_atenuantes": [
        {"codigo": "reincidencia", "dispositivo": "CP.art61.I", "direcao": "agravante", "preponderante": True}
    ],
    "causas": [
        {
            "codigo": "repouso_noturno",
            "dispositivo": "CP.art155.§1",
            "direcao": "aumento",
            "origem": "parte_especial",
            "fracao_min": "1/3",
        }
    ],
    "estrategia": {"tipo": "fracao_do_intervalo", "fracao": "1/8"},
    "composicao": "cascata",
}


# ---------- entrada ----------


class PenaEntrada(BaseModel):
    """Pena em anos, meses e dias (convenção: 1 ano = 365 dias, 1 mês = 30 dias)."""

    model_config = ConfigDict(extra="forbid")

    anos: int = Field(0, ge=0)
    meses: int = Field(0, ge=0)
    dias: int = Field(0, ge=0)


class FaixaEntrada(BaseModel):
    """Pena em abstrato do tipo penal já escolhido (simples ou qualificado)."""

    origem: str = Field(examples=["CP.art155"], description="Rótulo do dispositivo que define a faixa.")
    minimo: PenaEntrada
    maximo: PenaEntrada


class AgravanteAtenuanteEntrada(BaseModel):
    codigo: str = Field(examples=["reincidencia"])
    dispositivo: str = Field(examples=["CP.art61.I"])
    direcao: Direcao
    preponderante: bool = Field(
        False, description="Motivos determinantes, personalidade ou reincidência (art. 67 do CP)."
    )


class CausaEntrada(BaseModel):
    """Causa de aumento ou de diminuição (3ª fase)."""

    codigo: str = Field(examples=["repouso_noturno"])
    dispositivo: str = Field(examples=["CP.art155.§1"])
    direcao: DirecaoCausa
    origem: OrigemCausa
    fracao_min: str = Field(pattern=PADRAO_FRACAO, examples=["1/3"])
    fracao_max: str | None = Field(None, pattern=PADRAO_FRACAO, description="Vazio quando a fração é fixa.")
    fracao_escolhida: str | None = Field(
        None,
        pattern=PADRAO_FRACAO,
        description="Outra fração dentro do intervalo legal; exige justificativa.",
    )
    justificativa: str | None = None


class EstrategiaEntrada(BaseModel):
    tipo: str = Field(
        examples=["fracao_do_intervalo"], description=f"Opções: {', '.join(ESTRATEGIAS)}."
    )
    fracao: str = Field(pattern=PADRAO_FRACAO, examples=["1/8"])


class EntradaDosimetria(BaseModel):
    """Os fatos do caso já classificados, prontos para as três fases do art. 68 do CP."""

    model_config = ConfigDict(json_schema_extra={"examples": [EXEMPLO_ENTRADA]})

    faixa: FaixaEntrada
    circunstancias_desfavoraveis: list[CircunstanciaJudicial] = Field(
        default_factory=list, description="Circunstâncias do art. 59 valoradas contra o réu."
    )
    agravantes_atenuantes: list[AgravanteAtenuanteEntrada] = Field(default_factory=list)
    causas: list[CausaEntrada] = Field(default_factory=list)
    estrategia: EstrategiaEntrada
    composicao: Composicao


class RespostaEstudante(BaseModel):
    """A dosimetria feita pelo estudante. Preencha só as fases que quiser corrigir."""

    pena_base: PenaEntrada | None = None
    pena_intermediaria: PenaEntrada | None = None
    pena_definitiva: PenaEntrada | None = None


class PedidoComparacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entrada": EXEMPLO_ENTRADA,
                    "resposta": {
                        "pena_base": {"anos": 1, "meses": 4, "dias": 16},
                        "pena_intermediaria": {"anos": 1, "meses": 9, "dias": 2},
                        "pena_definitiva": {"anos": 2, "meses": 4},
                    },
                }
            ]
        }
    )

    entrada: EntradaDosimetria
    resposta: RespostaEstudante


# ---------- saída ----------


class PenaSaida(BaseModel):
    total_dias: int
    anos: int
    meses: int
    dias: int
    texto: str


class FaixaSaida(BaseModel):
    origem: str
    minimo: PenaSaida
    maximo: PenaSaida


class PassoSaida(BaseModel):
    fase: str
    regra: str
    dispositivo: str
    valor_antes: PenaSaida
    valor_depois: PenaSaida
    motivo: str


class AlternativaSaida(BaseModel):
    descricao: str
    pena_definitiva: PenaSaida
    passos: list[PassoSaida]


class ResultadoSaida(BaseModel):
    faixa_aplicada: FaixaSaida
    pena_base: PenaSaida
    pena_intermediaria: PenaSaida
    pena_definitiva: PenaSaida
    alternativa_art68: AlternativaSaida | None
    passos: list[PassoSaida]
    criterio_quantum: str
    composicao: str
    alertas: list[str]
    fundamentacao: str = Field(description="Texto da dosimetria para leitura humana.")


class ComparacaoFaseSaida(BaseModel):
    fase: str
    correta: bool
    esperado: PenaSaida
    resposta: PenaSaida
    diferenca_dias: int = Field(description="Positivo: a resposta ficou acima da pena do motor.")
    explicacao: list[str] = Field(description="Como o motor chegou à pena desta fase.")
    observacao: str | None


class ComparacaoSaida(BaseModel):
    acertos: int
    total: int
    fases: list[ComparacaoFaseSaida]
    gabarito: ResultadoSaida


class Opcoes(BaseModel):
    circunstancias_judiciais: list[str]
    direcoes_agravante_atenuante: list[str]
    direcoes_causa: list[str]
    origens_causa: list[str]
    estrategias: list[str]
    composicoes: list[str]


class ExemploResumo(BaseModel):
    id: str
    descricao: str
    fonte: str


class Exemplo(ExemploResumo):
    entrada: EntradaDosimetria
