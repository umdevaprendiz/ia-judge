// Funções compartilhadas pelas páginas: chamadas à API, formatação e exibição do resultado.
// Todo texto vindo do usuário ou da API entra na página via textContent (nunca innerHTML).

export const CIRCUNSTANCIAS = {
  culpabilidade: "Culpabilidade",
  antecedentes: "Antecedentes",
  conduta_social: "Conduta social",
  personalidade: "Personalidade",
  motivos: "Motivos",
  circunstancias: "Circunstâncias",
  consequencias: "Consequências",
  comportamento_da_vitima: "Comportamento da vítima",
};

export const ESTRATEGIAS = {
  fracao_do_intervalo: "fração do intervalo entre mínimo e máximo",
  fracao_do_minimo: "fração da pena mínima",
};

export const COMPOSICOES = {
  cascata: "em cascata (cada fração sobre a pena já modificada)",
  sobre_pena_intermediaria: "sobre a pena intermediária (efeitos somados)",
};

const NOMES_CAMPOS = {
  faixa: "Faixa",
  origem: "dispositivo",
  minimo: "pena mínima",
  maximo: "pena máxima",
  anos: "anos",
  meses: "meses",
  dias: "dias",
  circunstancias_desfavoraveis: "Circunstância judicial",
  agravantes_atenuantes: "Agravante/atenuante",
  causas: "Causa",
  codigo: "nome",
  dispositivo: "dispositivo",
  direcao: "tipo",
  preponderante: "preponderante",
  fracao_min: "fração mínima",
  fracao_max: "fração máxima",
  fracao_escolhida: "fração escolhida",
  justificativa: "justificativa",
  estrategia: "Critério do quantum",
  tipo: "tipo",
  fracao: "fração",
  composicao: "Composição das causas",
  entrada: "Caso",
  resposta: "Sua resposta",
  pena_base: "pena-base",
  pena_intermediaria: "pena intermediária",
  pena_definitiva: "pena definitiva",
  descricao: "Descrição",
  consentimento: "Concordância",
};

export class ApiError extends Error {
  constructor(mensagens) {
    super(mensagens.join("\n"));
    this.mensagens = mensagens;
  }
}

/** GET sem corpo; POST com JSON quando há corpo; ou o método indicado (ex.: DELETE).
 *  Erros viram ApiError com mensagens legíveis. Respostas sem conteúdo (204) devolvem null. */
export async function chamarApi(caminho, corpo, metodo) {
  const opcoes =
    corpo === undefined
      ? { method: metodo || "GET" }
      : { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    throw new ApiError(["Não foi possível falar com o servidor. Verifique a conexão e tente de novo."]);
  }
  if (resposta.status === 204) return null;
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ApiError(mensagensDeErro(resposta.status, dados));
  return dados;
}

function mensagensDeErro(status, dados) {
  const detalhe = dados && dados.detail;
  if (Array.isArray(detalhe)) {
    return detalhe.map((erro) => (erro.campo ? `${descreverCampo(erro.campo)}: ${erro.mensagem}` : erro.mensagem));
  }
  if (typeof detalhe === "string") return [detalhe];
  if (status >= 500) return ["O servidor teve um problema. Tente de novo em instantes."];
  return [`Erro ${status} ao falar com o servidor.`];
}

/** "causas.0.fracao_min" -> "Causa 1 · fração mínima" */
export function descreverCampo(caminho) {
  return caminho
    .split(".")
    .map((parte) => (/^\d+$/.test(parte) ? String(Number(parte) + 1) : NOMES_CAMPOS[parte] || parte))
    .join(" · ")
    .replace(/ · (\d+)/g, " $1");
}

/** Cria um elemento. Filhos em texto viram nós de texto (seguro contra HTML injetado). */
export function el(tag, propriedades = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [chave, valor] of Object.entries(propriedades)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (chave === "classe") elemento.className = valor;
    else if (chave === "texto") elemento.textContent = valor;
    else if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
    else elemento.setAttribute(chave, valor === true ? "" : valor);
  }
  for (const filho of filhos.flat()) {
    if (filho === undefined || filho === null || filho === false) continue;
    elemento.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return elemento;
}

/** {anos, meses, dias} -> "1 ano, 4 meses, 16 dias" (mesmo formato do motor). */
export function textoPena({ anos = 0, meses = 0, dias = 0 } = {}) {
  const partes = [];
  if (anos) partes.push(`${anos} ${anos === 1 ? "ano" : "anos"}`);
  if (meses) partes.push(`${meses} ${meses === 1 ? "mês" : "meses"}`);
  if (dias || partes.length === 0) partes.push(`${dias} ${dias === 1 ? "dia" : "dias"}`);
  return partes.join(", ");
}

