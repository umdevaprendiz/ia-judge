"""Anonimização por regras da descrição de um caso, antes de qualquer gravação (LGPD).

Troca documentos, contatos, endereços, bairros, datas de nascimento, apelidos, números de
processo e nomes de pessoas por marcadores como [CPF] ou [PESSOA 1]. O mesmo nome recebe sempre o mesmo número, e
menções parciais a um nome já trocado ("Rafael", depois de "Rafael Souza") também
são trocadas. A detecção de nomes é heurística: por isso o estudante vê o texto
anonimizado e confirma antes de salvar, e o texto original nunca é gravado.
"""

import re
import unicodedata
from dataclasses import dataclass

# ---------- documentos, contatos e identificadores ----------

_PADROES_FIXOS: list[tuple[str, re.Pattern]] = [
    ("PROCESSO", re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("CPF", re.compile(r"(?<=CPF)(?:\s*(?:n[º°o]\.?|:))?\s*\d{11}\b", re.IGNORECASE)),
    ("RG", re.compile(r"(?<=\bRG)(?:\s*(?:n[º°o]\.?|:))?\s*[\d.\-xX]{5,14}", re.IGNORECASE)),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("TELEFONE", re.compile(r"(?:\(\d{2}\)\s?|\b\d{2}\s)?\b9?\d{4}-\d{4}\b")),
    ("CEP", re.compile(r"\b\d{5}-\d{3}\b")),
    ("PLACA", re.compile(r"\b[A-Z]{3}-?\d[A-Z0-9]\d{2}\b")),
    (
        "ENDERECO",
        re.compile(
            r"\b(?:Rua|R\.|Avenida|Av\.|Travessa|Alameda|Estrada|Rodovia|Praça|Largo|Beco)\s+"
            r"[^,;\n]{2,60}?(?:,\s*(?:n[º°o]\.?\s*)?\d+[A-Za-z]?)?(?=[,;.\n]|$)"
        ),
    ),
]

# só o grupo 1 é trocado; o texto antes dele fica ("vulgo [APELIDO]", "bairro [BAIRRO]").
# A idade não é trocada de propósito: ela muda a pena (arts. 61, II, h, e 65, I, do CP).
_LETRA_MAIUSCULA = "A-ZÁÉÍÓÚÂÊÔÃÕÇ"
_PADROES_COM_CONTEXTO: list[tuple[str, re.Pattern]] = [
    # apelido entre aspas, depois de vulgo/apelido/alcunha/conhecido como: "vulgo 'Baixinho'"
    (
        "APELIDO",
        re.compile(
            r"(?i:\b(?:vulgo|apelid(?:o|ad[oa])|alcunha|conhecid[oa]\s+(?:como|por))\b)[\s:,]*"
            r"([\"“'‘][^\"”'’\n]{1,40}[\"”'’])"
        ),
    ),
    # apelido sem aspas, mesmo em minúsculas: "vulgo baixinho" (só depois de vulgo/alcunha,
    # porque "conhecido como" também aparece antes de lugares e coisas)
    ("APELIDO", re.compile(r"(?i:\b(?:vulgo|alcunha)\b)[\s:,]*([^\s,.;:!?()\[\]\"“”'‘’]{2,30})")),
    (
        "NASCIMENTO",
        re.compile(
            r"(?i:\b(?:nascid[oa]\s+(?:em|no\s+dia|aos)|data\s+de\s+nascimento)\b)[\s:,]*"
            r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}(?:º|°)?\s+de\s+[a-zç]+\s+de\s+\d{4})"
        ),
    ),
    (
        "BAIRRO",
        re.compile(
            rf"(?i:\bbairro)[\s:]*(?:(?i:d[aeo]s?)\s+)?"
            rf"([{_LETRA_MAIUSCULA}][\w'-]+(?:\s+(?:(?:de|da|do|das|dos)\s+)?[{_LETRA_MAIUSCULA}][\w'-]+){{0,3}})"
        ),
    ),
]

# ---------- nomes de pessoas ----------

_CONECTORES = {"de", "da", "do", "das", "dos", "e"}

