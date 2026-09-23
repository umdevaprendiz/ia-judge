"""Limpeza do texto extraído dos PDFs de legislação.

O pypdf devolve o texto página a página, com cabeçalhos e números de página no meio dos
artigos, palavras partidas no fim da linha ("obs-\\ntáculo") e o ordinal "º" lido como
"o" ("Art. 1 o"). Estas funções deixam o texto pronto para ser dividido em artigos.
"""

import re
import unicodedata
from collections import Counter

_TROCAS = str.maketrans(
    {
        "‑": "-",  # hífen que não quebra (usado pelo Senado no CPP)
        "‐": "-",
        "­": "",  # hífen de quebra opcional
        " ": " ",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "“": "“",
    }
)

# pronomes que seguem o hífen em "considera-se", "aplicar-se-á": o hífen fica
_CLITICOS = r"(?:se|lhes?|l[oa]s?|n[oa]s?|[oa]s?|me|te|nos|vos)\b"

# título de lei numa linha própria: "Lei no 8.072/1990", "LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990"
PADRAO_CABECALHO_DE_LEI = re.compile(
    r"^(?P<tipo>lei complementar|decreto-lei|decreto|lei|medida provis[óo]ria)\s+n\s*[ºo°]?\s*\.?\s*"
    r"(?P<numero>\d{1,3}(?:\.\d{3})*(?:-\d+)?)"
    r"(?:\s*/\s*(?P<ano>\d{4}))?"
    r"(?:,?\s+de\s+[^.]*?(?P<ano_por_extenso>\d{4}))?"
    r"\s*(?:\((?P<apelido>[^)]*)\))?\s*$",
    re.IGNORECASE,
)
_ANO_NA_LINHA_SEGUINTE = re.compile(r"^de\s+.*?(\d{4})\s*$", re.IGNORECASE)
_PARECE_DISPOSITIVO = re.compile(r"^(Art\.|§|\(|Parágrafo|Pena\b|[IVXLC]+\s*[–-]|[a-z]\))")


def sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def limpar_paginas(paginas: list[str]) -> list[str]:
    """Texto das páginas -> linhas limpas do documento inteiro."""
    paginas = [pagina.translate(_TROCAS) for pagina in paginas]
    repetidas = _linhas_de_borda_repetidas(paginas)
    linhas: list[str] = []
    for pagina in paginas:
        linhas_da_pagina = [linha.strip() for linha in pagina.splitlines()]
        linhas_da_pagina = [linha for linha in linhas_da_pagina if linha]
        total = len(linhas_da_pagina)
        for posicao, linha in enumerate(linhas_da_pagina):
            na_borda = posicao < 3 or posicao >= total - 3
            if na_borda and not PADRAO_CABECALHO_DE_LEI.match(linha):
                if linha.isdigit() or _chave_de_borda(linha) in repetidas:
                    continue
            # número de nota de rodapé grudado no fim da linha: "...do crime:5", "Constituição49"
            # (só depois de letra, para não cortar "Lei nº 10.406")
            linhas.append(re.sub(r"(?<=[a-zà-ÿ)])([:;.,]?)\d{1,3}$", r"\1", linha))
    texto = "\n".join(linhas)
    texto = juntar_palavras_partidas(texto)
    texto = corrigir_ordinais(texto)
    return texto.split("\n")


def juntar_palavras_partidas(texto: str) -> str:
    """ "obs-\\ntáculo" -> "obstáculo"; "aplicar -\\n-se-á" -> "aplicar-se-á"; "considera-\\nse" fica com hífen."""
    texto = re.sub(r"(\w) ?-\n-(?=\w)", r"\1-", texto)
    texto = re.sub(rf"(\w) ?-\n(?={_CLITICOS})", r"\1-", texto)
    return re.sub(r"(\w) ?-\n(?=[a-zà-ÿ])", r"\1", texto)


def corrigir_ordinais(texto: str) -> str:
    """ "Art. 1 o" -> "Art. 1º", "§ 4o-A" -> "§ 4º-A", "Lei no 8.072" -> "Lei nº 8.072"."""
    texto = re.sub(r"\b(\d{1,4}) ?o(?=[\s.,;:)\-]|$)", r"\1º", texto, flags=re.MULTILINE)
    return re.sub(
        r"\b(Lei|Decreto-lei|Decreto|Complementar|Provisória|Emenda Constitucional|art\.|arts\.)\s+n ?o\s+(?=\d)",
        r"\1 nº ",
        texto,
        flags=re.IGNORECASE,
    )


def _chave_de_borda(linha: str) -> str:
    """ "143Código Civil Brasileiro" e "Código Civil Brasileiro 145" viram a mesma chave."""
    return re.sub(r"[\d\s]+", "", sem_acentos(linha).lower())


def _linhas_de_borda_repetidas(paginas: list[str]) -> set[str]:
    """Cabeçalhos e rodapés: linhas curtas que se repetem no alto ou no pé de muitas páginas."""
    contagem: Counter[str] = Counter()
    for pagina in paginas:
        linhas = [linha.strip() for linha in pagina.splitlines() if linha.strip()]
        for linha in set(linhas[:3] + linhas[-3:]):
            # linhas de lei que se repetem de verdade ("I – (Revogado);") não são cabeçalho
            if len(linha) <= 70 and not _PARECE_DISPOSITIVO.match(linha):
                contagem[_chave_de_borda(linha)] += 1
    minimo = max(5, len(paginas) // 20)
    return {chave for chave, vezes in contagem.items() if vezes >= minimo and chave}
