"""Das escolhas confirmadas pelo estudante à entrada do motor de dosimetria.

As regras de montagem, todas visíveis ao estudante como alertas:
- a faixa é a do caput ou, havendo forma com pena própria marcada (qualificadora, privilégio,
  forma culposa), a da primeira; qualificadoras a mais não trocam a faixa de novo e são
  valoradas como circunstância judicial desfavorável (circunstâncias do crime), como faz a
  jurisprudência;
- incisos do mesmo parágrafo que dividem uma fração viram uma só causa (a fração é do
  parágrafo); acima da mínima, só com justificativa (Súmula 443 do STJ);
- agravante que repete o que qualificou ou aumentou a pena é descartada (bis in idem).
"""

from fractions import Fraction

from .analise import CrimeAgent
from .catalogo import (
    AGRAVANTES,
    ATENUANTES,
    CIRCUNSTANCIAS_JUDICIAIS,
    CONFLITOS_DE_AGRAVANTES,
    ELEMENTARES_DO_TIPO,
    INCOMPATIBILIDADES,
)

_AGRAVANTES = {a.codigo: a for a in AGRAVANTES}
_ATENUANTES = {a.codigo: a for a in ATENUANTES}
_JUDICIAIS = {c.codigo for c in CIRCUNSTANCIAS_JUDICIAIS}


