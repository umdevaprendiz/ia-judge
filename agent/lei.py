"""Leitura da estrutura de um crime a partir do texto da lei (parser de penas e de frações).

Do artigo inteiro, como está na base de legislação, sai o que o motor precisa:
- a pena do caput ("Pena – reclusão, de um a quatro anos, e multa" -> 365 a 1.460 dias);
- as formas com pena própria (qualificadas, privilegiadas, culposas: "§ 4º A pena é de
  reclusão de dois a oito anos... se o crime é cometido: I – ...");
- as causas de aumento e de diminuição, com a fração ("aumenta-se de 1/3 (um terço) até
  metade", "diminuí-la de um a dois terços").

Tudo é lido do texto, e não transcrito à mão: vale para qualquer crime da base, e o que o
agente mostra ao estudante é exatamente o que a lei diz.
"""

import re
from dataclasses import dataclass
from fractions import Fraction

from sources.extracao import LegalProvision

_NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
    "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40,
}
_NUM = r"(?:\d{1,3}(?:\s*\([^)]{1,30}\))?|" + "|".join(sorted(_NUMEROS, key=len, reverse=True)) + r")"
_UNIDADE = r"(?:anos?|m[êe]s(?:es)?|dias?)"
_QUANTIDADE = rf"{_NUM}(?:\s+{_UNIDADE}(?:\s+e\s+{_NUM}\s+{_UNIDADE})?)?"
_PENA = re.compile(
    rf"(?P<especie>reclus[ãa]o|deten[çc][ãa]o|pris[ãa]o simples)\s*,?\s*(?:de\s+)?"
    rf"(?P<minimo>{_QUANTIDADE})\s+a\s+(?P<maximo>{_QUANTIDADE})(?P<resto>[^.;:]{{0,40}})",
    re.IGNORECASE,
)
_DIAS_POR_UNIDADE = {"ano": 365, "mes": 30, "dia": 1}

_FRACOES_POR_EXTENSO = {
    "terco": 3, "tercos": 3, "sexto": 6, "sextos": 6, "quinto": 5, "quintos": 5, "quarto": 4, "quartos": 4,
    "oitavo": 8, "oitavos": 8,
}
_FRACAO = (
    r"(?:\d{1,2}\s*/\s*\d{1,2}(?:\s*\([^)]{1,30}\))?|(?:um|uma|dois|duas|tres|três)\s+(?:terços?|tercos?|sextos?|quintos?|quartos?|oitavos?)"
    r"|(?:a\s+)?metade|(?:o\s+)?dobro|(?:o\s+)?triplo|quarta parte|um|dois)"
)
_GATILHO_DA_FRACAO = re.compile(
    r"(aument\w*(?:-se)?|agravad\w*|diminu\w*(?:-la)?|reduz\w*(?:-la)?|reduzid\w*)[^.;:]{0,40}?"
    rf"\b(?:de|em)\s+(?P<de>{_FRACAO})(?:\s+(?:a|até|ao)\s+(?P<ate>{_FRACAO}))?",
    re.IGNORECASE,
)
_EM_DOBRO = re.compile(r"(?:aplica-se|aplicam-se|será aplicada|é aplicada)?[^.;]{0,40}\bem\s+(dobro|triplo)\b", re.IGNORECASE)

_INCISO = re.compile(r"^(?P<numeral>[IVXLC]+(?:-[A-Z])?)\s*[–-]\s*(?P<texto>.*)$")
_PARAGRAFO = re.compile(r"^(?:§\s*(?P<numero>\d+)º?(?:-(?P<sufixo>[A-Z]))?\.?|Parágrafo único\.?)\s*(?P<texto>.*)$")
_EPIGRAFE_INTERNA = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.;:]{2,80}$")


@dataclass(frozen=True, slots=True)
class CominatedPenalty:
    """Pena em abstrato: espécie, mínimo e máximo em dias (1 ano = 365, 1 mês = 30)."""

    especie: str  # "reclusão", "detenção", "prisão simples"
    minimo_dias: int
    maximo_dias: int
    multa: bool


@dataclass(frozen=True, slots=True)
class CrimeOption:
    """Uma forma com pena própria, ou uma causa de aumento/diminuição, lida do artigo."""

    rotulo: str  # "CP.art155.§4.IV"
    tipo: str  # "forma" | "aumento" | "diminuicao"
    titulo: str  # "Furto qualificado (§ 4º, IV)"
    texto: str  # o texto do inciso ou do parágrafo
    grupo: str  # o parágrafo de onde veio ("CP.art155.§4"): incisos do mesmo grupo dividem pena/fração
    pena: CominatedPenalty | None = None
    fracao_min: Fraction | None = None
    fracao_max: Fraction | None = None


@dataclass(frozen=True, slots=True)
class CrimeType:
    """Um tipo penal (artigo com pena no caput), com as formas e causas que o próprio artigo prevê."""

    rotulo: str
    nome: str
    lei: str
    nome_lei: str
    pena: CominatedPenalty
    caput: str
    opcoes: tuple[CrimeOption, ...]


