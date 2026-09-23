from dataclasses import dataclass

from ..circunstancias.legais import CircunstanciaLegal, Direcao
from ..valores.faixa import Faixa
from ..relatorio.passo import Passo
from ..valores.pena import Pena
from ..quantum.estrategias import EstrategiaQuantum


@dataclass(frozen=True, slots=True)
class ResultadoFase2:
    pena_intermediaria: Pena
    passo: Passo
    alertas: tuple[str, ...] = ()


def calcular_pena_intermediaria(
    faixa: Faixa,
    pena_base: Pena,
    circunstancias: list[CircunstanciaLegal],
    estrategia: EstrategiaQuantum,
) -> ResultadoFase2:
    """2ª fase do art. 68 do CP: aplica agravantes e atenuantes sobre a pena-base.

    Continua sem sair da faixa — em particular, a atenuante nunca reduz abaixo do
    mínimo (Súmula 231 do STJ), garantido por `Faixa.limitar`.

    Havendo concurso entre agravantes e atenuantes com preponderância só de um lado
    (art. 67 do CP: motivos determinantes do crime, personalidade do agente e
    reincidência), as circunstâncias do outro lado são desconsideradas. Nos demais
    casos (sem concurso, ou preponderância dos dois lados, ou de nenhum), o efeito é
    a compensação líquida entre o número de agravantes e de atenuantes.
    """
    agravantes = [c for c in circunstancias if c.direcao is Direcao.AGRAVANTE]
    atenuantes = [c for c in circunstancias if c.direcao is Direcao.ATENUANTE]

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
    pena_intermediaria = faixa.limitar(Pena(max(dias_bruto, 0)))

    partes_motivo = [f"{len(agravantes)} agravante(s), {len(atenuantes)} atenuante(s)"]
    if regra_preponderancia:
        partes_motivo.append(regra_preponderancia)
    if pena_intermediaria.dias != dias_bruto:
        partes_motivo.append("resultado contido na faixa (Súmula 231 do STJ, se for o caso)")

    passo = Passo(
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
    return ResultadoFase2(
        pena_intermediaria=pena_intermediaria, passo=passo, alertas=tuple(alertas)
    )