# palavras que indicam instituição, lugar ou termo jurídico: sequências com elas não são pessoas
_NAO_PESSOA = {
    "código", "codigo", "penal", "civil", "processo", "ministério", "ministerio", "público", "publico",
    "defensoria", "tribunal", "justiça", "justica", "juízo", "juizo", "vara", "comarca", "foro", "estado",
    "federal", "estadual", "municipal", "município", "municipio", "união", "uniao", "polícia", "policia",
    "militar", "delegacia", "supremo", "superior", "súmula", "sumula", "lei", "decreto", "constituição",
    "constituicao", "república", "republica", "parte", "geral", "especial", "direito", "artigo", "art",
    "inciso", "parágrafo", "paragrafo", "juiz", "juíza", "juiza", "desembargador", "ministro", "promotor",
    "promotora", "defensor", "defensora", "delegado", "delegada", "banco", "caixa", "receita", "prefeitura",
    "secretaria", "governo", "câmara", "camara", "senado", "congresso", "sistema", "único", "unico", "saúde",
    "saude", "conselho", "cp", "cpp", "cf", "stj", "stf", "tj", "trf", "brasil", "carnaval", "natal",
    "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
    "outubro", "novembro", "dezembro", "segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado",
    "sabado", "domingo", "shopping", "supermercado", "loja", "empresa", "escola", "universidade", "hospital",
    "igreja", "ltda", "sa", "s/a", "me", "eireli", "vistos", "julgo", "condeno", "absolvo", "procedente",
    "improcedente", "relatório", "relatorio", "fundamentação", "fundamentacao", "dispositivo", "dosimetria",
}

# capitais e estados: nomes de lugar, que não são dado pessoal
_LUGARES = {
    "são paulo", "rio de janeiro", "belo horizonte", "porto alegre", "curitiba", "salvador", "recife",
    "fortaleza", "brasília", "brasilia", "goiânia", "goiania", "manaus", "belém", "belem", "florianópolis",
    "florianopolis", "vitória", "vitoria", "natal", "joão pessoa", "joao pessoa", "maceió", "maceio",
    "aracaju", "teresina", "são luís", "sao luis", "cuiabá", "cuiaba", "campo grande", "porto velho",
    "rio branco", "macapá", "macapa", "boa vista", "palmas", "minas gerais", "rio grande do sul",
    "rio grande do norte", "santa catarina", "mato grosso", "mato grosso do sul", "espírito santo",
    "espirito santo", "distrito federal", "paraná", "parana", "bahia", "pernambuco", "ceará", "ceara",
    "goiás", "goias", "pará", "para", "amazonas", "maranhão", "maranhao", "piauí", "piaui", "paraíba",
    "paraiba", "alagoas", "sergipe", "tocantins", "rondônia", "rondonia", "acre", "amapá", "amapa", "roraima",
}

