from dataclasses import dataclass

from ..circunstancias.legais import LegalCircumstance
from ..circunstancias.causas import ModifyingCause
from ..circunstancias.judiciais import JudicialCircumstance, Assessment
from ..valores.faixa import PenaltyRange
from .fase1 import calcular_pena_base
from .fase2 import calcular_pena_intermediaria
from .fase3 import Composition, Phase3Option, calcular_pena_definitiva
from ..relatorio.passo import Step
from ..valores.pena import Penalty
from ..quantum.estrategias import QuantumStrategy


@dataclass(frozen=True, slots=True)
class SentencingResult:
    """Saída do motor (seção 7.2 do plano): as três penas, o passo a passo e os alertas.

    `pena_definitiva` e `passos` aplicam todas as causas da 3ª fase. Quando há
    concurso de causas da Parte Especial, `alternativa_art68` traz a outra opção do
    art. 68, parágrafo único (com os passos só da 3ª fase); a escolha é do juiz.
    """

    faixa_aplicada: PenaltyRange
    pena_base: Penalty
    pena_intermediaria: Penalty
    pena_definitiva: Penalty
    alternativa_art68: Phase3Option | None
    passos: tuple[Step, ...]
    criterio_quantum: str
    composicao: Composition
    alertas: tuple[str, ...]


def calcular_dosimetria_completa(
    faixa: PenaltyRange,
    circunstancias_judiciais: dict[JudicialCircumstance, Assessment],
    agravantes_atenuantes: list[LegalCircumstance],
    causas: list[ModifyingCause],
    estrategia: QuantumStrategy,
    composicao: Composition,
) -> SentencingResult:
    """Sistema trifásico do art. 68 do CP: encadeia as três fases e monta o relatório.

    A faixa já deve ser a aplicada (simples ou qualificada): escolher a faixa é tarefa
    de quem monta o caso, não do motor. Estratégia de quantum e composição da 3ª fase
    são sempre explícitas.
    """
    fase1 = calcular_pena_base(faixa, circunstancias_judiciais, estrategia)
    fase2 = calcular_pena_intermediaria(faixa, fase1.pena_base, agravantes_atenuantes, estrategia)
    fase3 = calcular_pena_definitiva(fase2.pena_intermediaria, causas, composicao)

    pena_definitiva = fase3.aplicando_todas.pena_definitiva
    alertas = [*fase1.alertas, *fase2.alertas]
    if not faixa.contem(pena_definitiva):
        lado = "acima do máximo" if pena_definitiva > faixa.maximo else "abaixo do mínimo"
        alertas.append(
            f"pena definitiva {lado} da faixa ({faixa.minimo} a {faixa.maximo}), "
            "o que é permitido na 3ª fase"
        )
    if fase3.limitada_art68 is not None:
        alertas.append(
            "concurso de causas da Parte Especial: há duas opções de pena definitiva "
            f"({pena_definitiva} ou {fase3.limitada_art68.pena_definitiva}); "
            "a escolha é do juiz (art. 68, parágrafo único, do CP)"
        )

    return SentencingResult(
        faixa_aplicada=faixa,
        pena_base=fase1.pena_base,
        pena_intermediaria=fase2.pena_intermediaria,
        pena_definitiva=pena_definitiva,
        alternativa_art68=fase3.limitada_art68,
        passos=(fase1.passo, fase2.passo, *fase3.aplicando_todas.passos),
        criterio_quantum=estrategia.nome,
        composicao=composicao,
        alertas=tuple(alertas),
    )
