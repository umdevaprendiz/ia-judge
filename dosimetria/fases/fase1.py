from dataclasses import dataclass

from ..circunstancias.judiciais import JudicialCircumstance, Assessment
from ..valores.faixa import PenaltyRange
from ..relatorio.passo import Step
from ..valores.pena import Penalty
from ..quantum.estrategias import QuantumStrategy


@dataclass(frozen=True, slots=True)
class Phase1Result:
    pena_base: Penalty
    passo: Step
    alertas: tuple[str, ...] = ()


def calcular_pena_base(
    faixa: PenaltyRange,
    circunstancias: dict[JudicialCircumstance, Assessment],
    estrategia: QuantumStrategy,
) -> Phase1Result:
    """1ª fase do art. 68 do CP: fixa a pena-base a partir das 8 circunstâncias do art. 59.

    Circunstâncias favoráveis ou neutras não alteram a pena-base — ela parte do mínimo
    da faixa. Cada circunstância desfavorável soma um incremento fixo (definido pela
    estratégia de quantum), e o resultado nunca sai da faixa.
    """
    esperadas = set(JudicialCircumstance)
    recebidas = set(circunstancias)
    if recebidas != esperadas:
        faltando = esperadas - recebidas
        desconhecidas = recebidas - esperadas
        raise ValueError(
            "circunstâncias devem cobrir exatamente as 8 do art. 59 "
            f"(faltando={faltando or None}, desconhecidas={desconhecidas or None})"
        )

    desfavoraveis = [
        circunstancia.value
        for circunstancia in JudicialCircumstance
        if circunstancias[circunstancia] is Assessment.DESFAVORAVEL
    ]
    quantidade_desfavoravel = len(desfavoraveis)
    incremento = estrategia.incremento_por_circunstancia(faixa)
    pena_base_bruta = faixa.minimo.mais_dias(incremento.dias * quantidade_desfavoravel)
    pena_base = faixa.limitar(pena_base_bruta)

    if quantidade_desfavoravel:
        motivo = (
            f"{quantidade_desfavoravel} circunstância(s) desfavorável(is) do art. 59 "
            f"({', '.join(desfavoraveis)}), {estrategia.nome} cada"
        )
    else:
        motivo = "nenhuma circunstância desfavorável: pena-base fixada no mínimo da faixa"

    passo = Step(
        fase="1ª fase (pena-base)",
        regra="art. 59 do CP",
        dispositivo=faixa.origem,
        valor_antes=faixa.minimo,
        valor_depois=pena_base,
        motivo=motivo,
    )
    alertas = ()
    if pena_base != pena_base_bruta:
        alertas = (
            f"pena-base calculada ({pena_base_bruta}) passaria do máximo da faixa; "
            f"fixada no máximo ({faixa.maximo})",
        )
    return Phase1Result(pena_base=pena_base, passo=passo, alertas=alertas)