def montar_entrada(agente: CrimeAgent, escolhas: dict) -> tuple[dict, list[str]]:
    """escolhas: crime, formas, causas (rótulos), fracoes_escolhidas ({rótulo: {fracao, justificativa}}),
    agravantes, atenuantes, circunstancias_desfavoraveis (códigos), estrategia, composicao.
    Devolve (entrada no formato de POST /dosimetria/calcular, alertas do agente)."""
    estrutura = agente.estrutura(escolhas["crime"])
    formas_do_crime = {item["rotulo"]: item for item in estrutura["formas"]}
    causas_do_crime = {item["rotulo"]: item for item in estrutura["causas"]}
    alertas: list[str] = []

    desconhecidos = [r for r in escolhas.get("formas", []) if r not in formas_do_crime]
    desconhecidos += [r for r in escolhas.get("causas", []) if r not in causas_do_crime]
    desconhecidos += [c for c in escolhas.get("agravantes", []) if c not in _AGRAVANTES]
    desconhecidos += [c for c in escolhas.get("atenuantes", []) if c not in _ATENUANTES]
    desconhecidos += [c for c in escolhas.get("circunstancias_desfavoraveis", []) if c not in _JUDICIAIS]
    if desconhecidos:
        raise ValueError(f"itens que não pertencem a este crime: {', '.join(sorted(set(desconhecidos)))}")

    # ---------- faixa ----------
    formas = [formas_do_crime[r] for r in formas_do_crime if r in set(escolhas.get("formas", []))]
    judiciais = list(dict.fromkeys(escolhas.get("circunstancias_desfavoraveis", [])))
    if formas:
        principal = formas[0]
        pena, origem = principal["pena"], principal["rotulo"]
        excedentes = [f for f in formas[1:] if f["grupo"] == principal["grupo"] or f["pena"] == principal["pena"]]
        outras = [f for f in formas[1:] if f not in excedentes]
        if excedentes:
            if "circunstancias" not in judiciais:
                judiciais.append("circunstancias")
            alertas.append(
                "mais de uma qualificadora marcada: a faixa vem de "
                f"{principal['titulo']}; {', '.join(f['titulo'] for f in excedentes)} "
                "entra(m) como circunstância judicial desfavorável (circunstâncias do crime)"
            )
        if outras:
            alertas.append(
                "formas com penas diferentes marcadas juntas; foi usada a primeira "
                f"({principal['titulo']}). Confira se as demais ({', '.join(f['titulo'] for f in outras)}) cabem no caso"
            )
    else:
        pena, origem = estrutura["crime"]["pena"], estrutura["crime"]["rotulo"]

    # ---------- causas (3ª fase) ----------
    escolhidas = set(escolhas.get("causas", []))
    for causa, prefixo, motivo in INCOMPATIBILIDADES:
        if causa in escolhidas and any(f["rotulo"].startswith(prefixo) for f in formas):
            escolhidas.discard(causa)
            alertas.append(f"causa não aplicada: {motivo}")
    fracoes = escolhas.get("fracoes_escolhidas", {}) or {}
    grupos: dict[tuple, list[dict]] = {}
    for rotulo, item in causas_do_crime.items():
        if rotulo in escolhidas:
            chave = (item["grupo"], item["direcao"], item["fracao_min"], item["fracao_max"])
            grupos.setdefault(chave, []).append(item)
    causas = []
    for (grupo, direcao, minima, maxima), itens in grupos.items():
        causa = {
            "codigo": " + ".join(_nome_curto(i) for i in itens)[:100],
            "dispositivo": itens[0]["rotulo"] if len(itens) == 1 else grupo,
            "direcao": direcao,
            "origem": itens[0]["origem"],
            "fracao_min": minima,
        }
        if maxima != minima:
            causa["fracao_max"] = maxima
        escolha = next((fracoes[i["rotulo"]] for i in itens if i["rotulo"] in fracoes), None)
        if escolha and escolha.get("fracao") and Fraction(escolha["fracao"]) != Fraction(minima):
            causa["fracao_escolhida"] = escolha["fracao"]
            causa["justificativa"] = escolha.get("justificativa") or None
        if len(itens) > 1 and maxima != minima:
            alertas.append(
                f"{len(itens)} hipóteses do mesmo parágrafo ({grupo}) contam como uma só causa, com a fração do "
                "parágrafo; o número de majorantes, sozinho, não justifica fração acima da mínima (Súmula 443 do STJ)"
            )
        causas.append(causa)

    # ---------- agravantes e atenuantes (2ª fase) ----------
    textos_usados = " ".join(
        [f["texto"] for f in formas] + [causas_do_crime[r].get("texto", "") for r in escolhidas]
    )
    agravantes_atenuantes = []
    for codigo in dict.fromkeys(escolhas.get("agravantes", [])):
        agravante = _AGRAVANTES[codigo]
        if codigo in ELEMENTARES_DO_TIPO.get(escolhas["crime"], ()):
            alertas.append(f"agravante \"{agravante.titulo}\" não aplicada: já é elementar do crime (bis in idem)")
            continue
        conflito = CONFLITOS_DE_AGRAVANTES.get(codigo)
        if conflito is not None and conflito.search(textos_usados):
            alertas.append(
                f"agravante \"{agravante.titulo}\" não aplicada: o fato já qualificou ou aumentou a pena (bis in idem)"
            )
            continue
        agravantes_atenuantes.append(
            {"codigo": codigo, "dispositivo": agravante.rotulo, "direcao": "agravante", "preponderante": agravante.preponderante}
        )
    for codigo in dict.fromkeys(escolhas.get("atenuantes", [])):
        atenuante = _ATENUANTES[codigo]
        agravantes_atenuantes.append(
            {"codigo": codigo, "dispositivo": atenuante.rotulo, "direcao": "atenuante", "preponderante": atenuante.preponderante}
        )

    minimo, maximo = pena["minimo"], pena["maximo"]
    entrada = {
        "faixa": {
            "origem": origem,
            "minimo": {k: minimo[k] for k in ("anos", "meses", "dias")},
            "maximo": {k: maximo[k] for k in ("anos", "meses", "dias")},
        },
        "circunstancias_desfavoraveis": judiciais,
        "agravantes_atenuantes": agravantes_atenuantes,
        "causas": causas,
        "estrategia": escolhas.get("estrategia") or {"tipo": "fracao_do_intervalo", "fracao": "1/8"},
        "composicao": escolhas.get("composicao") or "cascata",
    }
    return entrada, alertas


def _nome_curto(item: dict) -> str:
    """ "Roubo (§ 2º, II)" -> "§ 2º, II"; causas gerais ficam com o título ("Tentativa")."""
    titulo = item["titulo"]
    if titulo.endswith(")") and "(" in titulo:
        return titulo[titulo.rindex("(") + 1 : -1]
    return titulo
