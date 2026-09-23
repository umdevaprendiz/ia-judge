"""O agente: lê a descrição de um caso, identifica o crime e sugere o que se aplica a ele.

Tudo sai da base de legislação (fontes/) e de regras escritas neste projeto, sem IA de
terceiros:
1. identificar: os tipos penais mais parecidos com a descrição (BM25 sobre a epígrafe e o
   caput de cada crime, com os sinônimos leigos da busca);
2. estrutura: as formas (qualificadas, privilegiadas, culposas) e causas de aumento e de
   diminuição do crime escolhido, lidas do texto da lei, mais agravantes, atenuantes, causas
   gerais e circunstâncias judiciais;
3. sugestões: cada item que tem indício na descrição vem marcado, com a frase que o motivou.
   O estudante confirma tudo antes do cálculo (supervisão humana, seção 11 do plano).
"""

import math
import re
from collections import Counter, defaultdict
from functools import cache
from threading import Lock

from dosimetria import Penalty, pena_para_dict
from fontes.busca import SINONIMOS, LegalSearchIndex, _Bm25Field, base_de_fontes, normalizar, termos

from .catalogo import (
    AGRAVANTES,
    ATENUANTES,
    CAUSAS_GERAIS,
    CIRCUNSTANCIAS_JUDICIAIS,
    COM_VIOLENCIA,
    CONFLITOS_DE_AGRAVANTES,
    INDICIOS_DAS_OPCOES,
    INDICIOS_DE_CRIMES,
    INCOMPATIBILIDADES,
    GeneralCircumstance,
)
from .lei import CominatedPenalty, CrimeOption, CrimeType, ler_crime, ler_fracao

# contravenções e crimes de leis especiais só vencem o Código Penal com vantagem clara
_PESO_DA_LEI = {"CP": 1.0, "LCP": 0.75}
_PESO_DAS_OUTRAS_LEIS = 0.85
_FRASE = re.compile(r"[^.!?;\n]+[.!?;]?")

_AUSENCIAS = (
    ("antecedentes e reincidência do réu", re.compile(r"reincident|prim[áa]ri|antecedentes|condenad|nunca (?:foi|havia sido) (?:pres|process)", re.I)),
    ("se o réu confessou", re.compile(r"confess|negou|admitiu|sil[êe]ncio|permaneceu calado", re.I)),
    (
        "a idade do réu na data do fato (menor de 21 ou maior de 70 muda a pena)",
        re.compile(r"(?:r[ée]u|acusad[oa]|agente|autor)[^.;]{0,60}\b\d{2} anos|\b\d{2} anos[^.;]{0,40}(?:r[ée]u|acusad)", re.I),
    ),
    ("se o crime se consumou ou ficou na tentativa", re.compile(r"consum|conseguiu|levou|fugiu com|subtraiu|matou|morreu|tent|ficou com|recebeu", re.I)),
)


