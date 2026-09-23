// Página Analisar caso, parte opcional "Contribuir com este caso": revisão da anonimização,
// consentimento, gravação, consulta e exclusão. Só aparece com o banco ligado (veja agente.js).
// Todo texto entra na página via textContent (nunca innerHTML).
import { ApiError, chamarApi, el, esconder, mostrarErros } from "./comum.js";

const MINIMO = 50;
const MAXIMO = 20000;
const MARCADOR = /(\[(?:PESSOA \d+|CPF|CNPJ|RG|EMAIL|TELEFONE|CEP|PLACA|ENDERECO|PROCESSO)\])/;
const NOMES_TIPOS = {
  PESSOA: "nome", CPF: "CPF", CNPJ: "CNPJ", RG: "RG", EMAIL: "e-mail", TELEFONE: "telefone",
  CEP: "CEP", PLACA: "placa", ENDERECO: "endereço", PROCESSO: "número de processo",
};

const campoDescricao = document.getElementById("descricao");
const contador = document.getElementById("contador");
const caixaErros = document.getElementById("erros");
const secaoPrevia = document.getElementById("previa");
const textoAnonimizado = document.getElementById("texto-anonimizado");
const listaTrocas = document.getElementById("trocas");
const caixaConsentimento = document.getElementById("consentimento");
const botaoSalvar = document.getElementById("salvar");
const secaoSalvo = document.getElementById("salvo");
const formConsulta = document.getElementById("form-consulta");
const areaConsulta = document.getElementById("consulta");

// a descrição revisada: salvar só é permitido se o texto não mudou desde a revisão
let descricaoRevisada = null;

function atualizarContador() {
  const tamanho = campoDescricao.value.length;
  contador.textContent = `${tamanho.toLocaleString("pt-BR")} de ${MAXIMO.toLocaleString("pt-BR")} caracteres (mínimo ${MINIMO})`;
}

function invalidarPrevia() {
  descricaoRevisada = null;
  caixaConsentimento.checked = false;
  botaoSalvar.disabled = true;
  esconder(secaoPrevia);
}

function textoComMarcadores(texto) {
  // separa o texto nos marcadores e destaca cada um, sem nunca interpretar HTML
  return texto.split(MARCADOR).map((parte) => (MARCADOR.test(parte) ? el("mark", { texto: parte }) : parte));
}

function renderizarPrevia(previa) {
  textoAnonimizado.replaceChildren(...textoComMarcadores(previa.descricao_anonimizada));
  const vistas = new Map();
  for (const troca of previa.substituicoes) {
    const chave = `${troca.original}→${troca.marcador}`;
    if (!vistas.has(chave)) vistas.set(chave, troca);
  }
  listaTrocas.replaceChildren(
    vistas.size
      ? el(
          "details",
          { classe: "detalhes" },
          el("summary", { texto: `O que foi trocado (${vistas.size})` }),
          el(
            "ul",
            {},
            [...vistas.values()].map((troca) =>
              el("li", {}, el("span", { texto: `${NOMES_TIPOS[troca.tipo] || troca.tipo}: ` }), el("s", { texto: troca.original }), " → ", el("mark", { texto: troca.marcador }))
            )
          )
        )
      : el("p", { classe: "ajuda", texto: "Nenhum dado pessoal foi identificado automaticamente. Confira o texto mesmo assim." })
  );
  secaoPrevia.hidden = false;
  secaoPrevia.scrollIntoView({ behavior: "smooth", block: "start" });
}

campoDescricao.addEventListener("input", () => {
  atualizarContador();
  if (descricaoRevisada !== null && campoDescricao.value !== descricaoRevisada) invalidarPrevia();
});

caixaConsentimento.addEventListener("change", () => {
  botaoSalvar.disabled = !(caixaConsentimento.checked && descricaoRevisada === campoDescricao.value);
});

