from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..valores.pena import Pena
from .fundamentacao import gerar_fundamentacao
from .passo import Passo

if TYPE_CHECKING:  # import só para tipagem: fases/ já depende de relatorio/
    from ..fases.completa import ResultadoDosimetria


def resultado_para_dict(resultado: ResultadoDosimetria) -> dict[str, Any]:
    """Resultado do motor em tipos simples de JSON, com a fundamentação em texto."""
    alternativa = resultado.alternativa_art68
    faixa = resultado.faixa_aplicada
    return {
        "faixa_aplicada": {
            "origem": faixa.origem,
            "minimo": pena_para_dict(faixa.minimo),
            "maximo": pena_para_dict(faixa.maximo),
        },
        "pena_base": pena_para_dict(resultado.pena_base),
        "pena_intermediaria": pena_para_dict(resultado.pena_intermediaria),
        "pena_definitiva": pena_para_dict(resultado.pena_definitiva),
        "alternativa_art68": None
        if alternativa is None
        else {
            "descricao": alternativa.descricao,
            "pena_definitiva": pena_para_dict(alternativa.pena_definitiva),
            "passos": [passo_para_dict(p) for p in alternativa.passos],
        },
        "passos": [passo_para_dict(p) for p in resultado.passos],
        "criterio_quantum": resultado.criterio_quantum,
        "composicao": resultado.composicao.value,
        "alertas": list(resultado.alertas),
        "fundamentacao": gerar_fundamentacao(resultado),
    }


def pena_para_dict(pena: Pena) -> dict[str, Any]:
    anos, meses, dias = pena.como_anos_meses_dias()
    return {"total_dias": pena.dias, "anos": anos, "meses": meses, "dias": dias, "texto": str(pena)}


def passo_para_dict(passo: Passo) -> dict[str, Any]:
    return {
        "fase": passo.fase,
        "regra": passo.regra,
        "dispositivo": passo.dispositivo,
        "valor_antes": pena_para_dict(passo.valor_antes),
        "valor_depois": pena_para_dict(passo.valor_depois),
        "motivo": passo.motivo,
    }
