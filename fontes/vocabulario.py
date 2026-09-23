"""Forma base das palavras do português brasileiro, e sinônimos revisados.

"mata", "matou", "matando" e "matava" viram "matar"; "assassinou" vira "assassinar" e, pelo
sinônimo revisado, "matar". Assim a busca e o agente comparam a descrição do estudante com
a lei pela palavra, e não pela forma em que ela foi escrita.

O léxico (dados/vocabulario/lexico.json) traz as palavras base e as regras de sufixo do
dicionário VERO; aqui as regras são aplicadas ao contrário: para cada sufixo possível da
palavra, desfaz-se a regra e confere-se se a base existe e aceita aquela regra. Palavra que
o léxico não reconhece fica como está (a busca ainda a reduz ao radical).
"""

import json
import re
from functools import cache, lru_cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "dados" / "vocabulario"
_PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")
_VERBO = re.compile(r"(?:ar|er|ir|or|ôr)$")
# auxiliares ficam como foram escritos: carregam o tempo e a intenção ("iria matar" não é matar)
_AUXILIARES = frozenset(
    """
    ia iam iria iriam vai vão vou vamos irá irão foi foram fora era eram é são será serão seria seriam
    está estão estava estavam esteve estará estaria tem têm tinha tinham teve terá teria há havia houve
    haverá haveria pode podem podia podiam pôde poderá poderia deve devem devia deveria quer querem
    queria queriam quis quiser pretendia pretende prometeu prometia
    """.split()
)


class Lemmatizer:
    def __init__(self, regras: dict[str, list[list[str]]], entradas: dict[str, str], sinonimos: dict[str, list[str]]):
        self._entradas = entradas
        # sufixo acrescentado -> [(bandeira, o que a regra tirou da base, condição da base)]
        self._por_sufixo: dict[str, list[tuple[str, str, re.Pattern]]] = {}
        for bandeira, lista in regras.items():
            for tirar, por, condicao in lista:
                self._por_sufixo.setdefault(por, []).append((bandeira, tirar, re.compile(f"(?:{condicao})$")))
        self._maior_sufixo = max((len(s) for s in self._por_sufixo), default=0)
        self._canonica = {sinonimo: canonica for canonica, lista in sinonimos.items() for sinonimo in lista}
        self._canonicas = set(sinonimos)

    @classmethod
    def carregar(cls, pasta: Path = PASTA) -> "Lemmatizer":
        lexico = json.loads((pasta / "lexico.json").read_text(encoding="utf-8"))
        sinonimos = json.loads((pasta / "sinonimos.json").read_text(encoding="utf-8"))["sinonimos"]
        return cls(lexico["regras"], lexico["entradas"], sinonimos)

    @lru_cache(maxsize=200_000)
    def lema(self, palavra: str) -> str:
        """Forma base, já trocada pela palavra canônica se for um sinônimo revisado."""
        palavra = palavra.lower()
        base = palavra if palavra in self._entradas else self._desfazer_sufixo(palavra)
        return self._canonica.get(base, base)

    def _desfazer_sufixo(self, palavra: str) -> str:
        candidatas = set()
        for tamanho in range(min(len(palavra) - 1, self._maior_sufixo) + 1):
            sufixo = palavra[len(palavra) - tamanho :] if tamanho else ""
            for bandeira, tirar, condicao in self._por_sufixo.get(sufixo, ()):
                base = palavra[: len(palavra) - tamanho] + tirar
                if bandeira in self._entradas.get(base, "") and condicao.search(base):
                    candidatas.add(base)
        # plural que o dicionário não gera pela regra ("crianças" -> "criança")
        if not candidatas and palavra.endswith("s") and palavra[:-1] in self._entradas:
            candidatas.add(palavra[:-1])
        if not candidatas:
            return palavra

        def prefixo_comum(base: str) -> int:
            return next((i for i, (a, b) in enumerate(zip(palavra, base)) if a != b), min(len(palavra), len(base)))

        return max(sorted(candidatas), key=lambda b: (prefixo_comum(b), bool(_VERBO.search(b)), -len(b)))

    def lematizar(self, texto: str) -> str:
        """O texto com os verbos na forma base e os sinônimos revisados na palavra canônica.

        Substantivos e adjetivos ficam como foram escritos: "ex-companheira" não pode virar
        "ex-companheiro", nem "esposa" virar "esposo", porque o gênero muda o crime.
        """

        def trocar(correspondencia: re.Match) -> str:
            palavra = correspondencia.group(0)
            base = self.lema(palavra)
            minuscula = palavra.lower()
            if minuscula in _AUXILIARES:
                return palavra
            if base != minuscula and (_VERBO.search(base) or base in self._canonicas):
                return base
            return palavra

        return _PALAVRA.sub(trocar, texto)


@cache
def lematizador() -> Lemmatizer:
    return Lemmatizer.carregar()


def lema(palavra: str) -> str:
    return lematizador().lema(palavra)


def lematizar(texto: str) -> str:
    return lematizador().lematizar(texto)