document.getElementById("revisar").addEventListener("click", async () => {
  esconder(caixaErros, secaoSalvo);
  const descricao = campoDescricao.value;
  if (descricao.trim().length < MINIMO) {
    mostrarErros(caixaErros, new ApiError([`A descrição precisa ter pelo menos ${MINIMO} caracteres.`]));
    return;
  }
  const botao = document.getElementById("revisar");
  botao.disabled = true;
  try {
    renderizarPrevia(await chamarApi("/casos/previa", { descricao }));
    descricaoRevisada = descricao;
    caixaConsentimento.checked = false;
    botaoSalvar.disabled = true;
  } catch (erro) {
    invalidarPrevia();
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
  }
});

function cartaoDoCaso(caso) {
  const data = new Date(`${caso.criado_em}Z`).toLocaleString("pt-BR");
  return [
    el("p", {}, el("strong", { texto: "Código: " }), el("code", { classe: "codigo", texto: caso.codigo })),
    el("p", { classe: "ajuda", texto: `Salvo em ${data}. Situação: ${caso.status}.` }),
    el("div", { classe: "texto-anonimizado" }, ...textoComMarcadores(caso.descricao)),
  ];
}

function botaoExcluir(codigo, aoExcluir) {
  return el("button", {
    type: "button",
    classe: "botao botao--perigo",
    texto: "Excluir este caso",
    onclick: async () => {
      if (!window.confirm("Excluir este caso definitivamente? Não dá para desfazer.")) return;
      try {
        await chamarApi(`/casos/${encodeURIComponent(codigo)}`, undefined, "DELETE");
        aoExcluir();
      } catch (erro) {
        mostrarErros(caixaErros, erro);
      }
    },
  });
}

botaoSalvar.addEventListener("click", async () => {
  esconder(caixaErros);
  if (descricaoRevisada === null || descricaoRevisada !== campoDescricao.value || !caixaConsentimento.checked) return;
  botaoSalvar.disabled = true;
  botaoSalvar.textContent = "Salvando…";
  try {
    const caso = await chamarApi("/casos", { descricao: descricaoRevisada, consentimento: true });
    // o texto original sai da página: fica só a versão anonimizada, que foi a salva
    campoDescricao.value = "";
    atualizarContador();
    invalidarPrevia();
    secaoSalvo.replaceChildren(
      el("h2", { texto: "Caso salvo" }),
      el("p", { texto: "Guarde o código abaixo: com ele você consulta ou exclui o caso." }),
      ...cartaoDoCaso(caso),
      el(
        "div",
        { classe: "acoes" },
        el("button", {
          type: "button",
          classe: "botao",
          texto: "Copiar código",
          onclick: async (evento) => {
            try {
              await navigator.clipboard.writeText(caso.codigo);
              evento.target.textContent = "Copiado!";
            } catch {
              evento.target.textContent = "Selecione e copie o código";
            }
          },
        }),
        botaoExcluir(caso.codigo, () => secaoSalvo.replaceChildren(el("p", { texto: "Caso excluído." })))
      )
    );
    secaoSalvo.hidden = false;
    secaoSalvo.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  } finally {
    botaoSalvar.textContent = "Salvar caso";
  }
});

formConsulta.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconder(caixaErros, areaConsulta);
  const codigo = document.getElementById("codigo").value.trim();
  if (!/^[A-Za-z0-9_-]{8,16}$/.test(codigo)) {
    mostrarErros(caixaErros, new ApiError(["Código inválido: confira o que você copiou ao salvar o caso."]));
    return;
  }
  try {
    const caso = await chamarApi(`/casos/${encodeURIComponent(codigo)}`);
    areaConsulta.replaceChildren(
      ...cartaoDoCaso(caso),
      el(
        "div",
        { classe: "acoes" },
        botaoExcluir(caso.codigo, () => {
          areaConsulta.replaceChildren(el("p", { texto: "Caso excluído." }));
          // se é o caso recém-salvo, o cartão de confirmação também não deve mais mostrá-lo
          if (secaoSalvo.querySelector(".codigo")?.textContent === caso.codigo) {
            secaoSalvo.replaceChildren(el("p", { texto: "Caso excluído." }));
          }
        })
      )
    );
    areaConsulta.hidden = false;
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  }
});

atualizarContador();
