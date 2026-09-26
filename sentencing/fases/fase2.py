from dataclasses import dataclass

from ..circunstancias.legais import LegalCircumstance, CircumstanceDirection
from ..valores.faixa import PenaltyRange
from ..relatorio.passo import Step
from ..valores.pena import Penalty
from ..quantum.estrategias import QuantumStrategy


@dataclass(frozen=True, slots=True)
class Phase2Result:
    pena_intermediaria: Penalty
    passo: Step
    alertas: tuple[str, ...] = ()


def calcular_pena_intermediaria(
    faixa: PenaltyRange,
    pena_base: Penalty,
    circunstancias: list[LegalCircumstance],
    estrategia: QuantumStrategy,
) -> Phase2Result:
    """2ª fase do art. 68 do CP: aplica agravantes e atenuantes sobre a pena-base.

    Continua sem sair da faixa — em particular, a atenuante nunca reduz abaixo do
    mínimo (Súmula 231 do STJ), garantido por `PenaltyRange.limitar`.

    Havendo concurso entre agravantes e atenuantes com preponderância só de um lado
    (art. 67 do CP: motivos determinantes do crime, personalidade do agente e
    reincidência), as circunstâncias do outro lado são desconsideradas. Nos demais
    casos (sem concurso, ou preponderância dos dois lados, ou de nenhum), o efeito é
    a compensação líquida entre o número de agravantes e de atenuantes.
    """
    agravantes = [c for c in circunstancias if c.direcao is CircumstanceDirection.AGRAVANTE]
    atenuantes = [c for c in circunstancias if c.direcao is CircumstanceDirection.ATENUANTE]

    regra_preponderancia = None
    if agravantes and atenuantes:
        agravantes_preponderantes = any(c.preponderante for c in agravantes)
        atenuantes_preponderantes = any(c.preponderante for c in atenuantes)
        if agravantes_preponderantes and not atenuantes_preponderantes:
            atenuantes = []
            regra_preponderancia = "preponderam as agravantes (art. 67 do CP)"
        elif atenuantes_preponderantes and not agravantes_preponderantes:
            agravantes = []
            regra_preponderancia = "preponderam as atenuantes (art. 67 do CP)"

    incremento = estrategia.incremento_por_circunstancia(faixa).dias
    dias_bruto = pena_base.dias + incremento * len(agravantes) - incremento * len(atenuantes)
    pena_intermediaria = faixa.limitar(Penalty(max(dias_bruto, 0)))

    partes_motivo = [
        f"{len(agravantes)} agravante(s){_codigos(agravantes)}, "
        f"{len(atenuantes)} atenuante(s){_codigos(atenuantes)}"
    ]
    if regra_preponderancia:
        partes_motivo.append(regra_preponderancia)
    if pena_intermediaria.dias != dias_bruto:
        partes_motivo.append("resultado contido na faixa (Súmula 231 do STJ, se for o caso)")

    passo = Step(
        fase="2ª fase (pena intermediária)",
        regra="arts. 61 a 67 do CP",
        dispositivo=faixa.origem,
        valor_antes=pena_base,
        valor_depois=pena_intermediaria,
        motivo="; ".join(partes_motivo),
    )
    alertas = []
    if dias_bruto < faixa.minimo.dias:
        alertas.append(
            "atenuante(s) não aplicada(s) integralmente: a pena intermediária não pode "
            f"ficar abaixo do mínimo da faixa ({faixa.minimo}) — Súmula 231 do STJ"
        )
    elif dias_bruto > faixa.maximo.dias:
        alertas.append(
            "agravante(s) não aplicada(s) integralmente: a pena intermediária não pode "
            f"passar do máximo da faixa ({faixa.maximo})"
        )
    if regra_preponderancia:
        alertas.append(f"concurso de agravantes e atenuantes: {regra_preponderancia}")
    return Phase2Result(
        pena_intermediaria=pena_intermediaria, passo=passo, alertas=tuple(alertas)
    )


def _codigos(circunstancias: list[LegalCircumstance]) -> str:
    """Ex.: " (reincidencia, confissao_espontanea)", ou vazio se não houver nenhuma."""
    if not circunstancias:
        return ""
    return " (" + ", ".join(c.codigo for c in circunstancias) + ")"