# um padrão só com todos os lugares, do nome mais longo ao mais curto ("Mato Grosso do Sul" antes de "Mato Grosso")
_PADRAO_LUGARES = re.compile(
    r"\b(?:" + "|".join(re.escape(l) for l in sorted(_LUGARES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# prenomes brasileiros frequentes: pegam o nome solto ("bens de Maria"), sem sobrenome nem papel
_PRENOMES = set(
    """
    maria josé jose ana joão joao antônio antonio francisco carlos paulo pedro lucas luiz luis luís
    marcos gabriel rafael daniel marcelo bruno eduardo felipe raimundo rodrigo manoel manuel mateus
    matheus andré andre fernando fábio fabio leonardo gustavo guilherme leandro tiago thiago anderson
    ricardo márcio marcio jorge sebastião sebastiao alexandre roberto edson diego vitor victor sérgio
    sergio cláudio claudio geraldo adriano luciano júlio julio renato alex vinícius vinicius rogério
    rogerio samuel ronaldo mário mario flávio flavio igor douglas davi jeferson jefferson gilberto
    wellington henrique enzo miguel arthur heitor bernardo théo theo lorenzo benjamin murilo caio
    juliana adriana márcia marcia fernanda patrícia patricia aline sandra camila amanda bruna jéssica
    jessica letícia leticia júlia julia luciana vanessa mariana gabriela vera larissa cláudia claudia
    beatriz luana rita sônia sonia renata eliane josefa simone natália natalia francisca raimunda
    lúcia lucia isabela isabel carla débora debora rafaela tatiane sueli andreia andréia cristina
    paula daniela priscila regina helena laura alice sofia sophia valentina heloísa heloisa lívia
    livia isadora manuela cecília cecilia luiza luísa luisa lorena yasmin carolina bianca rebeca sara
    joana antônia antonia terezinha tereza teresa aparecida luzia marta edna fátima fatima rosângela
    rosangela silvana solange tânia tania viviane kelly michele michelle roberta sabrina thais
    thaís valéria valeria eduarda emanuelly agatha
    """.split()
)

# palavras que abrem frases e não fazem parte de nomes
_ABERTURAS = set(
    """
    em no na nos nas o a os as um uma de do da dos das para pelo pela com por segundo após apos
    durante quando então entao ele ela eles elas depois antes ontem hoje também tambem mas porém
    porem contudo sendo conforme consta segundo porque como onde ao aos à às este esta esse essa
    aquele aquela seu sua dia noite
    """.split()
)

_PALAVRA = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõçü]+"
_PALAVRA_MAIUSCULA = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}"
_CONECTOR = r"(?:de|da|do|das|dos|e|DE|DA|DO|DAS|DOS|E)"

# "Rafael Souza e Silva": duas ou mais palavras capitalizadas, com conectores no meio
_NOME_CAPITALIZADO = re.compile(rf"\b{_PALAVRA}(?:\s+(?:{_CONECTOR}\s+)?{_PALAVRA})+\b")
# "RAFAEL SOUZA E SILVA": como sentenças costumam grafar as partes
_NOME_MAIUSCULO = re.compile(rf"\b{_PALAVRA_MAIUSCULA}(?:\s+(?:{_CONECTOR}\s+)?{_PALAVRA_MAIUSCULA})+\b")
# "o réu Rafael", "vítima: Ana": um único nome depois de um papel processual
_NOME_APOS_PAPEL = re.compile(
    r"(?i:\b(?:réu|ré|acusad[oa]|denunciad[oa]|investigad[oa]|vítima|vitima|testemunha|autor|autora|"
    r"sr\.?|sra\.?|senhor|senhora|menor|adolescente|criança|crianca|filh[oa]|espos[oa]|marido|"
    r"companheir[oa]|namorad[oa]|irmã|irmão|irma|irmao|mãe|pai|mae|chamad[oa]|conhecid[oa] como|"
    r"identificad[oa] como|de nome|nomead[oa])"
    r")[\s:,]+(" + _PALAVRA + r")\b"
)


@dataclass(frozen=True, slots=True)
class Replacement:
    tipo: str
    original: str
    marcador: str


@dataclass(frozen=True, slots=True)
class AnonymizationResult:
    texto: str
    substituicoes: tuple[Replacement, ...]

    def contagem_por_tipo(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for substituicao in self.substituicoes:
            contagem[substituicao.tipo] = contagem.get(substituicao.tipo, 0) + 1
        return contagem


def anonimizar(texto: str) -> AnonymizationResult:
    substituicoes: list[Replacement] = []

    def trocar_fixo(tipo: str):
        def trocar(match: re.Match) -> str:
            original = match.group(0).strip()
            if not original:
                return match.group(0)
            marcador = f"[{tipo}]"
            substituicoes.append(Replacement(tipo, original, marcador))
            # mantém o espaço inicial capturado (ex.: "CPF 123..." -> "CPF [CPF]")
            prefixo = match.group(0)[: len(match.group(0)) - len(match.group(0).lstrip())]
            return prefixo + marcador

        return trocar

    for tipo, padrao in _PADROES_FIXOS:
        texto = padrao.sub(trocar_fixo(tipo), texto)

    def trocar_grupo(tipo: str):
        def trocar(match: re.Match) -> str:
            marcador = f"[{tipo}]"
            substituicoes.append(Replacement(tipo, match.group(1), marcador))
            inicio = match.start(1) - match.start()
            return match.group(0)[:inicio] + marcador + match.group(0)[match.end(1) - match.start():]

        return trocar

    for tipo, padrao in _PADROES_COM_CONTEXTO:
        texto = padrao.sub(trocar_grupo(tipo), texto)

    # lugares (capitais e estados) ficam protegidos durante a busca por nomes, senão
    # "São Paulo" viraria "São [PESSOA 1]" e "João Pessoa" seria tomado por uma pessoa
    lugares_protegidos: list[str] = []

    def proteger_lugar(match: re.Match) -> str:
        lugares_protegidos.append(match.group(0))
        return f"\ue000{len(lugares_protegidos) - 1}\ue001"

    texto = _PADRAO_LUGARES.sub(proteger_lugar, texto)

    pessoas: dict[str, str] = {}  # nome normalizado -> marcador
    partes_de_nomes: dict[str, str] = {}  # primeiro/último nome -> marcador

    def marcador_da_pessoa(nome: str) -> str:
        chave = _normalizar(nome)
        if chave not in pessoas and chave in partes_de_nomes:
            return partes_de_nomes[chave]
        if chave not in pessoas:
            pessoas[chave] = f"[PESSOA {len(pessoas) + 1}]"
            palavras = [p for p in chave.split() if p not in _CONECTORES]
            for palavra in (palavras[0], palavras[-1]):
                partes_de_nomes.setdefault(palavra, pessoas[chave])
        return pessoas[chave]

    def trocar_nome(match: re.Match, grupo: int = 0) -> str:
        inicio, fim = match.span(grupo)
        nome = match.group(grupo)
        # "Em Vitória", "No Rafael Souza": a palavra que abre a frase não faz parte do nome
        while (primeira := nome.split(maxsplit=1))[0].lower() in _ABERTURAS and len(primeira) > 1:
            deslocamento = len(nome) - len(primeira[1])
            nome, inicio = primeira[1], inicio + deslocamento
        if " " not in nome and grupo == 0:
            # sobrou uma palavra só: vale apenas se for prenome conhecido (tratado adiante)
            return match.group(0)
        if not _parece_pessoa(nome):
            return match.group(0)
        marcador = marcador_da_pessoa(nome)
        substituicoes.append(Replacement("PESSOA", nome, marcador))
        return match.group(0)[: inicio - match.start()] + marcador + match.group(0)[fim - match.start():]

    texto = _NOME_MAIUSCULO.sub(trocar_nome, texto)
    texto = _NOME_CAPITALIZADO.sub(trocar_nome, texto)
    texto = _NOME_APOS_PAPEL.sub(lambda m: trocar_nome(m, 1), texto)

    # prenome conhecido sozinho ("bens de Maria")
    def trocar_prenome(match: re.Match) -> str:
        nome = match.group(0)
        if _normalizar(nome) not in _PRENOMES:
            return nome
        marcador = marcador_da_pessoa(nome)
        substituicoes.append(Replacement("PESSOA", nome, marcador))
        return marcador

    texto = re.sub(r"\b" + _PALAVRA + r"\b", trocar_prenome, texto)

    # menções soltas a um nome já trocado ("Rafael" depois de "Rafael Souza")
    if partes_de_nomes:
        solta = re.compile(r"\b(" + _PALAVRA + r"|" + _PALAVRA_MAIUSCULA + r")\b")

        def trocar_solta(match: re.Match) -> str:
            marcador = partes_de_nomes.get(_normalizar(match.group(1)))
            if marcador is None:
                return match.group(0)
            substituicoes.append(Replacement("PESSOA", match.group(1), marcador))
            return marcador

        texto = solta.sub(trocar_solta, texto)

    # numera as pessoas pela ordem em que aparecem no texto (cada regra acha nomes em outra ordem)
    ordem: dict[str, str] = {}
    for marcador in re.findall(r"\[PESSOA \d+\]", texto):
        ordem.setdefault(marcador, f"[PESSOA {len(ordem) + 1}]")
    texto = re.sub(r"\[PESSOA \d+\]", lambda m: ordem[m.group(0)], texto)
    substituicoes = [
        Replacement(s.tipo, s.original, ordem.get(s.marcador, s.marcador)) if s.tipo == "PESSOA" else s
        for s in substituicoes
    ]

    texto = re.sub("\ue000(\\d+)\ue001", lambda m: lugares_protegidos[int(m.group(1))], texto)
    return AnonymizationResult(texto=texto, substituicoes=tuple(substituicoes))


def _normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _parece_pessoa(nome: str) -> bool:
    normalizado = _normalizar(nome)
    if normalizado in _LUGARES or _sem_acentos(normalizado) in {_sem_acentos(l) for l in _LUGARES}:
        return False
    palavras = [p for p in normalizado.split() if p not in _CONECTORES]
    if not palavras:
        return False
    return not any(p in _NAO_PESSOA or _sem_acentos(p) in _NAO_PESSOA for p in palavras)
