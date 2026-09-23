"""Quais PDFs alimentam a base e como cada lei é chamada nela.

A sigla de cada lei é a mesma usada nos rótulos dos casos de dosimetria (CP.art155,
L11343.art33): códigos têm sigla própria; as demais leis viram "L" + número
(L8072), decretos-leis "DL" + número e decretos "D" + número.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Um PDF de legislação e o que dele entra na base."""

    id: str
    arquivo: str
    titulo: str
    atualizado_ate: str  # "AAAA-MM", como a própria edição informa
    # marcos próprios do documento: (regex da linha, sigla que começa ali, ou None para encerrar)
    marcos: tuple[tuple[str, str | None], ...] = field(default=())


FONTES: tuple[SourceDocument, ...] = (
    SourceDocument(
        id="coletanea-penal-16",
        arquivo="Coletanea_basica_penal_16ed.pdf",
        titulo="Coletânea básica penal, 16ª ed. (Senado Federal)",
        atualizado_ate="2026-01",
    ),
    SourceDocument(
        id="cf-ec134",
        arquivo="CF88_EC134_separata.pdf",
        titulo="Constituição Federal, compilada até a EC 134/2024 (Senado Federal)",
        atualizado_ate="2024-12",
        marcos=(
            (r"^Título I – Dos Princípios Fundamentais$", "CF"),
            (r"^ATO DAS DISPOSIÇÕES$", "ADCT"),
            (r"^Emendas Constitucionais de Revisão$", None),
        ),
    ),
    SourceDocument(
        id="cdc-13",
        arquivo="Código de defesa do consumidor -13ed.pdf",
        titulo="Código de Defesa do Consumidor, 13ª ed. (Câmara dos Deputados)",
        atualizado_ate="2024-03",
    ),
    SourceDocument(
        id="cpp-5",
        arquivo="Codigo_processo_penal_5ed.pdf",
        titulo="Código de Processo Penal, 5ª ed. (Senado Federal)",
        atualizado_ate="2023-02",
    ),
    SourceDocument(
        id="cc-2",
        arquivo="Código Civil 2 ed.pdf",
        titulo="Código Civil brasileiro e legislação correlata, 2ª ed. (Senado Federal)",
        atualizado_ate="2008-07",
    ),
)

# "Decreto-lei 2.848/1940" -> (sigla, nome)
LEIS_CONHECIDAS: dict[str, tuple[str, str]] = {
    "Decreto-lei 2.848/1940": ("CP", "Código Penal"),
    "Decreto-lei 3.689/1941": ("CPP", "Código de Processo Penal"),
    "Decreto-lei 3.688/1941": ("LCP", "Lei das Contravenções Penais"),
    "Decreto-lei 3.914/1941": ("LICP", "Lei de Introdução ao Código Penal"),
    "Decreto-lei 3.931/1941": ("LICPP", "Lei de Introdução ao Código de Processo Penal"),
    "Decreto-lei 4.657/1942": ("LINDB", "Lei de Introdução às Normas do Direito Brasileiro"),
    "Lei 10.406/2002": ("CC", "Código Civil"),
    "Lei 8.078/1990": ("CDC", "Código de Defesa do Consumidor"),
    "Lei 7.210/1984": ("LEP", "Lei de Execução Penal"),
    "Lei 8.072/1990": ("L8072", "Lei dos Crimes Hediondos"),
    "Lei 9.099/1995": ("L9099", "Lei dos Juizados Especiais Cíveis e Criminais"),
    "Lei 10.259/2001": ("L10259", "Lei dos Juizados Especiais Federais"),
    "Lei 12.830/2013": ("L12830", "Lei da investigação criminal pelo delegado de polícia"),
    "Lei 11.343/2006": ("L11343", "Lei de Drogas"),
    "Lei 8.137/1990": ("L8137", "Lei dos Crimes contra a Ordem Tributária, Econômica e as Relações de Consumo"),
    "Lei 9.656/1998": ("L9656", "Lei dos Planos de Saúde"),
    "Lei 9.870/1999": ("L9870", "Lei da Mensalidade Escolar"),
    "Lei 10.741/2003": ("L10741", "Estatuto da Pessoa Idosa"),
    "Lei 12.414/2011": ("L12414", "Lei do Cadastro Positivo"),
    "Lei 12.529/2011": ("L12529", "Lei de Defesa da Concorrência"),
    "Lei 8.245/1991": ("L8245", "Lei do Inquilinato"),
    "Lei 8.009/1990": ("L8009", "Lei do Bem de Família"),
    "Lei 9.307/1996": ("L9307", "Lei de Arbitragem"),
    "Lei 9.279/1996": ("L9279", "Lei da Propriedade Industrial"),
}

NOMES_ESPECIAIS = {
    "CF": "Constituição Federal",
    "ADCT": "Ato das Disposições Constitucionais Transitórias",
}


def sigla_e_nome(norma: str, ementa: str = "") -> tuple[str, str]:
    """ "Lei 8.072/1990" -> ("L8072", nome conhecido ou a ementa)."""
    if norma in LEIS_CONHECIDAS:
        return LEIS_CONHECIDAS[norma]
    if norma in NOMES_ESPECIAIS:
        return norma, NOMES_ESPECIAIS[norma]
    tipo, _, numero_e_ano = norma.rpartition(" ")
    numero = numero_e_ano.split("/")[0].replace(".", "").replace("-", "_")
    prefixos = {"Lei": "L", "Decreto-lei": "DL", "Decreto": "D", "Lei Complementar": "LC", "Medida Provisória": "MP"}
    return prefixos.get(tipo, "N") + numero, (ementa or norma)