class CrimeAgent:
    def __init__(self, base: LegalSearchIndex):
        self.base = base
        self.crimes: dict[str, CrimeType] = {}
        for dispositivo in base.dispositivos:
            crime = ler_crime(dispositivo)
            if crime is not None:
                self.crimes[crime.rotulo] = crime
        self._ordem = list(self.crimes)
        self._indice = _Bm25Field([self._termos_do_crime(c) for c in self.crimes.values()], k1=1.2, b=0.3)
        self._termos_da_cabeca = [set(self._termos_do_crime(c)) for c in self.crimes.values()]
        self._causas_gerais = []
        for causa in CAUSAS_GERAIS:
            trecho = base.trecho_do_rotulo(causa.rotulo)
            fracao = ler_fracao(trecho[1]) if trecho else None
            if fracao is not None:
                self._causas_gerais.append((causa, fracao))

    def _termos_do_crime(self, crime: CrimeType) -> list[str]:
        dispositivo = self.base.obter(crime.rotulo)
        capitulo = dispositivo.estrutura[-1] if dispositivo.estrutura else ""
        return termos(crime.nome) * 3 + termos(crime.caput) + termos(capitulo)

    # ---------- 1. qual é o crime ----------

    def identificar(self, texto: str, limite: int = 3) -> list[dict]:
        pesos: Counter[str] = Counter()
        for termo, vezes in Counter(termos(texto)).items():
            pesos[termo] = 1.0 + math.log(vezes)
        normalizado = normalizar(texto)
        for expressao, expansao in SINONIMOS.items():
            if re.search(rf"\b{re.escape(expressao)}\b", normalizado):
                for termo in termos(expansao):
                    pesos[termo] = max(pesos[termo], 0.8)
        pontos: dict[int, float] = defaultdict(float)
        self._indice.pontuar(pesos, pontos)
        for posicao in list(pontos):
            lei = self.crimes[self._ordem[posicao]].lei
            pontos[posicao] *= _PESO_DA_LEI.get(lei, _PESO_DAS_OUTRAS_LEIS)
        # indícios fortes do léxico: pesam mais que a semelhança de palavras
        indicios: dict[str, str] = {}
        for rotulo, peso, padrao in INDICIOS_DE_CRIMES:
            evidencia = _frase_com(padrao, [f.strip() for f in _FRASE.findall(texto) if f.strip()])
            if evidencia is not None and rotulo in self.crimes:
                pontos[self._ordem.index(rotulo)] += peso
                indicios[rotulo] = evidencia
        # artigo citado na própria descrição ("art. 155 do CP") vai para o topo
        citados = [r for r in self.base.referencias(texto) if r in self.crimes]
        maximo = max(pontos.values(), default=0.0)
        for ordem, rotulo in enumerate(citados):
            pontos[self._ordem.index(rotulo)] = maximo + 100 - ordem
        melhores = sorted(pontos.items(), key=lambda item: -item[1])[:limite]
        resultado = []
        for posicao, valor in melhores:
            crime = self.crimes[self._ordem[posicao]]
            resultado.append(
                {
                    "rotulo": crime.rotulo,
                    "nome": crime.nome,
                    "nome_lei": crime.nome_lei,
                    "pontuacao": round(valor, 3),
                    "citado_na_descricao": crime.rotulo in citados,
                    "evidencias": list(
                        dict.fromkeys(
                            ([indicios[crime.rotulo]] if crime.rotulo in indicios else [])
                            + self._frases_parecidas(texto, self._termos_da_cabeca[posicao])
                        )
                    )[:2],
                }
            )
        return resultado

    def _frases_parecidas(self, texto: str, termos_do_crime: set[str], limite: int = 2) -> list[str]:
        frases = [f.strip() for f in _FRASE.findall(texto) if f.strip()]
        pontuadas = []
        for frase in frases:
            comuns = set(termos(frase)) & termos_do_crime
            valor = sum(self._indice.idf.get(t, 0) for t in comuns)
            if valor > 0:
                pontuadas.append((valor, frase))
        return [_encurtar(frase) for _, frase in sorted(pontuadas, key=lambda item: -item[0])[:limite]]

    # ---------- 2 e 3. estrutura do crime, com sugestões ----------

    def estrutura(self, rotulo: str, texto: str = "") -> dict:
        crime = self.crimes.get(rotulo)
        if crime is None:
            raise ValueError(f"crime não encontrado na base: {rotulo}")
        frases = [f.strip() for f in _FRASE.findall(texto) if f.strip()]
        com_violencia = bool(COM_VIOLENCIA.search(crime.caput))

        formas = [self._opcao(op, frases) for op in crime.opcoes if op.tipo == "forma"]
        causas = [self._opcao(op, frases) for op in crime.opcoes if op.tipo != "forma"]
        for causa, (direcao, minima, maxima) in self._causas_gerais:
            if causa.so_sem_violencia and com_violencia:
                continue
            sugestao = _sugerir(causa, frases)
            causas.append(
                {
                    "rotulo": causa.rotulo,
                    "titulo": causa.titulo,
                    "tipo": direcao,
                    "direcao": direcao,
                    "origem": "parte_geral",
                    "grupo": causa.rotulo,
                    "fracao_min": _fracao(minima),
                    "fracao_max": _fracao(maxima),
                    **sugestao,
                }
            )

        # causa incompatível com uma forma sugerida (repouso noturno x furto qualificado) sai da sugestão
        formas_sugeridas = [f["rotulo"] for f in formas if f["sugerido"]]
        for item in causas:
            for causa, prefixo, motivo in INCOMPATIBILIDADES:
                if item["rotulo"] == causa and any(r.startswith(prefixo) for r in formas_sugeridas) and item["sugerido"]:
                    item.update(sugerido=False, observacao=motivo)

        # bis in idem: o que já qualificou ou aumentou a pena não vira agravante sugerida
        textos_sugeridos = " ".join(item["texto"] for item in formas + causas if item["sugerido"] and "texto" in item)
        agravantes = []
        for agravante in AGRAVANTES:
            item = _circunstancia(agravante, frases)
            conflito = CONFLITOS_DE_AGRAVANTES.get(agravante.codigo)
            if item["sugerido"] and conflito is not None and conflito.search(textos_sugeridos):
                item.update(sugerido=False, observacao="já considerada na qualificadora ou causa de aumento sugerida (bis in idem)")
            agravantes.append(item)

        return {
            "crime": {
                "rotulo": crime.rotulo,
                "nome": crime.nome,
                "nome_lei": crime.nome_lei,
                "caput": crime.caput,
                "pena": _pena(crime.pena),
            },
            "formas": formas,
            "causas": causas,
            "agravantes": agravantes,
            "atenuantes": [_circunstancia(atenuante, frases) for atenuante in ATENUANTES],
            "circunstancias_judiciais": [
                {"codigo": c.codigo, "titulo": c.titulo, **_sugerir(c, frases)} for c in CIRCUNSTANCIAS_JUDICIAIS
            ],
        }

    def _opcao(self, opcao: CrimeOption, frases: list[str]) -> dict:
        item = {
            "rotulo": opcao.rotulo,
            "titulo": opcao.titulo,
            "texto": opcao.texto,
            "tipo": opcao.tipo,
            "grupo": opcao.grupo,
            "sugerido": False,
            "evidencia": None,
        }
        if opcao.pena is not None:
            item["pena"] = _pena(opcao.pena)
        else:
            item.update(
                direcao=opcao.tipo, origem="parte_especial", fracao_min=_fracao(opcao.fracao_min), fracao_max=_fracao(opcao.fracao_max)
            )
        # os assuntos da lei que aparecem no texto da opção; os "exigidos" (ex.: arma de uso restrito)
        # precisam ter indício na descrição, senão a opção não é sugerida mesmo que outro assunto tenha
        assuntos = [(indicio, exigido) for assunto, indicio, exigido in INDICIOS_DAS_OPCOES if assunto.search(opcao.texto)]
        evidencias = [(_frase_com(indicio, frases), exigido) for indicio, exigido in assuntos]
        if all(evidencia for evidencia, exigido in evidencias if exigido):
            evidencia = next((e for e, _ in evidencias if e), None)
            if evidencia:
                item.update(sugerido=True, evidencia=evidencia)
        return item

    def informacoes_ausentes(self, texto: str) -> list[str]:
        return [descricao for descricao, padrao in _AUSENCIAS if not padrao.search(texto)]


