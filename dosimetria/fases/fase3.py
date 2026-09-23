import math
from dataclasses import dataclass
from enum import Enum
import fractions

from ..circunstancias.causas import ModifyingCause, CauseDirection, CauseOrigin, racional
from ..relatorio.passo import Step
from ..valores.pena import Penalty

FASE = "3ª fase (pena definitiva)"


class Composition(Enum):
    """Como várias causas se somam na 3ª fase.

    CASCATA: cada fração incide sobre a pena já modificada pela causa anterior.
    SOBRE_PENA_INTERMEDIARIA: toda fração incide sobre a pena intermediária, e os
    efeitos são somados. O motor não escolhe por conta própria: quem chama decide.
    """

    CASCATA = "cascata"
    SOBRE_PENA_INTERMEDIARIA = "sobre_pena_intermediaria"


@dataclass(frozen=True, slots=True)
class Phase3Option:
    descricao: str
    pena_definitiva: Penalty
    passos: tuple[Step, ...]


@dataclass(frozen=True, slots=True)
class Phase3Result:
    """Resultado da 3ª fase.

    `aplicando_todas` aplica todas as causas. `limitada_art68` só existe quando há
    concurso de causas da Parte Especial no mesmo sentido: é a alternativa do art. 68,
    parágrafo único (aplicar só a que mais aumente e/ou só a que mais diminua). O
    motor mostra as duas e deixa a escolha com o juiz.
    """

    aplicando_todas: Phase3Option
    limitada_art68: Phase3Option | None


def calcular_pena_definitiva(
    pena_intermediaria: Penalty,
    causas: list[ModifyingCause],
    composicao: Composition,
) -> Phase3Result:
    """3ª fase do art. 68 do CP: aplica causas de aumento e de diminuição.

    Diferente das fases anteriores, aqui a pena pode ultrapassar o máximo ou ficar
    abaixo do mínimo da faixa — por isso esta função nem recebe a `PenaltyRange`.

    O cálculo é feito com frações exatas e as frações de dia são desprezadas uma
    única vez, no fim (art. 11 do CP; seção 6.1 do plano). Consequência: na cascata,
    a ordem das causas não altera o resultado.
    """
    aplicando_todas = _aplicar(
        pena_intermediaria, causas, [], composicao, "todas as causas aplicadas"
    )

    aplicadas, descartadas, rotulos = _limitar_pelo_art68(causas)
    if not descartadas:
        return Phase3Result(aplicando_todas=aplicando_todas, limitada_art68=None)

    limitada = _aplicar(
        pena_intermediaria,
        aplicadas,
        descartadas,
        composicao,
        "art. 68, parágrafo único: " + " e ".join(rotulos),
    )
    return Phase3Result(aplicando_todas=aplicando_todas, limitada_art68=limitada)


def _limitar_pelo_art68(
    causas: list[ModifyingCause],
) -> tuple[list[ModifyingCause], list[ModifyingCause], list[str]]:
    """Separa, para cada sentido com concurso na Parte Especial, a causa que prevalece."""
    descartadas: list[ModifyingCause] = []
    rotulos: list[str] = []
    for direcao, rotulo in [
        (CauseDirection.AUMENTO, "só o aumento que mais aumenta"),
        (CauseDirection.DIMINUICAO, "só a diminuição que mais diminui"),
    ]:
        especiais = [
            c for c in causas if c.direcao is direcao and c.origem is CauseOrigin.PARTE_ESPECIAL
        ]
        if len(especiais) < 2:
            continue
        prevalece = max(especiais, key=lambda c: racional(c.fracao_aplicada))
        descartadas.extend(c for c in especiais if c is not prevalece)
        rotulos.append(rotulo)
    aplicadas = [c for c in causas if not any(c is d for d in descartadas)]
    return aplicadas, descartadas, rotulos


def _aplicar(
    pena_intermediaria: Penalty,
    causas: list[ModifyingCause],
    descartadas: list[ModifyingCause],
    composicao: Composition,
    descricao: str,
) -> Phase3Option:
    passos: list[Step] = []
    exato = fractions.Fraction(pena_intermediaria.dias)

    for causa in causas:
        fracao = racional(causa.fracao_aplicada)
        sinal = 1 if causa.direcao is CauseDirection.AUMENTO else -1
        if composicao is Composition.CASCATA:
            depois = exato * (1 + sinal * fracao)
        else:
            depois = exato + sinal * fracao * pena_intermediaria.dias
        if depois < 0:
            raise ValueError(
                "as diminuições somadas sobre a pena intermediária passam de 100% da pena; "
                "use a composição em cascata ou revise as frações"
            )
        passos.append(
            Step(
                fase=FASE,
                regra="art. 68 do CP",
                dispositivo=causa.dispositivo,
                valor_antes=_truncar(exato),
                valor_depois=_truncar(depois),
                motivo=_motivo(causa, composicao),
            )
        )
        exato = depois

    pena_definitiva = _truncar(exato)

    for causa in descartadas:
        passos.append(
            Step(
                fase=FASE,
                regra="art. 68, parágrafo único, do CP",
                dispositivo=causa.dispositivo,
                valor_antes=pena_definitiva,
                valor_depois=pena_definitiva,
                motivo=(
                    f"{causa.codigo} ({causa.fracao_aplicada}) não aplicada: concurso de causas "
                    "da Parte Especial, prevalece a que mais aumenta/diminui"
                ),
            )
        )

    if not causas and not descartadas:
        passos.append(
            Step(
                fase=FASE,
                regra="art. 68 do CP",
                dispositivo="-",
                valor_antes=pena_intermediaria,
                valor_depois=pena_intermediaria,
                motivo="nenhuma causa de aumento ou de diminuição: pena definitiva = pena intermediária",
            )
        )

    return Phase3Option(descricao=descricao, pena_definitiva=pena_definitiva, passos=tuple(passos))


def _motivo(causa: ModifyingCause, composicao: Composition) -> str:
    verbo = "aumento" if causa.direcao is CauseDirection.AUMENTO else "diminuição"
    base = "em cascata" if composicao is Composition.CASCATA else "sobre a pena intermediária"
    motivo = f"{causa.codigo}: {verbo} de {causa.fracao_aplicada} ({base})"
    if causa.acima_da_minima:
        motivo += f"; fração acima da mínima ({causa.fracao_min}): {causa.justificativa}"
    return motivo


def _truncar(valor: fractions.Fraction) -> Penalty:
    """Despreza as frações de dia (art. 11 do CP)."""
    return Penalty(math.floor(valor))
