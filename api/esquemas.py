"""Modelos de entrada e saída da API. Geram a documentação interativa em /docs."""

from pydantic import BaseModel, ConfigDict, Field

from dosimetria import (
    JudicialCircumstance,
    Composition,
    CircumstanceDirection,
    CauseDirection,
    CauseOrigin,
)
from dosimetria.entrada import ESTRATEGIAS

PADRAO_FRACAO = r"^\s*\d{1,4}\s*/\s*\d{1,4}\s*$"  # ex.: "1/3" (até 4 dígitos: frações legais são pequenas)

# limites de tamanho: bem acima de qualquer caso real, e baixos o bastante para uma
# requisição não ocupar o servidor (a maior pena em abstrato do CP é de 30 anos)
MAXIMO_ANOS = 1000
TEXTO_CURTO = 100
TEXTO_LONGO = 2000

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


class PenaltyInput(BaseModel):
    """Pena em anos, meses e dias (convenção: 1 ano = 365 dias, 1 mês = 30 dias)."""

    model_config = ConfigDict(extra="forbid")

    anos: int = Field(0, ge=0, le=MAXIMO_ANOS)
    meses: int = Field(0, ge=0, le=MAXIMO_ANOS * 12)
    dias: int = Field(0, ge=0, le=MAXIMO_ANOS * 365)


class PenaltyRangeInput(BaseModel):
    """Pena em abstrato do tipo penal já escolhido (simples ou qualificado)."""

    origem: str = Field(
        min_length=1, max_length=TEXTO_CURTO, examples=["CP.art155"], description="Rótulo do dispositivo que define a faixa."
    )
    minimo: PenaltyInput
    maximo: PenaltyInput


class AggravatingMitigatingInput(BaseModel):
    codigo: str = Field(min_length=1, max_length=TEXTO_CURTO, examples=["reincidencia"])
    dispositivo: str = Field(min_length=1, max_length=TEXTO_CURTO, examples=["CP.art61.I"])
    direcao: CircumstanceDirection
    preponderante: bool = Field(
        False, description="Motivos determinantes, personalidade ou reincidência (art. 67 do CP)."
    )


class CauseInput(BaseModel):
    """Causa de aumento ou de diminuição (3ª fase)."""

    codigo: str = Field(min_length=1, max_length=TEXTO_CURTO, examples=["repouso_noturno"])
    dispositivo: str = Field(min_length=1, max_length=TEXTO_CURTO, examples=["CP.art155.§1"])
    direcao: CauseDirection
    origem: CauseOrigin
    fracao_min: str = Field(pattern=PADRAO_FRACAO, examples=["1/3"])
    fracao_max: str | None = Field(None, pattern=PADRAO_FRACAO, description="Vazio quando a fração é fixa.")
    fracao_escolhida: str | None = Field(
        None,
        pattern=PADRAO_FRACAO,
        description="Outra fração dentro do intervalo legal; exige justificativa.",
    )
    justificativa: str | None = Field(None, max_length=TEXTO_LONGO)


class StrategyInput(BaseModel):
    tipo: str = Field(
        max_length=TEXTO_CURTO,
        examples=["fracao_do_intervalo"], description=f"Opções: {', '.join(ESTRATEGIAS)}."
    )
    fracao: str = Field(pattern=PADRAO_FRACAO, examples=["1/8"])


class SentencingRequest(BaseModel):
    """Os fatos do caso já classificados, prontos para as três fases do art. 68 do CP."""

    model_config = ConfigDict(json_schema_extra={"examples": [EXEMPLO_ENTRADA]})

    faixa: PenaltyRangeInput
    circunstancias_desfavoraveis: list[JudicialCircumstance] = Field(
        default_factory=list, max_length=8, description="Circunstâncias do art. 59 valoradas contra o réu."
    )
    agravantes_atenuantes: list[AggravatingMitigatingInput] = Field(default_factory=list, max_length=30)
    causas: list[CauseInput] = Field(default_factory=list, max_length=20)
    estrategia: StrategyInput
    composicao: Composition


class StudentAnswer(BaseModel):
    """A dosimetria feita pelo estudante. Preencha só as fases que quiser corrigir."""

    pena_base: PenaltyInput | None = None
    pena_intermediaria: PenaltyInput | None = None
    pena_definitiva: PenaltyInput | None = None


class ComparisonRequest(BaseModel):
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

    entrada: SentencingRequest
    resposta: StudentAnswer


# ---------- saída ----------


class PenaltyOutput(BaseModel):
    total_dias: int
    anos: int
    meses: int
    dias: int
    texto: str


class PenaltyRangeOutput(BaseModel):
    origem: str
    minimo: PenaltyOutput
    maximo: PenaltyOutput


class StepOutput(BaseModel):
    fase: str
    regra: str
    dispositivo: str
    valor_antes: PenaltyOutput
    valor_depois: PenaltyOutput
    motivo: str


class AlternativeOutput(BaseModel):
    descricao: str
    pena_definitiva: PenaltyOutput
    passos: list[StepOutput]


class SentencingOutput(BaseModel):
    faixa_aplicada: PenaltyRangeOutput
    pena_base: PenaltyOutput
    pena_intermediaria: PenaltyOutput
    pena_definitiva: PenaltyOutput
    alternativa_art68: AlternativeOutput | None
    passos: list[StepOutput]
    criterio_quantum: str
    composicao: str
    alertas: list[str]
    fundamentacao: str = Field(description="Texto da dosimetria para leitura humana.")


class PhaseComparisonOutput(BaseModel):
    fase: str
    correta: bool
    esperado: PenaltyOutput
    resposta: PenaltyOutput
    diferenca_dias: int = Field(description="Positivo: a resposta ficou acima da pena do motor.")
    explicacao: list[str] = Field(description="Como o motor chegou à pena desta fase.")
    observacao: str | None


class ComparisonOutput(BaseModel):
    acertos: int
    total: int
    fases: list[PhaseComparisonOutput]
    gabarito: SentencingOutput


class Options(BaseModel):
    circunstancias_judiciais: list[str]
    direcoes_agravante_atenuante: list[str]
    direcoes_causa: list[str]
    origens_causa: list[str]
    estrategias: list[str]
    composicoes: list[str]


class ExampleSummary(BaseModel):
    id: str
    descricao: str
    fonte: str


class Example(ExampleSummary):
    entrada: SentencingRequest
