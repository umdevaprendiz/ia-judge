"""Busca nos artigos de lei: a recuperação do RAG do agente, sem modelos de terceiros.

- BM25 sobre os artigos (dados/fontes/dispositivos.json), com as palavras reduzidas ao
  radical ("furtou", "furtada" e "furto" viram "furt") e sem acentos.
- A epígrafe do artigo ("Furto qualificado") pesa mais que o resto do texto.
- Sinônimos leigos: quem escreve "assalto com faca" encontra roubo e arma branca.
- Referências diretas ("art. 155 do CP", "artigo 5º da Constituição") vão para o topo.

Tudo determinístico: a mesma pergunta sempre traz o mesmo resultado, e cada resultado
aponta o artigo de onde veio, para a resposta citar só o que existe na base.
"""

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from threading import Lock

from .extracao import LegalProvision
from .texto import sem_acentos

ARQUIVO_BASE = Path(__file__).resolve().parent.parent / "dados" / "fontes" / "dispositivos.json"

_PALAVRAS_VAZIAS = set(
    """
    a o as os um uma uns umas de do da dos das no na nos nas em ao aos à às por pelo pela pelos pelas
    para com sem sob sobre entre e ou que se quando qual quais quem cujo cuja como onde mais menos muito
    muita muitos muitas ja nao sim seu sua seus suas ele ela eles elas lhe lhes isso isto esse essa este
    esta aquele aquela ter tem tinha ser foi era sao esta estava ha houve apos ate desde depois antes
    tambem mas porem pois porque entao nesse nessa neste nesta desse dessa deste desta qualquer quaisquer
    todo toda todos todas outro outra outros outras mesmo mesma eu voce voces meu minha nosso nossa
    fez faz fazer caso qual lei artigo art arts durante sendo estar pode podem deve devem quero sobre
    """.split()
)

_SUFIXOS = sorted(
    """
    amentos imentos amento imento acoes icoes acao icao coes cao mente idades idade ividade
    ivas ivos iva ivo ancias encias ancia encia aveis iveis avel ivel adoras adores adora ador
    antes ante entos ento enta istas ista ados adas idos idas ado ada ido ida ais eis oes aes
    ar er ir ou eu iu am em as es os is ao a e o s
    """.split(),
    key=len,
    reverse=True,
)

# termos leigos -> termos da lei (a expansão pesa menos que as palavras da pergunta)
SINONIMOS: dict[str, str] = {
    "noite": "repouso noturno",
    "madrugada": "repouso noturno",
    "assalto": "roubo grave ameaça",
    "assaltou": "roubo grave ameaça",
    "assaltar": "roubo grave ameaça",
    "assaltante": "roubo grave ameaça",
    "faca": "arma branca",
    "canivete": "arma branca",
    "facao": "arma branca",
    "revolver": "arma de fogo",
    "pistola": "arma de fogo",
    "espingarda": "arma de fogo",
    "garrucha": "arma de fogo",
    "matar": "homicídio matar alguém",
    "matou": "homicídio matar alguém",
    "assassinato": "homicídio matar alguém",
    "assassinou": "homicídio matar alguém",
    "agrediu": "lesão corporal ofender a integridade corporal",
    "agredir": "lesão corporal ofender a integridade corporal",
    "agressao": "lesão corporal ofender a integridade corporal",
    "espancou": "lesão corporal ofender a integridade corporal",
    "golpe": "estelionato fraude induzindo em erro",
    "enganou": "estelionato fraude induzindo em erro",
    "droga": "drogas tráfico",
    "drogas": "tráfico",
    "maconha": "drogas tráfico",
    "cocaina": "drogas tráfico",
    "crack": "drogas tráfico",
    "traficante": "tráfico drogas",
    "confessou": "confissão espontânea confessado espontaneamente",
    "confessar": "confissão espontânea confessado espontaneamente",
    "reincidente": "reincidência",
    "comparsa": "concurso de duas ou mais pessoas",
    "comparsas": "concurso de duas ou mais pessoas",
    "arrombou": "destruição ou rompimento de obstáculo",
    "arrombamento": "destruição ou rompimento de obstáculo",
    "arrombar": "destruição ou rompimento de obstáculo",
    "pulou o muro": "escalada",
    "carro": "veículo automotor",
    "moto": "veículo automotor",
    "refem": "mantém a vítima em seu poder restringindo sua liberdade",
    "sequestrou": "sequestro cárcere privado",
    "tentou": "tentativa não se consuma circunstâncias alheias",
    "dosimetria": "fixação da pena aplicação da pena",
    "pena base": "fixação da pena circunstâncias judiciais",
    "agravante": "circunstâncias agravantes agravam a pena",
    "agravantes": "circunstâncias agravantes agravam a pena",
    "atenuante": "circunstâncias atenuantes atenuam a pena",
    "atenuantes": "circunstâncias atenuantes atenuam a pena",
    "progressao": "progressão regime menos rigoroso",
    "embriagado": "embriaguez",
    "bebado": "embriaguez",
    "idoso": "idoso maior de 60 anos",
    "idosa": "idoso maior de 60 anos",
    "menor de idade": "menor de 18 anos inimputáveis",
    "defeito": "vício do produto fato do produto defeito",
    "estragado": "vício do produto impróprio ao consumo",
    "devolver": "direito de arrependimento desistir do contrato",
    "desistir da compra": "direito de arrependimento desistir do contrato 7 dias",
    "comprei pela internet": "fora do estabelecimento comercial desistir do contrato",
    "nome sujo": "bancos de dados cadastros de consumidores",
    "pretensao punitiva": "prescrição antes de transitar em julgado a sentença",
    "prescreve": "prescrição",
    "prescricao": "prescrição regula-se pelo máximo da pena",
    "cumprir a pena": "execução da pena regime",
    "trafico": "drogas entorpecentes",
    "roubou": "roubo subtrair coisa móvel alheia",
    "furtou": "furto subtrair coisa alheia móvel",
    "furtar": "furto subtrair coisa alheia móvel",
    "roubar": "roubo subtrair coisa móvel alheia",
    "sursis": "suspensão da pena execução da pena poderá ser suspensa",
}
_PESO_DOS_SINONIMOS = 0.6

