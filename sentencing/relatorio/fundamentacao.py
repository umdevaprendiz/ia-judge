from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING

from .passo import Step

if TYPE_CHECKING:  # import só para tipagem: fases/ já depende de relatorio/
    from ..fases.completa import SentencingResult

_COMPOSICAO = {
    "cascata": "causas compostas em cascata (cada fração sobre a pena já modificada)",
    "sobre_pena_intermediaria": "causas compostas sobre a pena intermediária (efeitos somados)",
}


def gerar_fundamentacao(resultado: SentencingResult) -> str:
    """Texto da dosimetria para leitura humana, montado só a partir do resultado do motor.

    Não acrescenta nenhuma conclusão que não esteja nos passos e alertas: o texto é
    uma apresentação do cálculo, não uma nova análise.
    """
    faixa = resultado.faixa_aplicada
    linhas = [
        "DOSIMETRIA DA PENA",
        "",
        f"Faixa aplicada ({faixa.origem}): de {faixa.minimo} a {faixa.maximo}.",
        f"Critério de quantum nas fases 1 e 2: {resultado.criterio_quantum}.",
        f"Composição da 3ª fase: {_COMPOSICAO[resultado.composicao.value]}.",
    ]

    fases = [list(passos) for _, passos in groupby(resultado.passos, key=lambda p: p.fase)]
    penas = [
        ("Pena-base", resultado.pena_base),
        ("Pena intermediária", resultado.pena_intermediaria),
        ("Pena definitiva", resultado.pena_definitiva),
    ]
    for passos, (rotulo, pena) in zip(fases, penas):
        linhas += ["", passos[0].fase.upper(), *_linhas_dos_passos(passos), f"{rotulo}: {pena}."]

    alternativa = resultado.alternativa_art68
    if alternativa is not None:
        linhas += [
            "",
            "OPÇÃO DO ART. 68, PARÁGRAFO ÚNICO, DO CP",
            f"({alternativa.descricao})",
            *_linhas_dos_passos(alternativa.passos),
            f"Pena definitiva nesta opção: {alternativa.pena_definitiva}.",
        ]

    if resultado.alertas:
        linhas += ["", "ALERTAS", *(f"- {alerta}" for alerta in resultado.alertas)]

    return "\n".join(linhas)


def _linhas_dos_passos(passos: tuple[Step, ...] | list[Step]) -> list[str]:
    return [
        f"- {passo.motivo} [{passo.regra}; {passo.dispositivo}]: "
        f"{passo.valor_antes} -> {passo.valor_depois}"
        for passo in passos
    ]
