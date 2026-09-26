"""Gera o vocabulário do agente a partir de dicionários abertos do português brasileiro.

    python scripts/construir_vocabulario.py            gera dados/vocabulario/lexico.json
    python scripts/construir_vocabulario.py sinonimos  lista candidatos a sinônimos para revisão

Fontes (baixadas para materiais/dicionarios/, fora do git):
- VERO, dicionário do LibreOffice para pt-BR (pt_BR.dic e pt_BR.aff), LGPLv3/MPL:
  palavras base e regras de sufixo, com as quais cada flexão volta à forma base ("mata",
  "matou", "matando" -> "matar").
- OpenWordnet-PT (own-pt-*.xml), CC BY 4.0: conjuntos de sinônimos. Não entram direto no
  agente: o modo "sinonimos" lista os candidatos, e os aprovados vão, revisados, para
  dados/vocabulario/sinonimos.json.

O léxico gerado guarda as regras de sufixo e as palavras base de todos os verbos, das
palavras da base de legislação e dos sinônimos revisados; a forma base de cada palavra é
calculada na hora (fontes/vocabulario.py).
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "materiais" / "dicionarios"
SAIDA = RAIZ / "dados" / "vocabulario"


def ler_regras(arquivo: Path) -> dict[str, list[tuple[str, str, re.Pattern]]]:
    """Regras de sufixo (SFX) do .aff: bandeira -> [(tirar, pôr, condição)]."""
    regras: dict[str, list] = defaultdict(list)
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        partes = linha.split()
        if len(partes) < 5 or partes[0] != "SFX":
            continue
        _, bandeira, tirar, por, condicao = partes[:5]
        tirar = "" if tirar == "0" else tirar
        por = "" if por == "0" else por.split("/")[0]
        regras[bandeira].append((tirar, por, re.compile(f"(?:{condicao})$")))
    return regras


def flexoes() -> dict[str, set[str]]:
    """Forma flexionada -> formas base (entradas do .dic que a geram)."""
    regras = ler_regras(PASTA / "pt_BR.aff")
    formas: dict[str, set[str]] = defaultdict(set)
    linhas = (PASTA / "pt_BR.dic").read_text(encoding="utf-8").splitlines()[1:]
    for linha in linhas:
        palavra, _, bandeiras = linha.partition("/")
        palavra = palavra.strip()
        if not palavra or " " in palavra:
            continue
        base = palavra.lower()
        formas[base].add(base)
        for bandeira in bandeiras.strip():
            for tirar, por, condicao in regras.get(bandeira, ()):
                if base.endswith(tirar) and condicao.search(base):
                    formas[base[: len(base) - len(tirar)] + por].add(base)
    return formas


def palavras_da_base() -> set[str]:
    dados = json.loads((RAIZ / "dados" / "fontes" / "dispositivos.json").read_text(encoding="utf-8"))
    palavras: set[str] = set()
    for dispositivo in dados["dispositivos"]:
        palavras.update(re.findall(r"[a-záéíóúâêôãõçü]+", (dispositivo["texto"] + " " + dispositivo["epigrafe"]).lower()))
    return palavras


def escolher_base(forma: str, bases: set[str]) -> str:
    """Várias bases possíveis: a própria forma; senão a de maior prefixo comum, com o verbo no empate."""
    if forma in bases:
        return forma

    def prefixo_comum(base: str) -> int:
        return next((i for i, (a, b) in enumerate(zip(forma, base)) if a != b), min(len(forma), len(base)))

    return max(sorted(bases), key=lambda b: (prefixo_comum(b), bool(re.search(r"(?:ar|er|ir|or|ôr)$", b)), -len(b)))


def gerar_lexico() -> None:
    """dados/vocabulario/lexico.json: as regras de sufixo e as palavras base que interessam.

    Interessam: todos os verbos do dicionário (o estudante descreve o caso com verbos que a lei
    não usa: "assassinou", "esfaqueou"), as palavras base do texto da lei e as dos sinônimos
    revisados. Formas com pronome ("matá-lo") ficam de fora. O agente desfaz o sufixo na hora
    (fontes/vocabulario.py), como faz um corretor ortográfico.
    """
    regras = ler_regras(PASTA / "pt_BR.aff")
    entradas: dict[str, str] = {}
    for linha in (PASTA / "pt_BR.dic").read_text(encoding="utf-8").splitlines()[1:]:
        palavra, _, bandeiras = linha.partition("/")
        palavra = palavra.strip().lower()
        if palavra and " " not in palavra:
            entradas[palavra] = entradas.get(palavra, "") + bandeiras.strip()

    mapa = flexoes()
    interessam = {p for p in entradas if re.search(r"(?:ar|er|ir|or|ôr)$", p)}
    interessam |= {escolher_base(p, mapa[p]) if p in mapa else p for p in palavras_da_base()}
    sinonimos = json.loads((SAIDA / "sinonimos.json").read_text(encoding="utf-8"))["sinonimos"]
    for canonica, lista in sinonimos.items():
        for palavra in [canonica, *lista]:
            interessam.add(escolher_base(palavra, mapa[palavra]) if palavra in mapa else palavra)

    escolhidas = {p: "".join(sorted(set(entradas[p]))) for p in sorted(interessam) if p in entradas}
    bandeiras_usadas = set("".join(escolhidas.values()))
    regras_usadas = {
        bandeira: [[tirar, por, condicao.pattern[3:-2]] for tirar, por, condicao in lista if "-" not in por]
        for bandeira, lista in sorted(regras.items())
        if bandeira in bandeiras_usadas
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "descricao": "Regras de sufixo e palavras base do português brasileiro; gerado por scripts/construir_vocabulario.py.",
        "fonte": "VERO - Verificador Ortográfico do LibreOffice, pt_BR 3.2 (github.com/LibreOffice/dictionaries)",
        "licenca": "LGPLv3 / MPL 2.0 (dicionário VERO); esta é uma seleção das entradas e regras originais",
        "regras": regras_usadas,
        "entradas": escolhidas,
    }
    saida = json.dumps(conteudo, ensure_ascii=False, separators=(",", ":"))
    (SAIDA / "lexico.json").write_text(saida + "\n", encoding="utf-8")
    total_regras = sum(len(v) for v in regras_usadas.values())
    print(f"{len(escolhidas):,} palavras base, {total_regras:,} regras ({len(saida) / 1e6:.2f} MB)")


def candidatos_a_sinonimos(termos: list[str]) -> None:
    """Para cada termo, os sinônimos do OpenWordnet-PT, por significado (para revisão manual)."""
    arquivo = next(PASTA.glob("own-pt/own-pt-*.xml"))
    lemas_do_synset: dict[str, set[str]] = defaultdict(set)
    synsets_do_lema: dict[str, set[str]] = defaultdict(set)
    for _, elemento in ET.iterparse(arquivo, events=("end",)):
        if elemento.tag == "LexicalEntry":
            lema = elemento.find("Lemma")
            forma = lema.get("writtenForm").lower()
            for sentido in elemento.findall("Sense"):
                lemas_do_synset[sentido.get("synset")].add(forma)
                synsets_do_lema[forma].add(sentido.get("synset"))
            elemento.clear()
    for termo in termos:
        print(f"\n## {termo}")
        for synset in sorted(synsets_do_lema.get(termo, ())):
            outros = sorted(lemas_do_synset[synset] - {termo})
            if outros:
                print(f"  {synset}: {', '.join(outros)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sinonimos":
        candidatos_a_sinonimos(sys.argv[2:])
    else:
        gerar_lexico()