def _circunstancia(circunstancia: GeneralCircumstance, frases: list[str]) -> dict:
    return {
        "codigo": circunstancia.codigo,
        "titulo": circunstancia.titulo,
        "rotulo": circunstancia.rotulo,
        "preponderante": circunstancia.preponderante,
        **_sugerir(circunstancia, frases),
    }


def _sugerir(circunstancia: GeneralCircumstance, frases: list[str]) -> dict:
    evidencia = _frase_com(circunstancia.indicios, frases) if circunstancia.indicios is not None else None
    return {"sugerido": evidencia is not None, "evidencia": evidencia}


def _frase_com(padrao: re.Pattern, frases: list[str]) -> str | None:
    for frase in frases:
        if padrao.search(frase):
            return _encurtar(frase)
    return None


def _fracao(fracao) -> str:
    """Sempre "numerador/denominador" ("1/1" para o dobro), o formato da entrada do motor."""
    return f"{fracao.numerator}/{fracao.denominator}"


def _pena(pena: CominatedPenalty) -> dict:
    minimo, maximo = Penalty(pena.minimo_dias), Penalty(pena.maximo_dias)
    return {
        "especie": pena.especie,
        "minimo": pena_para_dict(minimo),
        "maximo": pena_para_dict(maximo),
        "multa": pena.multa,
        "texto": f"{pena.especie}, de {minimo} a {maximo}{', e multa' if pena.multa else ''}",
    }


def _encurtar(texto: str, limite: int = 300) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rsplit(" ", 1)[0] + "…"


_trava = Lock()


@cache
def _agente() -> CrimeAgent:
    return CrimeAgent(base_de_fontes())


def agente() -> CrimeAgent:
    """O agente, montado uma vez por processo a partir da base de legislação."""
    with _trava:
        return _agente()
