from dataclasses import dataclass

from .circunstancias import CircunstanciaJudicial, Valoracao
from .faixa import Faixa
from .passo import Passo
from .pena import Pena
from .quantum import EstrategiaQuantum


@dataclass(frozen=True, slots=True)
class ResultadoFase1:
    pena_base: Pena
    passo: Passo


def calcular_pena_base(
    faixa: Faixa,
    circunstancias: dict[CircunstanciaJudicial, Valoracao],
    estrategia: EstrategiaQuantum,
) -> ResultadoFase1:
    """1ª fase do art. 68 do CP: fixa a pena-base a partir das 8 circunstâncias do art. 59.

    Circunstâncias favoráveis ou neutras não alteram a pena-base — ela parte do mínimo
    da faixa. Cada circunstância desfavorável soma um incremento fixo (definido pela
    estratégia de quantum), e o resultado nunca sai da faixa.
    """
    esperadas = set(CircunstanciaJudicial)
    recebidas = set(circunstancias)
    if recebidas != esperadas:
        faltando = esperadas - recebidas
        desconhecidas = recebidas - esperadas
        raise ValueError(
            "circunstâncias devem cobrir exatamente as 8 do art. 59 "
            f"(faltando={faltando or None}, desconhecidas={desconhecidas or None})"
        )

    quantidade_desfavoravel = sum(
        1 for valoracao in circunstancias.values() if valoracao is Valoracao.DESFAVORAVEL
    )
    incremento = estrategia.incremento_por_circunstancia(faixa)
    pena_base_bruta = faixa.minimo.mais_dias(incremento.dias * quantidade_desfavoravel)
    pena_base = faixa.limitar(pena_base_bruta)

    if quantidade_desfavoravel:
        motivo = (
            f"{quantidade_desfavoravel} circunstância(s) desfavorável(is) do art. 59, "
            f"{estrategia.nome} cada"
        )
    else:
        motivo = "nenhuma circunstância desfavorável: pena-base fixada no mínimo da faixa"

    passo = Passo(
        fase="1ª fase (pena-base)",
        regra="art. 59 do CP",
        dispositivo=faixa.origem,
        valor_antes=faixa.minimo,
        valor_depois=pena_base,
        motivo=motivo,
    )
    return ResultadoFase1(pena_base=pena_base, passo=passo)
