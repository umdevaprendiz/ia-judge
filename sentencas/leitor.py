import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

_MARCA_CASO = re.compile(r"DATASET PARA TREINAMENTO DE IA\s*—\s*CASO (\d+) DE (\d+)")
_RODAPE = re.compile(r"^Dataset Jurídico\s*—.*Página \d+ de \d+$")
_PROCESSO = re.compile(r"^Processo[^:]*:\s*(.+)$")
_SECOES = ("I. RELATÓRIO", "II. FUNDAMENTAÇÃO", "III. DISPOSITIVO")
_PAPEIS = ("Requerente", "Requerido", "Reclamante", "Reclamada", "Autor", "Réu")


@dataclass(frozen=True)
class Sentenca:
    """Uma sentença do conjunto de treinamento, com o cabeçalho e as três partes separados."""

    numero: int
    orgao: str
    ramo: str
    tema: str
    processo: str
    classe: str | None
    partes: dict[str, str] = field(hash=False)
    resultado: str
    relatorio: str
    fundamentacao: str
    dispositivo: str
    magistrado: str
    cargo: str


def ler_sentencas(caminho_pdf: str | Path) -> list[Sentenca]:
    """Lê o PDF do conjunto de treinamento e devolve as sentenças na ordem do arquivo.

    O arquivo tem uma sentença por trecho iniciado pela marca "CASO NN DE MM". As
    linhas quebradas pelo layout do PDF são juntadas em parágrafos corridos.
    """
    texto = "\n".join(pagina.extract_text() for pagina in PdfReader(caminho_pdf).pages)
    linhas = [linha.strip() for linha in texto.splitlines() if not _RODAPE.match(linha.strip())]

    inicios = [i for i, linha in enumerate(linhas) if _MARCA_CASO.search(linha)]
    if not inicios:
        raise ValueError(f"nenhuma sentença encontrada em {caminho_pdf}")

    sentencas = []
    for posicao, inicio in enumerate(inicios):
        # as duas linhas antes da marca são o cabeçalho do órgão (tribunal e vara)
        fim = inicios[posicao + 1] - 2 if posicao + 1 < len(inicios) else len(linhas)
        sentencas.append(_ler_sentenca(linhas[inicio - 2 : inicio], linhas[inicio:fim]))
    return sentencas


def _ler_sentenca(cabecalho_orgao: list[str], linhas: list[str]) -> Sentenca:
    numero = int(_MARCA_CASO.search(linhas[0]).group(1))

    campos: dict[str, str] = {}
    processo = None
    indice = 1
    while indice < len(linhas) and linhas[indice] not in _SECOES:
        linha = linhas[indice]
        if match := _PROCESSO.match(linha):
            processo = match.group(1)
        else:
            for parte in linha.split(" | "):
                chave, _, valor = parte.partition(":")
                campos[chave.strip()] = valor.strip()
        indice += 1

    secoes = _separar_secoes(linhas[indice:])
    *dispositivo, magistrado, cargo = secoes["III. DISPOSITIVO"]

    faltando = [c for c in ("Ramo", "Tema", "Resultado") if c not in campos]
    if faltando or processo is None:
        raise ValueError(f"caso {numero}: cabeçalho incompleto (faltando {faltando or 'Processo'})")

    return Sentenca(
        numero=numero,
        orgao=" — ".join(cabecalho_orgao),
        ramo=campos["Ramo"],
        tema=campos["Tema"],
        processo=processo,
        classe=campos.get("Classe"),
        partes={papel: campos[papel] for papel in _PAPEIS if papel in campos},
        resultado=campos["Resultado"],
        relatorio=_paragrafo(secoes["I. RELATÓRIO"]),
        fundamentacao=_paragrafo(secoes["II. FUNDAMENTAÇÃO"]),
        dispositivo=_paragrafo(dispositivo),
        magistrado=magistrado,
        cargo=cargo,
    )


def _separar_secoes(linhas: list[str]) -> dict[str, list[str]]:
    secoes: dict[str, list[str]] = {}
    atual = None
    for linha in linhas:
        if linha in _SECOES:
            atual = linha
            secoes[atual] = []
        elif atual is not None:
            secoes[atual].append(linha)
    faltando = [s for s in _SECOES if s not in secoes]
    if faltando:
        raise ValueError(f"seções não encontradas: {faltando}")
    return secoes


def _paragrafo(linhas: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(linhas)).strip()
