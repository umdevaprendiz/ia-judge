"""Avaliação da busca com os casos de teste de dados/fontes/perguntas.json.

    python -m fontes.avaliacao

Mede quantas perguntas trazem o artigo esperado na 1ª posição, entre os 3 e entre os 5
primeiros (acerto@1, @3, @5) e a posição média inversa (MRR). É o número que diz se uma
mudança na busca melhorou ou piorou o agente.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .busca import LegalSearchIndex, base_de_fontes

ARQUIVO_PERGUNTAS = Path(__file__).resolve().parent.parent / "dados" / "fontes" / "perguntas.json"


@dataclass(frozen=True, slots=True)
class QuestionResult:
    pergunta: str
    esperado: tuple[str, ...]
    ate: int
    posicao: int | None  # 1 = primeiro resultado; None = fora dos 10 primeiros
    encontrados: tuple[str, ...]

    @property
    def passou(self) -> bool:
        return self.posicao is not None and self.posicao <= self.ate


def avaliar(base: LegalSearchIndex | None = None, arquivo: Path = ARQUIVO_PERGUNTAS) -> tuple[list[QuestionResult], dict]:
    base = base or base_de_fontes()
    perguntas = json.loads(arquivo.read_text(encoding="utf-8"))["perguntas"]
    resultados = []
    for item in perguntas:
        encontrados = tuple(r.dispositivo.rotulo for r in base.buscar(item["pergunta"], limite=10))
        posicao = next((i + 1 for i, rotulo in enumerate(encontrados) if rotulo in item["esperado"]), None)
        resultados.append(QuestionResult(item["pergunta"], tuple(item["esperado"]), item["ate"], posicao, encontrados))
    total = len(resultados)
    metricas = {
        "perguntas": total,
        "acerto@1": sum(r.posicao == 1 for r in resultados) / total,
        "acerto@3": sum(r.posicao is not None and r.posicao <= 3 for r in resultados) / total,
        "acerto@5": sum(r.posicao is not None and r.posicao <= 5 for r in resultados) / total,
        "mrr": sum(1 / r.posicao for r in resultados if r.posicao) / total,
        "dentro_do_limite": sum(r.passou for r in resultados) / total,
    }
    return resultados, metricas


if __name__ == "__main__":
    resultados, metricas = avaliar()
    for r in resultados:
        marca = "ok " if r.passou else "ERRO"
        print(f"{marca} posição {r.posicao or '-':>2} (até {r.ate})  {r.pergunta[:70]:70}  -> {', '.join(r.encontrados[:3])}")
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in metricas.items()})
