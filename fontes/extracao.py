"""Divide o texto de um PDF de legislação em leis e cada lei em artigos.

Um artigo por registro (seção 4 do plano, fase 4): é a unidade que a busca devolve e que
a fundamentação cita (CP.art155). Parágrafos, incisos e alíneas ficam no texto do artigo,
um por linha, e podem ser recortados depois (veja busca.trecho_do_rotulo).
"""

import re
from dataclasses import dataclass, field

from .catalogo import SourceDocument, sigla_e_nome
from .texto import _ANO_NA_LINHA_SEGUINTE, PADRAO_CABECALHO_DE_LEI

_TIPOS = {
    "lei": "Lei",
    "lei complementar": "Lei Complementar",
    "decreto-lei": "Decreto-lei",
    "decreto": "Decreto",
    "medida provisória": "Medida Provisória",
    "medida provisoria": "Medida Provisória",
}

# conteúdo que não é lei (índices, exposições de motivos, tratados): encerra a lei atual
_FIM_DE_LEI = re.compile(
    r"^(Índice|ÍNDICE|Informações complementares|Exposição de [Mm]otivos|EXPOSIÇÃO DE MOTIVOS|"
    r"RESOLUÇÃO|DECISÃO|ACORDO|PROTOCOLO|CONVENÇÃO|PACTO|Pacto [Ii]nternacional|Ato internacional|"
    r"Dispositivos [Cc]onstitucionais|Legislação [Cc]orrelata|Normas correlatas|Súmulas)\b"
)
# "Rio de Janeiro, 7 de dezembro de 1940; ..." / "Brasília, 11 de setembro de 1990": fim do texto da lei
_ASSINATURA = re.compile(r"^(Rio de Janeiro|Brasília),?\s+(em\s+)?\d{1,2}º?\s+de\s+[a-zç]+\s+de\s+\d{4}", re.IGNORECASE)
_PREAMBULO = re.compile(r"^\(?Publicad[oa]|^de\s+\d{1,2}", re.IGNORECASE)
_TERMINA_EM_CONECTIVO = re.compile(
    r"\b(do|da|dos|das|de|no|na|nos|nas|pelo|pela|pelos|pelas|ao|aos|à|às|e|ou|o|a|os|as|em|com|por|que|"
    r"contra|sobre|entre|para|sem|art\.|arts\.|§)\s*$",
    re.IGNORECASE,
)
_CONTINUA_FRASE = re.compile(r"^([a-zà-ÿ]|[^()]*\)\s*[,;.]|\([^)]*\)\s*[,;.:]|[,;.])")