# nomes pelos quais a pergunta pode citar uma lei ("art. 155 do Código Penal")
_APELIDOS_DE_LEI = {
    "codigo penal": "CP",
    "cp": "CP",
    "codigo de processo penal": "CPP",
    "cpp": "CPP",
    "constituicao": "CF",
    "constituicao federal": "CF",
    "cf": "CF",
    "adct": "ADCT",
    "codigo de defesa do consumidor": "CDC",
    "cdc": "CDC",
    "codigo civil": "CC",
    "cc": "CC",
    "lei de execucao penal": "LEP",
    "lep": "LEP",
    "lei de drogas": "L11343",
    "lei dos crimes hediondos": "L8072",
    "lei das contravencoes penais": "LCP",
    "lindb": "LINDB",
}
# sem lei na pergunta, um "art. 59" é procurado primeiro nestas
_PRIORIDADE = ("CP", "CPP", "CF", "LEP", "CDC", "CC")

_REFERENCIA = re.compile(r"\bart(?:igo)?s?\.?\s*(\d{1,2}\.\d{3}|\d{1,4})\s*(?:º|o\b)?(?:\s*-\s*([a-z])\b)?")
_LEI_POR_NUMERO = re.compile(r"\blei\s*(?:n\s*[ºo°]?\.?\s*)?(\d{1,2}\.?\d{3})")


def radical(palavra: str) -> str:
    if palavra.isdigit():
        return palavra
    for sufixo in _SUFIXOS:
        if palavra.endswith(sufixo) and len(palavra) - len(sufixo) >= 4:
            palavra = palavra[: -len(sufixo)]
            break
    if len(palavra) > 4 and palavra[-1] in "aeio":
        palavra = palavra[:-1]
    return palavra


def normalizar(texto: str) -> str:
    return sem_acentos(texto.lower()).replace("º", "o").replace("ª", "a")


def termos(texto: str) -> list[str]:
    """Texto -> radicais, sem acentos e sem palavras vazias ("furtou a bicicleta" -> ["furt", "biciclet"])."""
    palavras = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [radical(p) for p in palavras if p not in _PALAVRAS_VAZIAS and (len(p) > 1 or p.isdigit())]


class _Bm25Field:
    """Um campo indexado com BM25: listas invertidas, tamanhos e IDF."""

    def __init__(self, documentos: list[list[str]], k1: float, b: float):
        self.k1, self.b = k1, b
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.tamanhos = []
        for posicao, termos_do_documento in enumerate(documentos):
            contagem = Counter(termos_do_documento)
            self.tamanhos.append(sum(contagem.values()))
            for termo, vezes in contagem.items():
                self.postings[termo].append((posicao, vezes))
        indexados = [t for t in self.tamanhos if t]
        self.tamanho_medio = sum(indexados) / max(len(indexados), 1)
        total = len(indexados)
        self.idf = {termo: math.log(1 + (total - len(lista) + 0.5) / (len(lista) + 0.5)) for termo, lista in self.postings.items()}

    def pontuar(self, pesos: Counter, pontos: dict[int, float], fator: float = 1.0) -> None:
        for termo, peso in pesos.items():
            idf = self.idf.get(termo)
            if idf is None:
                continue
            for posicao, vezes in self.postings[termo]:
                tamanho = self.tamanhos[posicao] / self.tamanho_medio
                pontos[posicao] += fator * peso * idf * vezes * (self.k1 + 1) / (vezes + self.k1 * (1 - self.b + self.b * tamanho))