def ler_pena(texto: str) -> CominatedPenalty | None:
    """ "Pena – reclusão, de 2 (dois) a 8 (oito) anos, e multa" -> reclusão, 730 a 2.920 dias, multa."""
    correspondencia = _PENA.search(texto)
    if correspondencia is None:
        return None
    unidade_final = _unidade(correspondencia["maximo"])
    minimo = _dias(correspondencia["minimo"], unidade_final)
    maximo = _dias(correspondencia["maximo"], unidade_final)
    if minimo is None or maximo is None or minimo > maximo:
        return None
    especie = correspondencia["especie"].lower().replace("reclusao", "reclusão").replace("detencao", "detenção")
    especie = especie.replace("prisao", "prisão")
    return CominatedPenalty(especie, minimo, maximo, "multa" in correspondencia["resto"].lower())


def ler_fracao(texto: str) -> tuple[str, Fraction, Fraction] | None:
    """ "aumenta-se de 1/3 (um terço) até metade" -> ("aumento", 1/3, 1/2);
    "diminuí-la de um a dois terços" -> ("diminuicao", 1/3, 2/3); "aplica-se em dobro" -> ("aumento", 1, 1)."""
    correspondencia = _GATILHO_DA_FRACAO.search(texto)
    if correspondencia is not None:
        direcao = "aumento" if re.match(r"aument|agrav", correspondencia.group(1), re.IGNORECASE) else "diminuicao"
        ate = _fracao(correspondencia["ate"]) if correspondencia["ate"] else None
        de = _fracao(correspondencia["de"], denominador_de=correspondencia["ate"])
        if de is not None and (ate is None or ate >= de):
            return direcao, de, ate if ate is not None else de
    dobro = _EM_DOBRO.search(texto)
    if dobro is not None:
        fracao = Fraction(1) if dobro.group(1).lower() == "dobro" else Fraction(2)
        return "aumento", fracao, fracao
    return None


def ler_crime(artigo: LegalProvision) -> CrimeType | None:
    """O tipo penal do artigo, ou None se o caput não comina pena (não é um crime)."""
    if artigo.revogado:
        return None
    linhas = artigo.texto.split("\n")
    fim_do_caput = next((i for i, linha in enumerate(linhas) if _PARAGRAFO.match(linha) and i > 0), len(linhas))
    caput = linhas[:fim_do_caput]
    # epígrafe de parágrafo que ficou no fim do caput ("Furto qualificado" antes do § 4º)
    epigrafe_seguinte = ""
    if caput and len(caput) > 1 and _EPIGRAFE_INTERNA.match(caput[-1]) and not _INCISO.match(caput[-1]):
        epigrafe_seguinte = caput.pop()
    pena = ler_pena(" ".join(caput))
    if pena is None:
        return None
    nome = artigo.epigrafe or f"art. {artigo.artigo} ({artigo.nome_lei})"
    opcoes = _opcoes(artigo.rotulo, nome, linhas[fim_do_caput:], epigrafe_seguinte)
    texto_do_caput = " ".join(linha for linha in caput if not linha.startswith("Pena"))
    return CrimeType(artigo.rotulo, nome, artigo.lei, artigo.nome_lei, pena, texto_do_caput, tuple(opcoes))


def _opcoes(rotulo: str, nome: str, linhas: list[str], primeira_epigrafe: str) -> list[CrimeOption]:
    blocos: list[dict] = []
    epigrafe = primeira_epigrafe
    for linha in linhas:
        paragrafo = _PARAGRAFO.match(linha)
        if paragrafo:
            parte = "parágrafo_único" if linha.startswith("Parágrafo") else f"§{paragrafo['numero']}" + (
                f"-{paragrafo['sufixo']}" if paragrafo["sufixo"] else ""
            )
            blocos.append({"parte": parte, "epigrafe": epigrafe, "cabeca": linha, "linhas": []})
            epigrafe = ""
        elif blocos and _EPIGRAFE_INTERNA.match(linha) and not _INCISO.match(linha) and not linha.startswith("Pena"):
            epigrafe = linha  # vale para o próximo parágrafo
        elif blocos:
            blocos[-1]["linhas"].append(linha)

    opcoes: list[CrimeOption] = []
    vistos: set[str] = set()
    for bloco in blocos:
        grupo = f"{rotulo}.{bloco['parte']}"
        rotulo_do_paragrafo = _nome_do_paragrafo(bloco["parte"])
        titulo_base = bloco["epigrafe"] or nome
        incisos = [(m["numeral"], m["texto"]) for m in map(_INCISO.match, bloco["linhas"]) if m]
        linhas_de_pena = [l for l in bloco["linhas"] if l.startswith("Pena")]
        cabeca = bloco["cabeca"]
        pena = ler_pena(" ".join([cabeca, *linhas_de_pena]))
        fracao = ler_fracao(cabeca)
        if pena is not None and "mesma pena" in cabeca.lower():
            pena = None  # "Na mesma pena incorre quem...": outra conduta, a mesma faixa do caput

        def adicionar(parte_do_rotulo: str, texto: str, pena_propria, fracao_propria, sufixo_titulo: str) -> None:
            if f"{rotulo}.{parte_do_rotulo}" in vistos:
                return
            vistos.add(f"{rotulo}.{parte_do_rotulo}")
            titulo = f"{titulo_base} ({rotulo_do_paragrafo}{sufixo_titulo})"
            if pena_propria is not None:
                opcoes.append(CrimeOption(f"{rotulo}.{parte_do_rotulo}", "forma", titulo, texto, grupo, pena=pena_propria))
            elif fracao_propria is not None:
                direcao, minima, maxima = fracao_propria
                opcoes.append(
                    CrimeOption(f"{rotulo}.{parte_do_rotulo}", direcao, titulo, texto, grupo, fracao_min=minima, fracao_max=maxima)
                )

        if incisos:
            # incisos com pena ou fração próprias (art. 157, § 3º) valem por si; senão, herdam as do parágrafo
            for numeral, texto in incisos:
                if re.match(r"\(?\s*(Revogad|Vetad)", texto, re.IGNORECASE):
                    continue
                pena_do_inciso = ler_pena(texto) or pena
                fracao_do_inciso = ler_fracao(texto) or fracao
                if pena_do_inciso is None and fracao_do_inciso is None:
                    continue
                adicionar(f"{bloco['parte']}.{numeral}", f"{_sem_rotulo(cabeca)} {numeral} – {texto}", pena_do_inciso, fracao_do_inciso, f", {numeral}")
        else:
            adicionar(bloco["parte"], _sem_rotulo(cabeca) + (" " + " ".join(bloco["linhas"]) if bloco["linhas"] else ""), pena, fracao, "")
    return opcoes


