// Página Analisar caso: o agente analisa a descrição, o estudante confere as sugestões e calcula.
// Todo texto entra na página via textContent (nunca innerHTML).
import { ApiError, chamarApi, el, esconder, formatarRotulo, mostrarErros, renderizarResultado } from "./comum.js";

const MINIMO = 50;

const formulario = document.getElementById("formulario");
const campoDescricao = document.getElementById("descricao");
const caixaErros = document.getElementById("erros");
const secaoAnalise = document.getElementById("analise");
const caixaAvisos = document.getElementById("avisos-agente");
const seletorCrime = document.getElementById("crime");
const detalhesCrime = document.getElementById("crime-detalhes");
const caixaAusentes = document.getElementById("ausentes");
const formDosimetria = document.getElementById("form-dosimetria");
const caixaAlertas = document.getElementById("alertas-agente");
const areaResultado = document.getElementById("resultado-agente");

// a descrição anonimizada da última análise: é com ela que as sugestões de outro crime são refeitas
let descricaoAnalisada = "";
let sugeridos = [];
let todosOsCrimes = null;

const TEXTO_DIRECAO = { aumento: "aumento", diminuicao: "diminuição" };

function indicio(evidencia) {
  return evidencia ? el("p", { classe: "opcao__indicio" }, "Indício no caso: ", el("q", { texto: evidencia })) : null;
}

/** Uma caixa de marcar com título, detalhe (fração ou pena), texto da lei e o indício que a motivou. */
function opcao(nome, valor, item, detalhe) {
  return el(
    "label",
    { classe: `opcao${item.sugerido ? " opcao--sugerida" : ""}` },
    el("input", { type: "checkbox", name: nome, value: valor, checked: item.sugerido }),
    el(
      "span",
      { classe: "opcao__corpo" },
      el("span", { classe: "opcao__titulo" }, item.titulo, item.sugerido ? el("span", { classe: "selo-sugerido", texto: "sugerido" }) : null),
      detalhe ? el("span", { classe: "opcao__detalhe", texto: detalhe }) : null,
      item.texto ? el("span", { classe: "opcao__texto", texto: item.texto }) : null,
      item.rotulo ? el("span", { classe: "opcao__rotulo", texto: formatarRotulo(item.rotulo) }) : null,
      indicio(item.evidencia),
      item.observacao ? el("span", { classe: "opcao__observacao", texto: item.observacao }) : null
    )
  );
}

function preencherGrupo(id, itens, fabricar, vazio, { recolher = true } = {}) {
  const grupo = document.getElementById(id);
  if (!itens.length) {
    grupo.replaceChildren(el("p", { classe: "ajuda", texto: vazio }));
    return;
  }
  // à mostra, o que o agente sugeriu; o resto fica em "Outras opções", para a lista não ficar enorme
  const sugeridas = recolher ? itens.filter((item) => item.sugerido) : itens;
  const outras = recolher ? itens.filter((item) => !item.sugerido) : [];
  // replaceChildren escreveria "null" como texto: só entram os elementos que existem
  const filhos = [
    ...sugeridas.map(fabricar),
    recolher && !sugeridas.length ? el("p", { classe: "ajuda", texto: "Nada sugerido pelo agente para esta fase." }) : null,
    outras.length
      ? el("details", { classe: "outras-opcoes" }, el("summary", { texto: `Outras opções (${outras.length})` }), el("div", { classe: "opcoes" }, outras.map(fabricar)))
      : null,
  ];
  grupo.replaceChildren(...filhos.filter(Boolean));
}

function renderizarEstrutura(estrutura) {
  const crime = estrutura.crime;
  detalhesCrime.replaceChildren(
    el("p", {}, el("strong", { texto: "Pena do caput: " }), crime.pena.texto, ` (${formatarRotulo(crime.rotulo)}, ${crime.nome_lei})`),
    el("p", { classe: "ajuda", texto: crime.caput })
  );
  preencherGrupo("grupo-formas", estrutura.formas, (f) => opcao("forma", f.rotulo, f, `pena: ${f.pena.texto}`), "Este crime não tem formas com pena própria.");
  preencherGrupo("grupo-circunstancias", estrutura.circunstancias_judiciais, (c) => opcao("circunstancia", c.codigo, c), "", { recolher: false });
  preencherGrupo("grupo-agravantes", estrutura.agravantes, (a) => opcao("agravante", a.codigo, a, a.preponderante ? "preponderante (art. 67)" : ""), "");
  preencherGrupo("grupo-atenuantes", estrutura.atenuantes, (a) => opcao("atenuante", a.codigo, a, a.preponderante ? "preponderante (art. 67)" : ""), "");
  preencherGrupo(
    "grupo-causas",
    estrutura.causas,
    (c) => {
      const fracao = c.fracao_min === c.fracao_max ? c.fracao_min : `${c.fracao_min} a ${c.fracao_max}`;
      const origem = c.origem === "parte_geral" ? "parte geral" : "deste crime";
      return opcao("causa", c.rotulo, c, `${TEXTO_DIRECAO[c.direcao]} de ${fracao} (${origem})`);
    },
    "Nenhuma causa de aumento ou de diminuição disponível."
  );
  esconder(caixaAlertas, areaResultado);
}