@dataclass(frozen=True, slots=True)
class SearchResult:
    dispositivo: LegalProvision
    pontuacao: float
    trecho: str  # a parte do artigo que mais responde à pergunta
    motivo: str  # "referência" (a pergunta citou o artigo) ou "texto"


class LegalSearchIndex:
    """Índice BM25 dos artigos, com busca por referência e recorte de parágrafos e incisos."""

    K1 = 1.2
    # artigos de lei variam de uma linha a várias páginas (art. 5º da CF); com o 0,75 usual,
    # artigos longos e centrais (art. 129 do CP, art. 6º do CDC) ficavam para trás
    B = 0.5
    PESO_DA_CABECA = 0.5

    def __init__(self, dispositivos: list[LegalProvision], fontes: list[dict]):
        self.dispositivos = dispositivos
        self.fontes = {fonte["id"]: fonte for fonte in fontes}
        self._por_rotulo = {d.rotulo: d for d in dispositivos}
        self._leis = {d.lei for d in dispositivos}
        self._termos_da_epigrafe = [set(termos(d.epigrafe)) for d in dispositivos]
        # decretos regulamentam leis: no empate, a lei (ou o código) vem antes do regulamento
        self._peso_da_norma = [0.8 if d.norma.startswith("Decreto ") else 1.0 for d in dispositivos]
        campos = [self._campos_do_documento(d) for d in dispositivos]
        # dois campos (BM25F simplificado): o texto inteiro, e a "cabeça" do artigo (epígrafe e
        # caput), que diz do que ele trata. Um artigo longo cujo caput é o assunto da pergunta
        # ("São considerados hediondos os seguintes crimes") não perde para artigos curtos que
        # só mencionam o assunto.
        self._texto = _Bm25Field([texto for texto, _ in campos], self.K1, self.B)
        self._cabeca = _Bm25Field([cabeca for _, cabeca in campos], self.K1, self.B)
        self._postings = self._texto.postings
        self._idf = self._texto.idf

    @classmethod
    def carregar(cls, arquivo: Path = ARQUIVO_BASE) -> "LegalSearchIndex":
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        dispositivos = [LegalProvision(**{**d, "estrutura": tuple(d["estrutura"])}) for d in dados["dispositivos"]]
        return cls(dispositivos, dados["fontes"])

    @staticmethod
    def _campos_do_documento(dispositivo: LegalProvision) -> tuple[list[str], list[str]]:
        if dispositivo.revogado:
            return [], []  # artigo revogado continua consultável pelo rótulo, mas não aparece na busca
        texto = re.sub(r"^Art\.\s*[\d.]+\s*º?(-[A-Z]+)?\.?", "", dispositivo.texto)
        caput = texto.split("\n", 1)[0]
        epigrafe = termos(dispositivo.epigrafe)
        corpo = termos(texto) + epigrafe * 2 + termos(" ".join(dispositivo.estrutura[-2:]))
        return corpo, epigrafe * 2 + termos(caput)

    # ---------- consulta ----------

    def obter(self, rotulo: str) -> LegalProvision | None:
        return self._por_rotulo.get(rotulo)

    def leis(self) -> list[dict]:
        contagem = Counter((d.lei, d.nome_lei, d.norma, d.fonte) for d in self.dispositivos)
        resumo: dict[str, dict] = {}
        for (lei, nome, norma, fonte), total in contagem.items():
            item = resumo.setdefault(lei, {"lei": lei, "nome": nome, "norma": norma, "artigos": 0, "fontes": set()})
            item["artigos"] += total
            item["fontes"].add(fonte)
        return sorted(
            ({**item, "fontes": sorted(item["fontes"])} for item in resumo.values()),
            key=lambda item: (_PRIORIDADE.index(item["lei"]) if item["lei"] in _PRIORIDADE else 99, -item["artigos"]),
        )

    def buscar(self, consulta: str, lei: str | None = None, limite: int = 5) -> list[SearchResult]:
        """Os artigos que mais respondem à pergunta, do mais para o menos relevante."""
        normalizada = normalizar(consulta)
        pesos: Counter[str] = Counter()
        for termo in termos(consulta):
            pesos[termo] += 1.0
        for expressao, expansao in SINONIMOS.items():
            if re.search(rf"\b{re.escape(expressao)}\b", normalizada):
                for termo in termos(expansao):
                    pesos[termo] = max(pesos[termo], _PESO_DOS_SINONIMOS)

        referencias = self._referencias(normalizada, lei)
        # o número do artigo citado não deve puxar outros artigos que só mencionem esse número
        for _, artigo in referencias:
            pesos.pop(artigo.split("-")[0], None)

        pontos: dict[int, float] = defaultdict(float)
        self._texto.pontuar(pesos, pontos)
        self._cabeca.pontuar(pesos, pontos, self.PESO_DA_CABECA)

        if lei is not None:
            pontos = {p: v for p, v in pontos.items() if self.dispositivos[p].lei == lei}
        # quem cobre mais termos da pergunta (pesados pela raridade) sobe: um artigo que fala de
        # "repouso noturno" e não de "furto" perde para o que fala dos dois
        peso_total = sum(peso * self._idf.get(termo, 0) for termo, peso in pesos.items()) or 1.0
        cobertura: dict[int, float] = defaultdict(float)
        for termo, peso in pesos.items():
            for posicao, _ in self._postings.get(termo, ()):
                if posicao in pontos:
                    cobertura[posicao] += peso * self._idf[termo]
        pontos = {
            p: v * (0.5 + cobertura[p] / peso_total) * self._bonus_da_epigrafe(p, pesos) * self._peso_da_norma[p]
            for p, v in pontos.items()
        }
        maximo = max(pontos.values(), default=0.0)

        resultados: dict[str, SearchResult] = {}
        for ordem, (sigla, artigo) in enumerate(referencias):
            dispositivo = self._por_rotulo.get(f"{sigla}.art{artigo}")
            if dispositivo is not None and dispositivo.rotulo not in resultados:
                resultados[dispositivo.rotulo] = SearchResult(
                    dispositivo, round(maximo + 100 - ordem, 3), self._trecho(dispositivo, pesos), "referência"
                )
        for posicao, valor in sorted(pontos.items(), key=lambda item: -item[1]):
            if len(resultados) >= limite:
                break
            dispositivo = self.dispositivos[posicao]
            if dispositivo.rotulo not in resultados:
                resultados[dispositivo.rotulo] = SearchResult(dispositivo, round(valor, 3), self._trecho(dispositivo, pesos), "texto")
        return list(resultados.values())[:limite]

    def referencias(self, consulta: str) -> list[str]:
        """Artigos citados diretamente na consulta ("art. 155 do CP" -> ["CP.art155"])."""
        return [f"{sigla}.art{artigo}" for sigla, artigo in self._referencias(normalizar(consulta), None)]

    def leis_ausentes(self, consulta: str) -> list[str]:
        """Leis que a pergunta cita e que não estão na base ("art. 33 da Lei de Drogas")."""
        normalizada = normalizar(consulta)
        ausentes = {
            sigla
            for apelido, sigla in _APELIDOS_DE_LEI.items()
            if sigla not in self._leis and re.search(rf"\b{re.escape(apelido)}\b", normalizada)
        }
        for correspondencia in _LEI_POR_NUMERO.finditer(normalizada):
            sigla = "L" + correspondencia.group(1).replace(".", "")
            if sigla not in self._leis:
                ausentes.add(sigla)
        return sorted(ausentes)

    def _bonus_da_epigrafe(self, posicao: int, pesos: Counter) -> float:
        """A pergunta repete a epígrafe ("lesão corporal", "livramento condicional"): o artigo é o assunto."""
        da_epigrafe = self._termos_da_epigrafe[posicao]
        if not da_epigrafe:
            return 1.0
        return 1.0 + 0.5 * sum(1 for termo in da_epigrafe if termo in pesos) / len(da_epigrafe)

    def _referencias(self, normalizada: str, lei_filtrada: str | None) -> list[tuple[str, str]]:
        """ "art. 155 do CP e art. 5º da CF" -> [("CP", "155"), ("CF", "5")]."""
        referencias = []
        for correspondencia in _REFERENCIA.finditer(normalizada):
            artigo = correspondencia.group(1).replace(".", "")
            if correspondencia.group(2):
                artigo += "-" + correspondencia.group(2).upper()
            depois = normalizada[correspondencia.end() : correspondencia.end() + 60]
            sigla = lei_filtrada or self._lei_citada(depois)
            candidatas = [sigla] if sigla else [s for s in _PRIORIDADE if s in self._leis]
            for candidata in candidatas:
                if f"{candidata}.art{artigo}" in self._por_rotulo:
                    referencias.append((candidata, artigo))
                    break
        return referencias

    def _lei_citada(self, trecho: str) -> str | None:
        """A lei mencionada logo depois do número do artigo ("do CP", "da Lei 8.072")."""
        numero = _LEI_POR_NUMERO.search(trecho)
        if numero:
            sigla = "L" + numero.group(1).replace(".", "")
            if sigla in self._leis:
                return sigla
        melhor = None
        for apelido, sigla in _APELIDOS_DE_LEI.items():
            posicao = re.search(rf"\b{re.escape(apelido)}\b", trecho)
            if posicao and (melhor is None or posicao.start() < melhor[0] or (posicao.start() == melhor[0] and len(apelido) > melhor[2])):
                melhor = (posicao.start(), sigla, len(apelido))
        return melhor[1] if melhor else None

    def _trecho(self, dispositivo: LegalProvision, pesos: Counter) -> str:
        """O caput e, se for outra, a linha do artigo com mais termos da pergunta."""
        linhas = dispositivo.texto.split("\n")
        caput = linhas[0]

        def relevancia(linha: str) -> float:
            return sum(pesos.get(t, 0) * self._idf.get(t, 0) for t in set(termos(linha)))

        melhor = max(linhas[1:], key=relevancia, default=None)
        partes = [caput]
        if melhor is not None and relevancia(melhor) > relevancia(caput):
            partes.append(melhor)
        return " … ".join(_encurtar(p, 350) for p in partes)

    # ---------- citações ----------

    def trecho_do_rotulo(self, rotulo: str) -> tuple[LegalProvision, str, bool] | None:
        """ "CP.art155.§4.IV" -> (artigo, texto do § 4º com o inciso IV, achou_a_parte).

        Sem o artigo na base, devolve None. Se o artigo existe mas a parte citada não foi
        encontrada no texto, devolve o artigo inteiro e achou_a_parte=False.
        """
        partes = rotulo.split(".")
        # "CP.art157.§2-A.I": o artigo é o segundo pedaço; o resto são parágrafo, inciso e alínea
        if len(partes) < 2 or not partes[1].startswith("art"):
            return None
        dispositivo = self._por_rotulo.get(f"{partes[0]}.{partes[1]}")
        if dispositivo is None:
            return None
        linhas = dispositivo.texto.split("\n")
        selecionadas = linhas
        achou = True
        for parte in partes[2:]:
            recorte = _recortar(selecionadas, parte)
            if recorte is None:
                achou = False
                break
            selecionadas = recorte
        if not achou or len(partes) == 2:
            return dispositivo, dispositivo.texto, achou
        return dispositivo, "\n".join(selecionadas), True