/** "repouso_noturno" -> "repouso noturno" */
export function nomeLegivel(codigo) {
  return String(codigo || "").replaceAll("_", " ");
}

/** Lê um grupo anos/meses/dias. Devolve null se os três estiverem vazios. */
export function lerPena(grupo) {
  const campos = ["anos", "meses", "dias"].map((nome) => grupo.querySelector(`[name="${nome}"]`));
  if (campos.every((campo) => campo.value.trim() === "")) return null;
  return Object.fromEntries(campos.map((campo) => [campo.name, Number(campo.value || 0)]));
}

export function preencherPena(grupo, pena = {}) {
  for (const nome of ["anos", "meses", "dias"]) {
    grupo.querySelector(`[name="${nome}"]`).value = pena[nome] ? String(pena[nome]) : "";
  }
}

export function mostrarErros(caixa, erro) {
  const mensagens = erro instanceof ApiError ? erro.mensagens : [String(erro && erro.message ? erro.message : erro)];
  caixa.replaceChildren(
    el("p", { texto: mensagens.length > 1 ? "Corrija estes pontos:" : "Não foi possível concluir:" }),
    el("ul", {}, mensagens.map((mensagem) => el("li", { texto: mensagem })))
  );
  caixa.hidden = false;
  caixa.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function esconder(...elementos) {
  for (const elemento of elementos) elemento.hidden = true;
}

/** "CP.art155.§4.IV" -> "CP, art. 155, § 4º, IV" */
export function formatarRotulo(rotulo) {
  return String(rotulo)
    .split(".")
    .map((parte, posicao) => {
      if (posicao === 0) return parte;
      const artigo = parte.match(/^art(\d+)(-[A-Z]+)?$/);
      if (artigo) return `art. ${artigo[1]}${Number(artigo[1]) < 10 ? "º" : ""}${artigo[2] || ""}`;
      const paragrafo = parte.match(/^§(\d+)(-[A-Z]+)?$/);
      if (paragrafo) return `§ ${paragrafo[1]}${Number(paragrafo[1]) < 10 ? "º" : ""}${paragrafo[2] || ""}`;
      return parte.replaceAll("_", " ");
    })
    .join(", ");
}

/** Um artigo da base de legislação: título, trecho (opcional), texto completo e a fonte. */
export function cartaoDeDispositivo(dispositivo, trecho) {
  const fonte = dispositivo.fonte;
  const titulo = [formatarRotulo(dispositivo.rotulo), dispositivo.epigrafe].filter(Boolean).join(" — ");
  return el(
    "article",
    { classe: "cartao dispositivo" },
    el("h3", { classe: "dispositivo__titulo", texto: titulo }),
    el("p", { classe: "dispositivo__meta", texto: [dispositivo.nome_lei, ...dispositivo.estrutura.slice(-2)].join(" · ") }),
    trecho && el("p", { classe: "dispositivo__trecho", texto: trecho }),
    el("details", {}, el("summary", { texto: "Ver o artigo completo" }), el("pre", { classe: "dispositivo__texto", texto: dispositivo.texto })),
    el(
      "p",
      { classe: `dispositivo__fonte${fonte.desatualizada ? " dispositivo__fonte--antiga" : ""}` },
      `Fonte: ${fonte.titulo}, atualizada até ${fonte.atualizado_ate}.`,
      fonte.desatualizada ? " Edição antiga: confira o texto vigente no site do Planalto." : ""
    )
  );
}

function secaoFontesCitadas(fontes) {
  if (!fontes || !fontes.length) return null;
  return el(
    "section",
    { classe: "fontes-citadas" },
    el("h3", { texto: "Textos da lei citados" }),
    el("p", { classe: "ajuda", texto: "Cada dispositivo usado no cálculo, conferido na base de legislação do agente." }),
    fontes.map((citacao) =>
      citacao.encontrado
        ? el(
            "details",
            { classe: "detalhes" },
            el("summary", {
              texto: `${formatarRotulo(citacao.rotulo)}${citacao.dispositivo.epigrafe ? ` — ${citacao.dispositivo.epigrafe}` : ""} (${citacao.dispositivo.nome_lei})`,
            }),
            el("pre", { classe: "dispositivo__texto", texto: citacao.texto }),
            !citacao.parte_encontrada && el("p", { classe: "ajuda", texto: "A parte citada não foi localizada; segue o artigo inteiro." }),
            el("p", { classe: "dispositivo__fonte", texto: `Fonte: ${citacao.dispositivo.fonte.titulo}.` })
          )
        : el("p", { classe: "dispositivo__ausente", texto: `${formatarRotulo(citacao.rotulo)}: não está na base de legislação.` })
    )
  );
}

function cartaoPena(rotulo, pena, destaque) {
  return el(
    "div",
    { classe: `pena${destaque ? " pena--destaque" : ""}` },
    el("span", { classe: "pena__rotulo", texto: rotulo }),
    el("strong", { classe: "pena__valor", texto: pena.texto }),
    el("span", { classe: "pena__dias", texto: `${pena.total_dias} dias` })
  );
}

function listaDePassos(passos) {
  return el(
    "ol",
    { classe: "passos" },
    passos.map((passo) =>
      el(
        "li",
        { classe: "passo" },
        el("p", { classe: "passo__motivo", texto: passo.motivo }),
        el("p", { classe: "passo__meta", texto: `${passo.regra} · ${passo.dispositivo}` }),
        el("p", { classe: "passo__valores" }, passo.valor_antes.texto, el("span", { "aria-hidden": "true", texto: " → " }), el("span", { classe: "visualmente-oculto", texto: " passa a " }), el("strong", { texto: passo.valor_depois.texto }))
      )
    )
  );
}

function agruparPorFase(passos) {
  const grupos = new Map();
  for (const passo of passos) {
    if (!grupos.has(passo.fase)) grupos.set(passo.fase, []);
    grupos.get(passo.fase).push(passo);
  }
  return grupos;
}

/** Monta a exibição completa de um resultado da API (/dosimetria/calcular ou o gabarito). */
export function renderizarResultado(resultado, { titulo = "Resultado" } = {}) {
  const fragmento = document.createDocumentFragment();
  const faixa = resultado.faixa_aplicada;
  const alternativa = resultado.alternativa_art68;

  fragmento.append(
    el("h2", { texto: titulo }),
    el("p", {
      classe: "resultado__contexto",
      texto: `Faixa ${faixa.origem}: de ${faixa.minimo.texto} a ${faixa.maximo.texto}. Quantum: ${resultado.criterio_quantum}. Causas ${COMPOSICOES[resultado.composicao] || resultado.composicao}.`,
    }),
    el(
      "div",
      { classe: "penas" },
      cartaoPena("Pena-base", resultado.pena_base),
      cartaoPena("Pena intermediária", resultado.pena_intermediaria),
      cartaoPena("Pena definitiva", resultado.pena_definitiva, true),
      alternativa && cartaoPena("Opção do art. 68, parágrafo único", alternativa.pena_definitiva)
    )
  );

  if (resultado.alertas.length) {
    fragmento.append(
      el(
        "div",
        { classe: "aviso aviso--alerta" },
        el("h3", { texto: "Alertas" }),
        el("ul", {}, resultado.alertas.map((alerta) => el("li", { texto: alerta })))
      )
    );
  }

  const passoAPasso = el("section", { classe: "passo-a-passo" }, el("h3", { texto: "Passo a passo" }));
  for (const [fase, passos] of agruparPorFase(resultado.passos)) {
    passoAPasso.append(el("h4", { texto: fase }), listaDePassos(passos));
  }
  if (alternativa) {
    passoAPasso.append(
      el(
        "details",
        { classe: "detalhes" },
        el("summary", { texto: `Opção do art. 68, parágrafo único (${alternativa.descricao})` }),
        listaDePassos(alternativa.passos)
      )
    );
  }
  fragmento.append(passoAPasso);

  const texto = el("pre", { classe: "fundamentacao", texto: resultado.fundamentacao });
  const botaoCopiar = el("button", {
    type: "button",
    classe: "botao botao--pequeno",
    texto: "Copiar texto",
    onclick: async () => {
      try {
        await navigator.clipboard.writeText(resultado.fundamentacao);
        botaoCopiar.textContent = "Copiado!";
      } catch {
        botaoCopiar.textContent = "Não foi possível copiar";
      }
      setTimeout(() => (botaoCopiar.textContent = "Copiar texto"), 2000);
    },
  });
  fragmento.append(
    el("section", { classe: "fundamentacao-bloco" }, el("div", { classe: "linha-titulo" }, el("h3", { texto: "Fundamentação" }), botaoCopiar), texto)
  );
  const citadas = secaoFontesCitadas(resultado.fontes_citadas);
  if (citadas) fragmento.append(citadas);
  return fragmento;
}