function opcoesDeCrime(crimes, sugeridosAgora) {
  const opcoesSugeridas = sugeridosAgora.map((c, posicao) =>
    el("option", { value: c.rotulo, texto: `${c.nome} (${formatarRotulo(c.rotulo)})${posicao === 0 ? " · mais provável" : " · sugerido"}` })
  );
  const grupos = new Map();
  for (const crime of crimes || []) {
    if (sugeridosAgora.some((s) => s.rotulo === crime.rotulo)) continue;
    if (!grupos.has(crime.nome_lei)) grupos.set(crime.nome_lei, []);
    grupos.get(crime.nome_lei).push(el("option", { value: crime.rotulo, texto: `${crime.nome} (${formatarRotulo(crime.rotulo)})` }));
  }
  return [
    el("optgroup", { label: "Sugeridos pelo agente" }, opcoesSugeridas),
    ...[...grupos].map(([lei, opcoes]) => el("optgroup", { label: lei }, opcoes)),
  ];
}

function renderizarAnalise(analise) {
  caixaAvisos.replaceChildren(el("ul", {}, analise.avisos.map((aviso) => el("li", { texto: aviso }))));
  sugeridos = analise.crimes;
  seletorCrime.replaceChildren(...opcoesDeCrime(todosOsCrimes, sugeridos));
  if (sugeridos.length) seletorCrime.value = sugeridos[0].rotulo;
  if (analise.informacoes_ausentes.length) {
    caixaAusentes.replaceChildren(
      el("p", { texto: "A descrição não diz (confira, porque muda a pena):" }),
      el("ul", {}, analise.informacoes_ausentes.map((item) => el("li", { texto: item })))
    );
    caixaAusentes.hidden = false;
  } else {
    esconder(caixaAusentes);
  }
  if (analise.estrutura) {
    renderizarEstrutura(analise.estrutura);
    mostrarEvidenciasDoCrime(sugeridos[0]);
    formDosimetria.hidden = false;
  } else {
    formDosimetria.hidden = true;
    detalhesCrime.replaceChildren();
  }
  secaoAnalise.hidden = false;
  secaoAnalise.scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarEvidenciasDoCrime(crime) {
  if (!crime || !crime.evidencias.length) return;
  detalhesCrime.append(
    el(
      "div",
      { classe: "opcao__indicio" },
      crime.citado_na_descricao ? "O artigo foi citado na descrição. " : "Por que este crime: ",
      ...crime.evidencias.map((frase) => el("q", { texto: frase }))
    )
  );
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconder(caixaErros);
  const descricao = campoDescricao.value;
  if (descricao.trim().length < MINIMO) {
    mostrarErros(caixaErros, new ApiError([`A descrição precisa ter pelo menos ${MINIMO} caracteres.`]));
    return;
  }
  const botao = document.getElementById("analisar-caso");
  botao.disabled = true;
  botao.textContent = "Analisando…";
  try {
    const [analise] = await Promise.all([chamarApi("/agente/analisar", { descricao }), carregarCrimes()]);
    descricaoAnalisada = analise.descricao_anonimizada;
    renderizarAnalise(analise);
  } catch (erro) {
    esconder(secaoAnalise);
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
    botao.textContent = "Analisar o caso";
  }
});

async function carregarCrimes() {
  if (todosOsCrimes) return;
  try {
    todosOsCrimes = await chamarApi("/agente/crimes");
  } catch {
    todosOsCrimes = []; // sem a lista completa, os sugeridos continuam disponíveis
  }
}

seletorCrime.addEventListener("change", async () => {
  esconder(caixaErros);
  try {
    const estrutura = await chamarApi("/agente/estrutura", { crime: seletorCrime.value, descricao: descricaoAnalisada });
    renderizarEstrutura(estrutura);
    mostrarEvidenciasDoCrime(sugeridos.find((c) => c.rotulo === seletorCrime.value));
    formDosimetria.hidden = false;
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  }
});

const marcados = (nome) => [...formDosimetria.querySelectorAll(`[name="${nome}"]:checked`)].map((caixa) => caixa.value);

formDosimetria.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconder(caixaErros, caixaAlertas);
  const botao = document.getElementById("calcular-pena");
  botao.disabled = true;
  botao.textContent = "Calculando…";
  try {
    const resposta = await chamarApi("/agente/calcular", {
      crime: seletorCrime.value,
      formas: marcados("forma"),
      causas: marcados("causa"),
      agravantes: marcados("agravante"),
      atenuantes: marcados("atenuante"),
      circunstancias_desfavoraveis: marcados("circunstancia"),
      estrategia: { tipo: formDosimetria.elements.estrategia_tipo.value, fracao: formDosimetria.elements.estrategia_fracao.value.trim() },
      composicao: formDosimetria.elements.composicao.value,
    });
    if (resposta.alertas.length) {
      caixaAlertas.replaceChildren(
        el("h3", { texto: "Como o agente montou a dosimetria" }),
        el("ul", {}, resposta.alertas.map((alerta) => el("li", { texto: alerta })))
      );
      caixaAlertas.hidden = false;
    }
    areaResultado.replaceChildren(renderizarResultado(resposta.resultado, { titulo: "Resultado da dosimetria" }));
    areaResultado.hidden = false;
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (erro) {
    esconder(areaResultado);
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
    botao.textContent = "Calcular a pena";
  }
});

// guardar o caso só existe com o banco ligado; sem ele, a seção nem aparece
chamarApi("/saude")
  .then((saude) => {
    document.getElementById("contribuir").hidden = saude.banco !== "ligado";
  })
  .catch(() => {});