def _recortar(linhas: list[str], parte: str) -> list[str] | None:
    """Dentro das linhas, só as do parágrafo, inciso ou alínea pedido."""
    if parte.startswith("§") or parte.lower().startswith("paragrafo") or parte.lower().startswith("parágrafo"):
        if parte.startswith("§"):
            numero = parte[1:]
            base, _, sufixo = numero.partition("-")
            inicio = re.compile(rf"^§\s*{re.escape(base)}º?{('-' + re.escape(sufixo)) if sufixo else ''}(?![-\dº]*[-\d])")
        else:
            inicio = re.compile(r"^Parágrafo único")
        fim = re.compile(r"^(§|Parágrafo único)")
    elif re.fullmatch(r"[IVXLC]+", parte):
        inicio = re.compile(rf"^{parte}\s*[–-]")
        fim = re.compile(r"^(§|Parágrafo único|[IVXLC]+\s*[–-])")
    elif re.fullmatch(r"[a-z]", parte):
        inicio = re.compile(rf"^{parte}\)")
        fim = re.compile(r"^(§|Parágrafo único|[IVXLC]+\s*[–-]|[a-z]\))")
    else:
        return None
    for posicao, linha in enumerate(linhas):
        if inicio.match(linha):
            final = next((j for j in range(posicao + 1, len(linhas)) if fim.match(linhas[j])), len(linhas))
            return linhas[posicao:final]
    return None


def _encurtar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rsplit(" ", 1)[0] + "…"


_trava_da_base = Lock()


@cache
def _base() -> LegalSearchIndex:
    return LegalSearchIndex.carregar()


def base_de_fontes() -> LegalSearchIndex:
    """O índice, carregado uma vez por processo (cerca de 2 segundos). A trava evita carregar
    duas vezes quando o primeiro pedido chega enquanto a carga do início ainda está em curso."""
    with _trava_da_base:
        return _base()