def _nome_do_paragrafo(parte: str) -> str:
    """ "§4-A" -> "§ 4º-A"; "§11" -> "§ 11" (a lei só usa º até o 9); "parágrafo_único" -> "parágrafo único"."""
    if parte == "parágrafo_único":
        return "parágrafo único"
    numero, _, sufixo = parte[1:].partition("-")
    return f"§ {numero}{'º' if int(numero) < 10 else ''}{'-' + sufixo if sufixo else ''}"


def _sem_rotulo(cabeca: str) -> str:
    correspondencia = _PARAGRAFO.match(cabeca)
    return correspondencia["texto"] if correspondencia else cabeca


def _unidade(quantidade: str) -> str:
    unidades = re.findall(_UNIDADE, quantidade, re.IGNORECASE)
    return unidades[-1] if unidades else "ano"


def _dias(quantidade: str, unidade_padrao: str) -> int | None:
    """ "2 (dois) anos e 6 (seis) meses" -> 912; "um" com unidade padrão "anos" -> 365."""
    partes = re.findall(rf"({_NUM})(?:\s+({_UNIDADE}))?", quantidade, re.IGNORECASE)
    total = 0
    for numero, unidade in partes:
        valor = _numero(numero)
        if valor is None:
            return None
        chave = (unidade or unidade_padrao).lower().replace("ê", "e")
        chave = "ano" if chave.startswith("ano") else "mes" if chave.startswith("mes") else "dia"
        total += valor * _DIAS_POR_UNIDADE[chave]
    return total or None


def _numero(texto: str) -> int | None:
    digitos = re.match(r"\d+", texto)
    if digitos:
        return int(digitos.group(0))
    return _NUMEROS.get(texto.lower())


def _fracao(texto: str, denominador_de: str | None = None) -> Fraction | None:
    """ "1/3 (um terço)", "dois terços", "metade", "o dobro"; "um" pega o denominador de "dois terços"."""
    texto = texto.lower().strip()
    digitos = re.match(r"(\d{1,2})\s*/\s*(\d{1,2})", texto)
    if digitos:
        return Fraction(int(digitos.group(1)), int(digitos.group(2)))
    if texto.endswith("metade"):
        return Fraction(1, 2)
    if texto.endswith("dobro"):
        return Fraction(1)
    if texto.endswith("triplo"):
        return Fraction(2)
    if texto == "quarta parte":
        return Fraction(1, 4)
    palavras = texto.replace("ç", "c").split()
    numerador = _NUMEROS.get(palavras[0].replace("tres", "três")) or _NUMEROS.get(palavras[0])
    if numerador is None:
        return None
    if len(palavras) == 2 and palavras[1] in _FRACOES_POR_EXTENSO:
        return Fraction(numerador, _FRACOES_POR_EXTENSO[palavras[1]])
    if len(palavras) == 1 and denominador_de:
        outra = denominador_de.lower().replace("ç", "c").split()
        if len(outra) == 2 and outra[1] in _FRACOES_POR_EXTENSO:
            return Fraction(numerador, _FRACOES_POR_EXTENSO[outra[1]])
        digitos = re.match(r"\d{1,2}\s*/\s*(\d{1,2})", denominador_de)
        if digitos:
            return Fraction(numerador, int(digitos.group(1)))
    return None