_ARTIGO = re.compile(
    r"^Art\.\s*(?P<num>\d\.\d{3}|\d{1,4})\s*(?P<ord>º)?\s*(?:-\s*(?P<suf>[A-Z]{1,3})\b)?\s*(?P<ponto>\.)?\s*(?P<resto>.*)$"
)
_INICIO_DE_TEXTO = re.compile(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ(“\"\[]")

_NIVEIS = {"parte": 0, "livro": 1, "titulo": 2, "capitulo": 3, "secao": 4, "subsecao": 5}
_ESTRUTURA = re.compile(
    r"^(?P<nivel>P\s?ARTE|LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SUBSE[ÇC][ÃA]O|SE[ÇC][ÃA]O)(?P<resto>(?:\s.*)?)$",
    re.IGNORECASE,
)
_NUMERAL_DA_ESTRUTURA = re.compile(r"(?i)^\s*(?:[ivxlc]+\b|[úu]nic[oa]|geral|especial|complementar|\d+)")

# linhas que começam uma parte do artigo: ficam em linha própria no texto final
_MARCA_DE_DISPOSITIVO = re.compile(r"^(Art\.|§|Parágrafo único|Pena\b|[IVXLC]+\s*[–-]|[a-z]\)|“)")
_CONTINUA_EM_PARAGRAFO = re.compile(
    r"(?<![;:])\s(no|nos|na|nas|do|dos|da|das|ao|aos|o|os|pelo|pela|pelos|pelas|em|de|com|e|ou|arts?\.)\s*$"
)
_REVOGADO = re.compile(r"^\(?\s*(Revogad|Vetad|Suprimid)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class LegalProvision:
    """Um artigo de lei, pronto para busca e citação."""

    rotulo: str  # "CP.art155"
    lei: str  # "CP"
    nome_lei: str  # "Código Penal"
    norma: str  # "Decreto-lei 2.848/1940"
    artigo: str  # "155", "157-A"
    epigrafe: str  # "Furto" (pode ser vazia)
    estrutura: tuple[str, ...]  # ("PARTE ESPECIAL", "TÍTULO II – Dos Crimes contra o Patrimônio", ...)
    texto: str  # "Art. 155. Subtrair...\n§ 1º A pena..."
    revogado: bool
    fonte: str  # id do SourceDocument


@dataclass(slots=True)
class _Segmento:
    norma: str
    ementa: str = ""
    linhas: list[str] = field(default_factory=list)
    encerrado: bool = False


def cabecalho_de_lei(linhas: list[str], i: int) -> str | None:
    """A norma que começa na linha i ("Lei 8.072/1990"), se a linha for um título de lei."""
    linha = linhas[i]
    correspondencia = PADRAO_CABECALHO_DE_LEI.match(linha)
    if correspondencia is None or len(linha) > 90:
        return None
    ano = correspondencia["ano"] or correspondencia["ano_por_extenso"]
    seguinte = i + 1
    if ano is None and seguinte < len(linhas):
        linha_do_ano = _ANO_NA_LINHA_SEGUINTE.match(linhas[seguinte])
        ano = linha_do_ano and linha_do_ano.group(1)
        seguinte += 1
    if ano is None:
        return None
    # citação no meio de uma frase que coube numa linha inteira ("...previsto no\nDecreto-Lei
    # nº 2.848, de 7 de dezembro de 1940\n(Código Penal), e no art."): não é título
    if i > 0 and _TERMINA_EM_CONECTIVO.search(linhas[i - 1]):
        return None
    if seguinte < len(linhas) and _CONTINUA_FRASE.match(linhas[seguinte]):
        return None
    tipo = _TIPOS.get(re.sub(r"\s+", " ", correspondencia["tipo"].lower()), correspondencia["tipo"])
    return f"{tipo} {correspondencia['numero']}/{ano}"


def segmentar(linhas: list[str], fonte: SourceDocument) -> list[_Segmento]:
    """Separa as linhas do documento por lei. Títulos repetidos (cabeçalho de página) são ignorados."""
    marcos = [(re.compile(padrao), sigla) for padrao, sigla in fonte.marcos]
    segmentos: list[_Segmento] = []
    atual: _Segmento | None = None
    for i, linha in enumerate(linhas):
        marco = next((sigla for padrao, sigla in marcos if padrao.match(linha)), False)
        if marco is not False:
            atual = _Segmento(norma=marco) if marco else None
            if atual:
                segmentos.append(atual)
            continue
        if _FIM_DE_LEI.match(linha):
            atual = None
            continue
        norma = cabecalho_de_lei(linhas, i)
        if norma is not None:
            if atual is not None and atual.norma == norma:
                continue  # o título da lei repetido no alto da página
            atual = _Segmento(norma=norma, ementa=_ementa(linhas, i))
            segmentos.append(atual)
            continue
        if atual is None or atual.encerrado:
            continue
        if _ASSINATURA.match(linha):
            atual.encerrado = True
            continue
        atual.linhas.append(linha)
    return segmentos


def extrair_documento(fonte: SourceDocument, linhas: list[str]) -> list[LegalProvision]:
    """Todas as leis de um documento, com os artigos de cada uma (a mesma lei em trechos é unida)."""
    por_norma: dict[str, _Segmento] = {}
    for segmento in segmentar(linhas, fonte):
        existente = por_norma.get(segmento.norma)
        if existente is None:
            por_norma[segmento.norma] = segmento
        else:
            existente.linhas.extend(segmento.linhas)
            existente.ementa = existente.ementa or segmento.ementa
    artigos: list[LegalProvision] = []
    for segmento in por_norma.values():
        artigos.extend(dividir_em_artigos(segmento.norma, segmento.ementa, segmento.linhas, fonte.id))
    return artigos


def dividir_em_artigos(norma: str, ementa: str, linhas: list[str], fonte_id: str) -> list[LegalProvision]:
    sigla, nome = sigla_e_nome(norma, ementa)
    inicios = _inicios_validos(linhas)

    artigos: list[LegalProvision] = []
    estrutura: list[tuple[int, str]] = []
    nome_pendente = False  # "CAPÍTULO I" numa linha e o nome do capítulo na seguinte
    atual: dict | None = None
    antes_do_primeiro: list[str] = []

    def fechar() -> None:
        if atual is not None:
            artigos.append(_montar(atual, sigla, nome, norma, fonte_id))

    for i, linha in enumerate(linhas):
        nivel = _nivel_da_estrutura(linha)
        if nivel is not None:
            estrutura = [(n, t) for n, t in estrutura if n < nivel] + [(nivel, linha)]
            nome_pendente = not re.search(r"[–-]\s*\S", linha.split(None, 2)[-1] if " " in linha else "")
            continue
        if estrutura and i > 0 and _nivel_da_estrutura(linhas[i - 1]) is not None and not nome_pendente:
            # "TÍTULO II – Dos Crimes contra o" + "Patrimônio": o nome continua na linha seguinte
            if _TERMINA_EM_CONECTIVO.search(linhas[i - 1]) and not _MARCA_DE_DISPOSITIVO.match(linha):
                nivel_anterior, titulo = estrutura[-1]
                estrutura[-1] = (nivel_anterior, f"{titulo} {linha}")
                continue
        if nome_pendente:
            nome_pendente = False
            if not _MARCA_DE_DISPOSITIVO.match(linha) and len(linha) <= 120:
                nivel_anterior, titulo = estrutura[-1]
                estrutura[-1] = (nivel_anterior, f"{titulo} – {linha}")
                continue
        if i in inicios:
            buffer = atual["linhas"] if atual else antes_do_primeiro
            epigrafe = buffer.pop() if buffer and _parece_epigrafe(buffer[-1]) else ""
            fechar()
            numero, sufixo = inicios[i]
            atual = {
                "artigo": f"{numero}-{sufixo}" if sufixo else str(numero),
                "epigrafe": epigrafe,
                "estrutura": tuple(t for _, t in estrutura),
                "linhas": [linha],
            }
            continue
        if atual is not None:
            atual["linhas"].append(linha)
        else:
            antes_do_primeiro.append(linha)
    fechar()
    return artigos


def _inicios_validos(linhas: list[str]) -> dict[int, tuple[int, str]]:
    """Linhas que começam artigos. Artigos citados dentro de outros (leis que alteram o CP,
    por exemplo) quebram a ordem crescente; a maior sequência crescente fica, o resto é texto."""
    candidatos: list[tuple[int, tuple[int, int, str]]] = []
    for i, linha in enumerate(linhas):
        correspondencia = _ARTIGO.match(linha)
        if correspondencia is None or not (correspondencia["ord"] or correspondencia["ponto"]):
            continue
        resto = correspondencia["resto"]
        if resto and not _INICIO_DE_TEXTO.match(resto):
            continue
        sufixo = correspondencia["suf"] or ""
        candidatos.append((i, (int(correspondencia["num"].replace(".", "")), len(sufixo), sufixo)))

    # maior subsequência estritamente crescente (paciência), guardando o caminho
    pilhas: list[tuple[int, str]] = []  # chave do topo de cada pilha
    topo: list[int] = []  # índice (em candidatos) do topo de cada pilha
    anterior: list[int] = [-1] * len(candidatos)
    for posicao, (_, chave) in enumerate(candidatos):
        esquerda, direita = 0, len(pilhas)
        while esquerda < direita:
            meio = (esquerda + direita) // 2
            if pilhas[meio] < chave:
                esquerda = meio + 1
            else:
                direita = meio
        if esquerda > 0:
            anterior[posicao] = topo[esquerda - 1]
        if esquerda == len(pilhas):
            pilhas.append(chave)
            topo.append(posicao)
        else:
            pilhas[esquerda] = chave
            topo[esquerda] = posicao
    escolhidos: dict[int, tuple[int, str]] = {}
    posicao = topo[-1] if topo else -1
    while posicao != -1:
        indice, (numero, _, sufixo) = candidatos[posicao]
        escolhidos[indice] = (numero, sufixo)
        posicao = anterior[posicao]
    return escolhidos


def _nivel_da_estrutura(linha: str) -> int | None:
    correspondencia = _ESTRUTURA.match(linha)
    if correspondencia is None or not linha[0].isupper():
        return None
    if not _NUMERAL_DA_ESTRUTURA.match(correspondencia["resto"]):
        return None
    palavra = correspondencia["nivel"].lower().replace(" ", "")
    palavra = palavra.replace("í", "i").replace("ç", "c").replace("ã", "a")
    return _NIVEIS.get(palavra)


def _parece_epigrafe(linha: str) -> bool:
    """ "Furto", "Furto qualificado", "Anterioridade da Lei": título curto antes do artigo."""
    return (
        len(linha) <= 80
        and linha[0].isupper()
        and not linha.endswith((".", ";", ":", ",", "–", "-"))
        and not _MARCA_DE_DISPOSITIVO.match(linha)
        and _nivel_da_estrutura(linha) is None
    )


def _montar(dados: dict, sigla: str, nome: str, norma: str, fonte_id: str) -> LegalProvision:
    texto = _reorganizar(dados["linhas"])
    corpo = _ARTIGO.match(texto)
    resto = corpo["resto"] if corpo else texto
    return LegalProvision(
        rotulo=f"{sigla}.art{dados['artigo']}",
        lei=sigla,
        nome_lei=nome,
        norma=norma,
        artigo=dados["artigo"],
        epigrafe=dados["epigrafe"],
        estrutura=dados["estrutura"],
        texto=texto,
        revogado=bool(_REVOGADO.match(resto)) and len(texto) < 200,
        fonte=fonte_id,
    )


def _reorganizar(linhas: list[str]) -> str:
    """Junta as linhas quebradas pelo PDF; parágrafos, incisos e epígrafes internas ficam em linha própria."""
    saida: list[str] = []
    for posicao, linha in enumerate(linhas):
        seguinte = linhas[posicao + 1] if posicao + 1 < len(linhas) else ""
        epigrafe_interna = _parece_epigrafe(linha) and bool(re.match(r"^(§|Art\.)", seguinte))
        # "...as indicadas no" + "§ 9º deste artigo, aumenta-se...": o "§" citado continua a frase
        citacao_de_paragrafo = bool(saida) and linha.startswith("§") and bool(_CONTINUA_EM_PARAGRAFO.search(saida[-1]))
        if not saida or (_MARCA_DE_DISPOSITIVO.match(linha) and not citacao_de_paragrafo) or epigrafe_interna or saida[-1].endswith("\u0000"):
            saida.append(linha + ("\u0000" if epigrafe_interna else ""))
        else:
            saida[-1] = f"{saida[-1]} {linha}"
    return "\n".join(linha.rstrip("\u0000") for linha in saida)


def _ementa(linhas: list[str], i: int) -> str:
    """A primeira linha descritiva depois do título da lei ("Dispõe sobre...", "(Código Penal)")."""
    for j in range(i + 1, min(i + 5, len(linhas))):
        linha = linhas[j]
        if _PREAMBULO.match(linha) or cabecalho_de_lei(linhas, j) is not None:
            continue
        if re.match(r"^(O|A)\s+PRESIDENT|^Faço saber|^O CONGRESSO|^Art\.", linha, re.IGNORECASE):
            return ""
        return linha.strip("()")[:200]
    return ""


def escolher_versoes(artigos_por_fonte: dict[str, list[LegalProvision]], datas: dict[str, str]) -> list[LegalProvision]:
    """Uma versão de cada artigo, a mais atual que se possa confiar.

    Para cada lei, a fonte principal é, entre as mais completas (ao menos 90% dos artigos da
    maior), a edição mais recente: o CPP da Coletânea (2026) vence o da 5ª ed. (2023). Uma
    edição mais nova que traga só parte da lei substitui esses artigos (a parte criminal da
    Lei 9.099 da Coletânea, de 2026, vence a do livro do Código Civil, de 2008), desde que o
    artigo não pareça cortado (ao menos 60% do texto). Artigos que a principal não tem vêm
    das outras fontes.
    """
    por_lei: dict[str, dict[str, list[LegalProvision]]] = {}
    for fonte_id, artigos in artigos_por_fonte.items():
        for artigo in artigos:
            por_lei.setdefault(artigo.lei, {}).setdefault(fonte_id, []).append(artigo)
    escolhidos: list[LegalProvision] = []
    for versoes in por_lei.values():
        maior = max(len(artigos) for artigos in versoes.values())
        elegiveis = [fonte_id for fonte_id, artigos in versoes.items() if len(artigos) >= 0.9 * maior]
        principal = max(elegiveis, key=lambda fonte_id: (datas[fonte_id], len(versoes[fonte_id])))
        artigos = {artigo.rotulo: artigo for artigo in versoes[principal]}
        for fonte_id in sorted(versoes, key=lambda f: datas[f], reverse=True):
            if fonte_id == principal:
                continue
            mais_nova = datas[fonte_id] > datas[principal]
            for artigo in versoes[fonte_id]:
                existente = artigos.get(artigo.rotulo)
                if existente is None or (
                    mais_nova and existente.fonte == principal and len(artigo.texto) >= 0.6 * len(existente.texto)
                ):
                    artigos[artigo.rotulo] = artigo
        escolhidos.extend(sorted(artigos.values(), key=_ordem_do_artigo))
    return escolhidos


def _ordem_do_artigo(artigo: LegalProvision) -> tuple[int, int, str]:
    numero, _, sufixo = artigo.artigo.partition("-")
    return int(numero), len(sufixo), sufixo
