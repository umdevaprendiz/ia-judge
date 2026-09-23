"""Correção da dosimetria feita por um estudante, comparando fase a fase com o motor."""

from dataclasses import dataclass

from .fases import ResultadoDosimetria
from .valores import Pena


@dataclass(frozen=True, slots=True)
class ComparacaoFase:
    fase: str
    esperado: Pena
    resposta: Pena
    correta: bool
    explicacao: tuple[str, ...]
    observacao: str | None = None

    @property
    def diferenca_dias(self) -> int:
        """Positivo: o estudante chegou a uma pena maior que a do motor."""
        return self.resposta.dias - self.esperado.dias


@dataclass(frozen=True, slots=True)
class ComparacaoResposta:
    fases: tuple[ComparacaoFase, ...]

    @property
    def acertos(self) -> int:
        return sum(fase.correta for fase in self.fases)

    @property
    def total(self) -> int:
        return len(self.fases)


def comparar_resposta(
    resultado: ResultadoDosimetria,
    pena_base: Pena | None = None,
    pena_intermediaria: Pena | None = None,
    pena_definitiva: Pena | None = None,
) -> ComparacaoResposta:
    """Compara só as fases que o estudante respondeu.

    Na pena definitiva, a opção do art. 68, parágrafo único (quando existe) também é
    aceita como correta, porque a escolha entre as duas é do juiz.
    """
    motivos = {}
    for passo in resultado.passos:
        motivos.setdefault(passo.fase, []).append(passo.motivo)
    nomes_fases = list(motivos)

    fases = []
    if pena_base is not None:
        fases.append(_comparar(nomes_fases[0], resultado.pena_base, pena_base, motivos))
    if pena_intermediaria is not None:
        fases.append(_comparar(nomes_fases[1], resultado.pena_intermediaria, pena_intermediaria, motivos))
    if pena_definitiva is not None:
        alternativa = resultado.alternativa_art68
        if alternativa is not None and pena_definitiva == alternativa.pena_definitiva:
            fases.append(
                ComparacaoFase(
                    fase=nomes_fases[2],
                    esperado=alternativa.pena_definitiva,
                    resposta=pena_definitiva,
                    correta=True,
                    explicacao=tuple(p.motivo for p in alternativa.passos),
                    observacao=f"corresponde à opção do art. 68, parágrafo único ({alternativa.descricao})",
                )
            )
        else:
            observacao = None
            if alternativa is not None:
                observacao = (
                    "também seria aceita a opção do art. 68, parágrafo único: "
                    f"{alternativa.pena_definitiva}"
                )
            fases.append(
                _comparar(nomes_fases[2], resultado.pena_definitiva, pena_definitiva, motivos, observacao)
            )
    return ComparacaoResposta(fases=tuple(fases))


def _comparar(fase, esperado, resposta, motivos, observacao=None) -> ComparacaoFase:
    return ComparacaoFase(
        fase=fase,
        esperado=esperado,
        resposta=resposta,
        correta=esperado == resposta,
        explicacao=tuple(motivos[fase]),
        observacao=observacao,
    )
