"""Avaliação do agente com os casos de dados/agente/casos.json.

    python -m agente.avaliacao

Para cada caso: o crime veio em 1º lugar? Tudo o que devia ser sugerido foi? Algo proibido
(ex.: agravante que já qualificou o crime) foi sugerido?
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .analise import CrimeAgent, agente

ARQUIVO_CASOS = Path(__file__).resolve().parent.parent / "dados" / "agente" / "casos.json"


@dataclass(frozen=True, slots=True)
class AgentCaseResult:
    id: str
    crime_esperado: str
    crimes: tuple[str, ...]
    faltaram: tuple[str, ...]
    indevidos: tuple[str, ...]

    @property
    def acertou_o_crime(self) -> bool:
        return bool(self.crimes) and self.crimes[0] == self.crime_esperado

    @property
    def passou(self) -> bool:
        return self.acertou_o_crime and not self.faltaram and not self.indevidos


def sugeridos(estrutura: dict) -> set[str]:
    itens = estrutura["formas"] + estrutura["causas"]
    circunstancias = estrutura["agravantes"] + estrutura["atenuantes"] + estrutura["circunstancias_judiciais"]
    return {i["rotulo"] for i in itens if i["sugerido"]} | {c["codigo"] for c in circunstancias if c["sugerido"]}


def avaliar(o_agente: CrimeAgent | None = None, arquivo: Path = ARQUIVO_CASOS) -> tuple[list[AgentCaseResult], dict]:
    o_agente = o_agente or agente()
    resultados = []
    for caso in json.loads(arquivo.read_text(encoding="utf-8"))["casos"]:
        crimes = tuple(c["rotulo"] for c in o_agente.identificar(caso["descricao"]))
        marcados = sugeridos(o_agente.estrutura(caso["crime"], caso["descricao"]))
        resultados.append(
            AgentCaseResult(
                caso["id"],
                caso["crime"],
                crimes,
                tuple(sorted(set(caso.get("sugerir", [])) - marcados)),
                tuple(sorted(set(caso.get("nao_sugerir", [])) & marcados)),
            )
        )
    total = len(resultados)
    metricas = {
        "casos": total,
        "crime_em_1o": sum(r.acertou_o_crime for r in resultados) / total,
        "crime_entre_os_3": sum(r.crime_esperado in r.crimes for r in resultados) / total,
        "sugestoes_completas": sum(not r.faltaram for r in resultados) / total,
        "sem_sugestao_indevida": sum(not r.indevidos for r in resultados) / total,
    }
    return resultados, metricas


if __name__ == "__main__":
    resultados, metricas = avaliar()
    for r in resultados:
        marca = "ok  " if r.passou else "ERRO"
        print(f"{marca} {r.id:40} crimes={', '.join(r.crimes)}  faltaram={list(r.faltaram)}  indevidos={list(r.indevidos)}")
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in metricas.items()})
