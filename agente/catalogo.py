"""O que o agente procura na descrição do caso: indícios de cada circunstância da parte geral
do CP e de cada qualificadora ou causa de aumento/diminuição da parte especial.

Os indícios são expressões regulares escritas à mão, e só SUGEREM: o estudante confirma cada
item antes do cálculo, e cada sugestão mostra a frase do caso que a motivou. As penas e as
frações não estão aqui: vêm do texto da lei (agente/lei.py), para não haver número copiado à mão.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GeneralCircumstance:
    """Agravante, atenuante, causa geral de aumento/diminuição ou circunstância judicial."""

    codigo: str
    titulo: str
    rotulo: str  # dispositivo na base de legislação ("CP.art61.I"); vazio nas circunstâncias judiciais
    indicios: re.Pattern | None
    preponderante: bool = False  # art. 67 do CP (motivos, personalidade, reincidência)
    # não sugerir em crimes cometidos com violência ou grave ameaça (ex.: arrependimento posterior)
    so_sem_violencia: bool = False


def _re(padrao: str) -> re.Pattern:
    return re.compile(padrao, re.IGNORECASE)


_REU = r"(?:r[ée]u|acusad[oa]|agente|autor|denunciad[oa]|condenad[oa]|homem|rapaz|jovem|indiv[íi]duo|suspeit[oa])"
# esposa, companheira, namorada, noiva, ex-mulher...: relação doméstica e familiar com a vítima
_PARCEIRA = r"\b(?:(?:sua|a própria|a) (?:esposa|companheira|namorada|noiva|mulher)|esposa|companheira|namorada|noiva|ex-(?:mulher|esposa|companheira|namorada|noiva))\b"

AGRAVANTES: tuple[GeneralCircumstance, ...] = (
    GeneralCircumstance(
        "reincidencia", "Reincidência", "CP.art61.I",
        _re(r"reincident|j[áa] (?:havia sido |tinha sido |foi |fora )?condenad|condena[çc][ãa]o (?:anterior|definitiva|transitada)"),
        preponderante=True,
    ),
    GeneralCircumstance("motivo_futil_ou_torpe", "Motivo fútil ou torpe", "CP.art61.II.a", _re(r"f[úu]til|torpe|motivo banal|por ci[úu]mes?"), preponderante=True),
    GeneralCircumstance("facilitar_outro_crime", "Para facilitar ou assegurar outro crime", "CP.art61.II.b", _re(r"para (?:garantir|assegurar|facilitar|esconder|ocultar) (?:o|a|outro)")),
    GeneralCircumstance(
        "traicao_emboscada", "Traição, emboscada, dissimulação ou recurso que dificulte a defesa", "CP.art61.II.c",
        _re(r"trai[çc][ãa]o|emboscada|dissimula|pelas costas|de surpresa|enquanto (?:a v[íi]tima |ela |ele )?dormia|sem chance de defesa"),
    ),
    GeneralCircumstance(
        "meio_cruel", "Veneno, fogo, explosivo, tortura ou meio cruel", "CP.art61.II.d",
        _re(r"veneno|envenen|\bfogo\b|incendi|explos|tortur|cruel|asfixi|estrangul"),
    ),
    GeneralCircumstance(
        "contra_familiar", "Contra ascendente, descendente, irmão ou cônjuge", "CP.art61.II.e",
        _re(r"contra (?:o |a |seu |sua |o próprio |a própria )?(?:pai|m[ãa]e|irm[ãa]o?|filh[oa]|c[ôo]njuge|esposa|marido|av[ôó])\b"),
    ),
    GeneralCircumstance(
        "relacoes_domesticas", "Abuso de autoridade, relações domésticas ou violência contra a mulher", "CP.art61.II.f",
        _re(r"viol[êe]ncia dom[ée]stica|coabita|hospitalidade|companheira|namorada|ex-(?:mulher|esposa|companheira|namorada)"),
    ),
    GeneralCircumstance("abuso_de_poder", "Abuso de poder ou violação de dever do cargo", "CP.art61.II.g", _re(r"abuso de poder|viola[çc][ãa]o de dever|valendo-se do cargo")),
    GeneralCircumstance(
        "vitima_vulneravel", "Contra criança, maior de 60 anos, enfermo ou mulher grávida", "CP.art61.II.h",
        _re(r"crian[çc]a|idos[oa]|v[íi]tima[^.;]{0,40}\b(?:6\d|7\d|8\d|9\d) anos|gr[áa]vida|gestante|enferm[oa]"),
    ),
    GeneralCircumstance("sob_protecao_da_autoridade", "Ofendido sob proteção da autoridade", "CP.art61.II.i", _re(r"sob (?:a )?(?:prote[çc][ãa]o|cust[óo]dia) (?:imediata )?da autoridade|escoltad")),
    GeneralCircumstance(
        "calamidade", "Em incêndio, naufrágio, inundação ou calamidade pública", "CP.art61.II.j",
        _re(r"inc[êe]ndio|naufr[áa]gio|inunda[çc][ãa]o|calamidade|enchente|pandemia"),
    ),
    GeneralCircumstance("embriaguez_preordenada", "Embriaguez preordenada", "CP.art61.II.l", _re(r"(?:bebeu|embriagou-se) (?:para|de prop[óo]sito)|embriaguez preordenada|para ter coragem")),
    GeneralCircumstance("lider_do_grupo", "Promove ou organiza a atuação dos demais", "CP.art62.I", _re(r"\bl[íi]der\b|chefe do grupo|organizou (?:o crime|a a[çc][ãa]o)|comandou|mandante")),
    GeneralCircumstance("mediante_paga", "Mediante paga ou promessa de recompensa", "CP.art62.IV", _re(r"mediante (?:paga|pagamento)|promessa de recompensa|recebeu (?:dinheiro|pagamento) para")),
)

ATENUANTES: tuple[GeneralCircumstance, ...] = (
    GeneralCircumstance(
        "menoridade_ou_senilidade", "Réu menor de 21 anos na data do fato ou maior de 70 na sentença", "CP.art65.I",
        _re(rf"{_REU}[^.;]{{0,60}}\b(?:18|19|20|7\d|8\d|9\d) anos|\b(?:18|19|20) anos[^.;]{{0,40}}{_REU}|menor de 21|maior de 70"),
        preponderante=True,
    ),
    GeneralCircumstance("desconhecimento_da_lei", "Desconhecimento da lei", "CP.art65.II", _re(r"desconhecia a lei|n[ãa]o sabia que (?:era|seria) crime")),
    GeneralCircumstance("relevante_valor", "Motivo de relevante valor social ou moral", "CP.art65.III.a", _re(r"relevante valor"), preponderante=True),
    GeneralCircumstance(
        "reparacao_do_dano", "Procurou evitar ou minorar as consequências, ou reparou o dano", "CP.art65.III.b",
        _re(r"(?:procurou|tentou) (?:evitar|minorar|diminuir)|repar(?:ou|ado) o dano|socorreu|levou (?:a v[íi]tima )?ao hospital|devolveu|ressarciu|restituiu"),
    ),
    GeneralCircumstance(
        "coacao_ordem_ou_violenta_emocao", "Coação resistível, ordem de superior ou violenta emoção provocada pela vítima", "CP.art65.III.c",
        _re(r"coa[çc][ãa]o|coagid|ordem (?:de|do) superior|violenta emo[çc][ãa]o|injusta provoca[çc][ãa]o|provocad[oa] pela v[íi]tima"),
    ),
    GeneralCircumstance(
        "confissao_espontanea", "Confissão espontânea", "CP.art65.III.d",
        _re(r"confess|admitiu (?:a autoria|o crime|os fatos|ter)"), preponderante=True,
    ),
    GeneralCircumstance("influencia_de_multidao", "Sob influência de multidão em tumulto", "CP.art65.III.e", _re(r"multid[ãa]o|tumulto|arrast[ãa]o")),
    GeneralCircumstance("atenuante_inominada", "Circunstância relevante não prevista em lei (art. 66)", "CP.art66", None),
)

CAUSAS_GERAIS: tuple[GeneralCircumstance, ...] = (
    GeneralCircumstance(
        "tentativa", "Tentativa", "CP.art14.parágrafo_único",
        _re(
            r"\btent(?:ou|aram|ativa)\b|n[ãa]o consegui|n[ãa]o se consum|sem conseguir|frustrad|"
            r"(?:foi|foram) (?:impedid|interrompid|surpreendid|contid)[oa]s?|antes de (?:conseguir|sair|fugir|levar)"
        ),
    ),
    GeneralCircumstance(
        "arrependimento_posterior", "Arrependimento posterior (reparação antes da denúncia)", "CP.art16",
        _re(r"devolveu|restituiu|ressarciu|repar(?:ou|ado) (?:o dano|o preju[íi]zo)|pagou o preju[íi]zo"), so_sem_violencia=True,
    ),
    GeneralCircumstance(
        "participacao_de_menor_importancia", "Participação de menor importância", "CP.art29.§1",
        _re(r"apenas (?:vigiou|ficou vigiando|deu cobertura|emprestou|dirigiu)|participa[çc][ãa]o (?:menor|de menor import[âa]ncia)|ficou do lado de fora"),
    ),
    GeneralCircumstance(
        "semi_imputabilidade", "Semi-imputabilidade (perturbação da saúde mental)", "CP.art26.parágrafo_único",
        _re(r"semi-?imput|perturba[çc][ãa]o (?:da sa[úu]de )?mental|desenvolvimento mental (?:incompleto|retardado)|transtorno mental|laudo psiqui"),
    ),
    GeneralCircumstance(
        "erro_de_proibicao_evitavel", "Erro sobre a ilicitude do fato, evitável", "CP.art21",
        _re(r"n[ãa]o sabia que (?:era|seria) (?:crime|proibido|il[íi]cito)|acreditava (?:que era|ser) (?:permitido|legal)|desconhecia a (?:proibi|ilicitude)"),
    ),
    GeneralCircumstance(
        "concurso_formal", "Concurso formal (uma só ação, dois ou mais crimes)", "CP.art70",
        _re(r"uma s[óo] (?:a[çc][ãa]o|conduta)|com um [úu]nico (?:disparo|golpe|ato|tiro)|duas v[íi]timas|ambas as v[íi]timas"),
    ),
    GeneralCircumstance(
        "crime_continuado", "Crime continuado", "CP.art71",
        _re(r"(?:v[áa]rias|diversas|repetidas|sucessivas) vezes|em (?:\d+|duas|tr[êe]s|quatro|cinco|v[áa]rias) ocasi[õo]es|reiteradamente|continuidade delitiva|todos os meses|durante (?:meses|semanas|anos)"),
    ),
)

CIRCUNSTANCIAS_JUDICIAIS: tuple[GeneralCircumstance, ...] = (
    GeneralCircumstance("culpabilidade", "Culpabilidade", "", _re(r"premedit|planej|frieza|sangue frio|culpabilidade (?:elevada|acentuada|exacerbada)")),
    GeneralCircumstance("antecedentes", "Antecedentes", "", _re(r"maus antecedentes|antecedentes criminais|outras condena[çc][õo]es|condena[çc][õo]es anteriores|ficha criminal")),
    GeneralCircumstance("conduta_social", "Conduta social", "", _re(r"conduta social (?:ruim|reprov|negativa)|temido (?:no bairro|na comunidade)")),
    GeneralCircumstance("personalidade", "Personalidade", "", _re(r"personalidade (?:violenta|agressiva|voltada|desajustada)")),
    GeneralCircumstance("motivos", "Motivos", "", _re(r"por vingan[çc]a|por gan[âa]ncia|lucro f[áa]cil|por ego[íi]smo")),
    GeneralCircumstance("circunstancias", "Circunstâncias do crime", "", _re(r"na frente (?:dos|das|de) (?:filhos|crian[çc]as)|na presen[çc]a (?:dos|das|de) (?:filhos|crian[çc]as)|local ermo")),
    GeneralCircumstance(
        "consequencias", "Consequências do crime", "",
        _re(r"preju[íi]zo (?:elevado|expressivo|grande|enorme|de R\$\s?\d{2,3}\.\d{3})|R\$\s?\d{2,3}\.\d{3}|traum|sequela|trauma psicol|n[ãa]o (?:foi|foram) recuperad"),
    ),
    GeneralCircumstance("comportamento_da_vitima", "Comportamento da vítima", "", None),
)

# Indícios das qualificadoras e causas de aumento/diminuição da parte especial: quando o texto
# da opção (da lei) fala do assunto da 1ª expressão, a descrição é procurada com a 2ª.
INDICIOS_DAS_OPCOES: tuple[tuple[re.Pattern, re.Pattern, bool], ...] = tuple(
    (_re(assunto), _re(descricao), exigido)
    for assunto, descricao, *resto in (
        # exigido: quando a lei fala disto, a descrição tem que falar também (a arma de uso restrito
        # do § 2º-B do art. 157 é arma de fogo, mas nem toda arma de fogo é de uso restrito)
        (r"uso restrito ou proibido", r"uso (?:restrito|proibido)|fuzil|metralhadora|\bpistola \.40|calibre restrito", True),
        (r"repouso noturno", r"\bnoite|noturn|madrugada"),
        (
            r"concurso de (?:duas|2) (?:\(duas\) )?ou mais pessoas",
            r"comparsa|em dupla|\b(?:dois|duas|tr[êe]s|dois outros|quatro) (?:homens|indiv[íi]duos|agentes|rapazes|jovens|pessoas|comparsas)|acompanhad[oa] de|junto com|em conjunto|coautor|agiram juntos|um (?:amigo|colega) (?:dele|do r[ée]u)",
        ),
        (r"arma de fogo", r"arma de fogo|rev[óo]lver|pistola|espingarda|fuzil|garrucha|disparo|atirou|\btiros?\b"),
        (r"arma branca", r"\bfaca\b|canivete|fac[ãa]o|punhal|arma branca|estilete|foice|peixeira"),
        (
            r"destrui[çc][ãa]o ou rompimento de obst[áa]culo",
            r"arromb|quebr\w+ (?:a |o )?(?:porta|janela|vidro|cadeado|fechadura|grade)|for[çc]\w+ (?:a |o )?(?:porta|janela|fechadura|cadeado)|rompeu",
        ),
        (r"escalada", r"escal|pul\w+ (?:o |um |a )?(?:muro|port[ãa]o|grade|janela|cerca)|pelo telhado"),
        (r"chave falsa", r"chave falsa|mixa|micha|chave (?:mestra|copiada|falsificada)"),
        (r"abuso de confian[çc]a", r"empregad[oa]|funcion[áa]ri[oa]|confian[çc]a|bab[áa]|caseir[oa]|diarista"),
        (r"mediante fraude", r"engan|fingiu|se passou por|disfar[çc]|ardil"),
        (r"destreza", r"sem que (?:a v[íi]tima|ela|ele) percebesse|batedor de carteira|punguista"),
        (r"transportado para outro Estado ou para o exterior", r"outro estado|outra unidade da federa|exterior|paraguai|bol[íi]via|fronteira"),
        (r"transporte de valores", r"carro-forte|transporte de valores|malote"),
        (r"restringindo sua liberdade|mant[ée]m a v[íi]tima em seu poder", r"ref[ée]m|amarr|tranc(?:ou|ada|ado|aram)|mantiveram|manteve (?:a v[íi]tima|as v[íi]timas)|porta-malas|cativeiro|restring|sequestr"),
        (r"les[ãa]o corporal grave|natureza grave", r"les[ãa]o (?:corporal )?grave|internad|fratur|perigo de vida|\buti\b|hospitaliz"),
        (r"(?:resulta|resultar) morte|^\s*morte|II – morte", r"\bmorreu|faleceu|\bmorte\b|[óo]bito|matou|veio a falecer"),
        (r"motivo f[úu]til", r"f[úu]til|motivo banal|motivo (?:bobo|insignificante)|discuss[ãa]o por|briga por causa|por ci[úu]mes?"),
        (r"motivo torpe|paga ou promessa de recompensa", r"torpe|recompensa|pagamento para|contratad\w+ para|heran[çc]a|vingan[çc]a"),
        (r"veneno, fogo, explosivo|meio insidioso ou cruel", r"veneno|envenen|\bfogo\b|incendi|queim|explos|asfixi|estrangul|sufoc|tortur|cruel"),
        (r"trai[çc][ãa]o|emboscada|dificulte ou torne imposs[íi]vel a defesa", r"pelas costas|emboscada|trai[çc][ãa]o|dissimul|de surpresa|dormindo|sem chance de defesa"),
        (r"assegurar a execu[çc][ãa]o, a oculta[çc][ãa]o|impunidade ou vantagem de outro crime", r"para (?:esconder|ocultar|garantir|assegurar)|queima de arquivo"),
        (r"condi[çc][ãa]o do sexo feminino|contra a mulher", r"esposa|companheira|namorada|ex-(?:mulher|companheira|namorada|esposa)|viol[êe]ncia dom[ée]stica|feminic"),
        (r"menor de 14|contra crian[çc]a", r"crian[çc]a|\b(?:[1-9]|1[0-3]) anos\b|menor de 14"),
        (r"idoso|maior de 60|60 \(sessenta\) anos", r"idos[oa]|\b(?:6\d|7\d|8\d|9\d) anos"),
        (r"culpos|se o homic[íi]dio [ée] culposo|se a les[ãa]o [ée] culposa", r"\bculpa\b|culposo|imprud|neglig|imper[íi]c|sem querer|acidente|excesso de velocidade|sem inten[çc][ãa]o"),
        (r"relevante valor social ou moral|violenta emo[çc][ãa]o", r"relevante valor|violenta emo[çc][ãa]o|injusta provoca[çc][ãa]o|provoca[çc][ãa]o da v[íi]tima"),
        (r"pequeno valor", r"pequeno valor|valor (?:baixo|irris[óo]rio|[íi]nfimo)|R\$\s?\d{1,3},\d{2}\b|R\$\s?\d{1,3}\b(?![.,]\d{3})"),
        (r"dispositivo eletr[ôo]nico ou inform[áa]tico|rede de computadores|redes sociais|correio eletr[ôo]nico", r"internet|online|on-line|aplicativo|whatsapp|\bpix\b|\bsite\b|e-mail|rede social|golpe (?:virtual|digital)|link falso"),
        (r"energia el[ée]trica", r"energia el[ée]trica|gato de energia|liga[çc][ãa]o clandestina"),
        (r"semovente", r"\bgado\b|\bbois?\b|vacas?\b|bovino|cavalos?\b|semovente|porcos?\b"),
        (r"explosivo ou de artefato an[áa]logo", r"explos|dinamite"),
        (r"entidade de direito p[úu]blico|patrim[ôo]nio da Uni[ãa]o|instituto de economia popular", r"prefeitura|\binss\b|[óo]rg[ãa]o p[úu]blico|patrim[ôo]nio p[úu]blico|autarquia|previd[êe]ncia"),
        (r"gravidez|gestante|acelera[çc][ãa]o de parto|aborto", r"gr[áa]vida|gestante|aborto|parto"),
        (r"debilidade permanente|perda ou inutiliza[çc][ãa]o|deformidade permanente", r"debilidade permanente|perdeu (?:a vis[ãa]o|o movimento|um dedo|a m[ãa]o|um olho)|cicatriz|deformidade"),
        (r"ocupa[çc][õo]es habituais, por mais de trinta dias", r"(?:mais de |por )(?:3\d|[4-9]\d) dias|afastad\w+ (?:do trabalho|das atividades)"),
        (r"presen[çc]a f[íi]sica ou virtual de descendente ou de ascendente", r"na (?:frente|presen[çc]a) d[aeo]s? (?:filh[oa]s?|pais|m[ãa]e|pai|av[óô]s?)|os filhos (?:viram|assistiram|presenciaram)"),
        (r"medidas protetivas de urg[êe]ncia", r"medida(?:s)? protetiva"),
        (r"ascendente, descendente, irm[ãa]o, c[ôo]njuge|rela[çc][õo]es dom[ée]sticas", r"viol[êe]ncia dom[ée]stica|esposa|marido|companheir|filh[oa]|\bpai\b|\bm[ãa]e\b|irm[ãa]o?"),
    )
    for exigido in [bool(resto and resto[0])]
)

# Indícios fortes de cada crime, com peso. Pesam mais que a semelhança de palavras (BM25), que
# fica como desempate e para os crimes sem indício aqui. Crimes "mais específicos" pesam mais:
# "comprou sabendo que era produto de furto" também fala de furto, mas é receptação; assalto
# com morte também fala de morte, mas é roubo (latrocínio).
INDICIOS_DE_CRIMES: tuple[tuple[str, float, re.Pattern], ...] = tuple(
    (rotulo, peso, _re(padrao))
    for rotulo, peso, padrao in (
        ("CP.art155", 20, r"subtrai|furt(?:ou|ar|o\b|ad)|surrupi|levou (?:escondido|sem que)|pegou (?:escondido|sem pagar)"),
        ("CP.art157", 32, r"assalt|roub(?:ou|ar|o\b|ad)|rend(?:eu|eram|ido)|anunci\w+ o assalto|mediante (?:grave )?amea[çc]a[^.;]{0,80}(?:subtrai|levou|levaram)|(?:com|armad\w*) (?:uma |um )?(?:faca|rev[óo]lver|pistola|arma)[^.;]{0,80}(?:levou|levaram|subtraiu|subtra[íi]ram)"),
        ("CP.art121", 26, r"\bmat(?:a|am|ou|ar|aram|ando|ado|ada)\b|assassin|homic[íi]di|tirou a vida|atropel\w+[^.;]{0,60}(?:morreu|faleceu|morte)"),
        # feminicídio (art. 121-A, crime autônomo desde a Lei 14.994/2024): morte de mulher no contexto
        # de violência doméstica e familiar (esposa, companheira, namorada, ex)
        (
            "CP.art121-A",
            44,
            rf"feminic[íi]di|\b(?:mat(?:a|am|ou|ar|aram|ando)|assassin\w*|esfaque\w*)\b[^.;]{{0,60}}{_PARCEIRA}"
            rf"|{_PARCEIRA}[^.;]{{0,60}}\b(?:morreu|morta|faleceu|assassinad)",
        ),
        ("CP.art129", 22, r"agred|les[ãa]o corporal|\bsocos?\b|chutes?|espanc|machuc|feriu|hematoma|fratur"),
        ("CP.art171", 26, r"engan|golpe|estelionat|fraude|se passou por|induz\w* (?:a v[íi]tima )?em erro|link falso|falso (?:estorno|boleto|leil[ãa]o)|vantagem il[íi]cita"),
        ("CP.art180", 38, r"recepta|produto de (?:furto|roubo|crime)|sabendo (?:que|ser)[^.;]{0,40}(?:roubad|furtad|produto de|origem il[íi]cita)|pe[çc]as de (?:carros|ve[íi]culos) roubad"),
        ("CP.art147", 24, r"amea[çc]\w*[^.;]{0,40}(?:de morte|mat[áa]-l|de mal)|amea[çc]ou|(?:disse|falou|afirmou|avisou|prometeu|escreveu|gritou|mandou)[^.;]{0,60}\b(?:vai|vou|iria|ia|irá)\s+(?:matar|mat[áa]-l|machucar|bater|pegar|acabar com|quebrar)"),
        ("CP.art168", 30, r"apropri\w+ (?:d[ao]s? |de )?(?:quantia|dinheiro|valor|bem|bens)|apropriou-se|apropria[çc][ãa]o ind[ée]bita|n[ãa]o devolveu[^.;]{0,40}(?:empresa|dono|propriet)"),
        ("CP.art213", 34, r"estupr|conjun[çc][ãa]o carnal|ato libidinoso"),
        ("CP.art217-A", 40, r"(?:conjun[çc][ãa]o carnal|ato libidinoso|abus\w+ sexual)[^.]{0,120}(?:menor de 14|crian[çc]a|\b(?:[1-9]|1[0-3]) anos)"),
        ("CP.art158", 30, r"extors|constrang\w+[^.;]{0,80}(?:a pagar|a entregar|vantagem econ[ôo]mica)|exig\w+ (?:dinheiro|pagamento)[^.;]{0,40}amea[çc]"),
        ("CP.art159", 45, r"sequestr\w+[^.;]{0,120}resgate|(?:pedi|exigi|cobr)\w*[^.;]{0,20}resgate"),
        ("CP.art163", 22, r"danific|destru(?:iu|[íi]ram)|quebrou|depred|pichou|pichado"),
        ("CP.art312", 32, r"pecul|desvi\w+[^.;]{0,60}(?:dinheiro|verba|bens?|recursos?) p[úu]blic|servidor[^.;]{0,80}(?:desviou|apropriou)"),
        ("CP.art317", 32, r"propina|solicitou (?:vantagem|dinheiro)|recebeu (?:vantagem indevida|propina)|corrup[çc][ãa]o passiva"),
        ("CP.art333", 32, r"ofereceu (?:propina|dinheiro|vantagem)[^.;]{0,40}(?:policial|fiscal|servidor|funcion[áa]rio|agente)|corrup[çc][ãa]o ativa"),
        ("CP.art148", 30, r"c[áa]rcere privado|privou[^.;]{0,60}liberdade|mant\w+[^.;]{0,20}trancad|\bsequestrar\b"),
        ("CP.art150", 24, r"invadiu (?:a )?(?:casa|resid[êe]ncia|apartamento)|viola[çc][ãa]o de domic[íi]lio|entrou[^.;]{0,40}sem (?:autoriza|permiss)"),
        ("CP.art138", 26, r"cal[úu]ni|imputou[^.;]{0,40}crime"),
        ("CP.art139", 26, r"difam"),
        ("CP.art140", 26, r"injuri|xingou|ofendeu a (?:honra|dignidade)"),
        ("CP.art288", 30, r"associa[çc][ãa]o criminosa|quadrilha|associaram-se"),
        ("CP.art297", 28, r"falsific\w+[^.;]{0,40}documento p[úu]blico|documento p[úu]blico falso|(?:rg|cnh|carteira de identidade) falsa"),
        ("CP.art304", 30, r"(?:usou|apresentou|fez uso de)[^.;]{0,40}(?:documento|rg|cnh|carteira)[^.;]{0,20}fals"),
        ("CP.art329", 28, r"resist\w+ [àa] pris[ãa]o|op[ôo]s-se[^.;]{0,40}(?:mediante viol[êe]ncia|amea[çc]a)"),
        ("CP.art330", 24, r"desobedec|descumpriu (?:a )?ordem"),
        ("CP.art331", 30, r"desacat|xingou (?:o|os) (?:policia|agente|servidor)"),
        ("CP.art184", 28, r"pirat|viola[çc][ãa]o de direito autoral"),
        ("CP.art146", 20, r"constrangimento ilegal"),
    )
)

# bis in idem: agravante que repete o que já qualificou ou aumentou a pena não se aplica de novo
CONFLITOS_DE_AGRAVANTES: dict[str, re.Pattern] = {
    "motivo_futil_ou_torpe": _re(r"f[úu]til|torpe|paga ou promessa"),
    "meio_cruel": _re(r"veneno|fogo|explosivo|tortura|cruel|asfixia"),
    "traicao_emboscada": _re(r"trai[çc][ãa]o|emboscada|dissimula[çc][ãa]o|dificulte ou torne imposs[íi]vel a defesa"),
    "vitima_vulneravel": _re(r"idoso|maior de 60|60 \(sessenta\) anos|menor de 14|crian[çc]a|vulner[áa]vel|gestante|gravidez"),
    "relacoes_domesticas": _re(r"sexo feminino|contra a mulher|rela[çc][õo]es dom[ée]sticas|coabita"),
    "contra_familiar": _re(r"ascendente, descendente, irm[ãa]o|c[ôo]njuge"),
    "facilitar_outro_crime": _re(r"assegurar a execu[çc][ãa]o|impunidade ou vantagem de outro crime"),
    "mediante_paga": _re(r"paga ou promessa de recompensa"),
}

# agravantes que já são elementares do tipo: aplicá-las seria bis in idem (crime -> códigos)
ELEMENTARES_DO_TIPO: dict[str, tuple[str, ...]] = {
    # no feminicídio, a violência doméstica e familiar contra a mulher é a própria razão do crime
    "CP.art121-A": ("relacoes_domesticas", "contra_familiar"),
}

# causas que não se aplicam junto com certas formas do crime: (causa, prefixo da forma, motivo)
INCOMPATIBILIDADES: tuple[tuple[str, str, str], ...] = (
    (
        "CP.art155.§1",
        "CP.art155.§4",
        "o aumento do repouso noturno (§ 1º) não se aplica ao furto qualificado (STJ, Tema 1.087)",
    ),
)

# o crime já tem violência ou grave ameaça no tipo (não cabe arrependimento posterior, art. 16)
COM_VIOLENCIA = _re(r"viol[êe]ncia|grave amea[çc]a|matar alg|ofender a integridade")
