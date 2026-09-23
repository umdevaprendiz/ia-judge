// Página Calcular: monta a entrada a partir do formulário e mostra o resultado da API.
import {
  CIRCUNSTANCIAS,
  chamarApi,
  el,
  esconder,
  lerPena,
  mostrarErros,
  preencherPena,
  renderizarResultado,
} from "./comum.js";

const EXEMPLO_INICIAL = "construido-01";

const formulario = document.getElementById("formulario");
const seletorExemplo = document.getElementById("exemplo");
const listaAgravantes = document.getElementById("agravantes");
const listaCausas = document.getElementById("causas");
const caixaErros = document.getElementById("erros");
const areaResultado = document.getElementById("resultado");

// ---------- montagem do formulário ----------

document.getElementById("circunstancias").append(
  ...Object.entries(CIRCUNSTANCIAS).map(([valor, rotulo]) =>
    el("label", { classe: "caixa" }, el("input", { type: "checkbox", name: "circunstancia", value: valor }), ` ${rotulo}`)
  )
);

function novaLinha(tipo, dados = {}) {
  const modelo = document.getElementById(`modelo-${tipo}`);
  const linha = modelo.content.firstElementChild.cloneNode(true);
  for (const campo of linha.querySelectorAll("input, select")) {
    const valor = dados[campo.name];
    if (campo.type === "checkbox") campo.checked = Boolean(valor);
    else if (valor !== undefined && valor !== null) campo.value = String(valor);
  }
  (tipo === "agravante" ? listaAgravantes : listaCausas).append(linha);
  return linha;
}

formulario.addEventListener("click", (evento) => {
  const adicionar = evento.target.closest("[data-adicionar]");
  if (adicionar) {
    novaLinha(adicionar.dataset.adicionar).querySelector("input, select").focus();
    return;
  }
  const remover = evento.target.closest("[data-remover]");
  if (remover) remover.closest(".linha").remove();
});

function limparFormulario() {
  formulario.reset();
  listaAgravantes.replaceChildren();
  listaCausas.replaceChildren();
  esconder(caixaErros, areaResultado);
}

function preencherFormulario(entrada) {
  limparFormulario();
  // "origem" também é o nome do campo "Previsão" das causas; por isso a faixa usa faixa_origem
  formulario.elements.faixa_origem.value = entrada.faixa.origem;
  preencherPena(formulario.querySelector('[data-pena="minimo"]'), entrada.faixa.minimo);
  preencherPena(formulario.querySelector('[data-pena="maximo"]'), entrada.faixa.maximo);
  for (const caixa of formulario.querySelectorAll('[name="circunstancia"]')) {
    caixa.checked = entrada.circunstancias_desfavoraveis.includes(caixa.value);
  }
  formulario.elements.estrategia_tipo.value = entrada.estrategia.tipo;
  formulario.elements.estrategia_fracao.value = entrada.estrategia.fracao;
  formulario.elements.composicao.value = entrada.composicao;
  for (const item of entrada.agravantes_atenuantes) novaLinha("agravante", item);
  for (const item of entrada.causas) novaLinha("causa", item);
}

// ---------- leitura do formulário ----------

function valoresDaLinha(linha) {
  const dados = {};
  for (const campo of linha.querySelectorAll("input, select")) {
    if (campo.type === "checkbox") dados[campo.name] = campo.checked;
    else if (campo.value.trim() !== "") dados[campo.name] = campo.value.trim();
  }
  return dados;
}

function lerFormulario() {
  const campos = formulario.elements;
  return {
    faixa: {
      origem: campos.faixa_origem.value.trim(),
      minimo: lerPena(formulario.querySelector('[data-pena="minimo"]')) || {},
      maximo: lerPena(formulario.querySelector('[data-pena="maximo"]')) || {},
    },
    circunstancias_desfavoraveis: [...formulario.querySelectorAll('[name="circunstancia"]:checked')].map((c) => c.value),
    agravantes_atenuantes: [...listaAgravantes.children].map(valoresDaLinha),
    causas: [...listaCausas.children].map(valoresDaLinha),
    estrategia: { tipo: campos.estrategia_tipo.value, fracao: campos.estrategia_fracao.value.trim() },
    composicao: campos.composicao.value,
  };
}

// ---------- ações ----------

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconder(caixaErros);
  const botao = formulario.querySelector('[type="submit"]');
  botao.disabled = true;
  botao.textContent = "Calculando…";
  try {
    const resultado = await chamarApi("/dosimetria/calcular", lerFormulario());
    areaResultado.replaceChildren(renderizarResultado(resultado));
    areaResultado.hidden = false;
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (erro) {
    esconder(areaResultado);
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
    botao.textContent = "Calcular";
  }
});

document.getElementById("limpar").addEventListener("click", () => {
  limparFormulario();
  seletorExemplo.value = "";
});

async function carregarExemplo(id) {
  esconder(caixaErros);
  try {
    const exemplo = await chamarApi(`/exemplos/${encodeURIComponent(id)}`);
    preencherFormulario(exemplo.entrada);
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  }
}

seletorExemplo.addEventListener("change", () => {
  if (seletorExemplo.value) carregarExemplo(seletorExemplo.value);
});

async function iniciar() {
  try {
    const exemplos = await chamarApi("/exemplos");
    seletorExemplo.replaceChildren(
      el("option", { value: "", texto: "Escolha um exemplo…" }),
      ...exemplos.map((exemplo) => el("option", { value: exemplo.id, texto: exemplo.descricao }))
    );
    if (exemplos.some((exemplo) => exemplo.id === EXEMPLO_INICIAL)) {
      seletorExemplo.value = EXEMPLO_INICIAL;
      await carregarExemplo(EXEMPLO_INICIAL);
    }
  } catch (erro) {
    seletorExemplo.replaceChildren(el("option", { value: "", texto: "Exemplos indisponíveis" }));
    mostrarErros(caixaErros, erro);
  }
}

iniciar();
