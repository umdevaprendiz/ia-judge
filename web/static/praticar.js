// Página Praticar: mostra um caso, recebe a dosimetria do estudante e exibe a correção.
import {
  CIRCUNSTANCIAS,
  COMPOSICOES,
  ESTRATEGIAS,
  ApiError,
  chamarApi,
  el,
  esconder,
  lerPena,
  mostrarErros,
  nomeLegivel,
  renderizarResultado,
  textoPena,
} from "./comum.js";

const seletorCaso = document.getElementById("caso");
const enunciado = document.getElementById("enunciado");
const formulario = document.getElementById("resposta");
const caixaErros = document.getElementById("erros");
const areaCorrecao = document.getElementById("correcao");
const FASES = ["pena_base", "pena_intermediaria", "pena_definitiva"];

let casoAtual = null;

// ---------- enunciado ----------

function item(rotulo, ...conteudo) {
  return el("li", {}, el("strong", { texto: `${rotulo}: ` }), ...conteudo);
}

function descreverFracao(causa) {
  const intervalo = causa.fracao_max ? `de ${causa.fracao_min} a ${causa.fracao_max}` : causa.fracao_min;
  const escolhida = causa.fracao_escolhida ? `; fração escolhida ${causa.fracao_escolhida} (${causa.justificativa || "sem justificativa"})` : "";
  return `${intervalo}${escolhida}`;
}

function renderizarEnunciado(exemplo) {
  const entrada = exemplo.entrada;
  const desfavoraveis = entrada.circunstancias_desfavoraveis.map((c) => CIRCUNSTANCIAS[c] || c);

  const agravantes = entrada.agravantes_atenuantes.length
    ? el(
        "ul",
        {},
        entrada.agravantes_atenuantes.map((a) =>
          el("li", { texto: `${a.direcao === "agravante" ? "Agravante" : "Atenuante"}: ${nomeLegivel(a.codigo)} (${a.dispositivo})${a.preponderante ? ", preponderante" : ""}` })
        )
      )
    : "nenhuma";

  const causas = entrada.causas.length
    ? el(
        "ul",
        {},
        entrada.causas.map((c) =>
          el("li", {
            texto: `${c.direcao === "aumento" ? "Aumento" : "Diminuição"}: ${nomeLegivel(c.codigo)} (${c.dispositivo}, ${c.origem === "parte_geral" ? "Parte Geral" : "Parte Especial"}), fração ${descreverFracao(c)}`,
          })
        )
      )
    : "nenhuma";

  // a descrição do caso pode entregar a resposta; ela só aparece depois da correção
  enunciado.replaceChildren(
    el("h2", { texto: seletorCaso.selectedOptions[0]?.textContent || "Caso" }),
    el(
      "ul",
      { classe: "fatos" },
      item("Faixa de pena", `${entrada.faixa.origem}, de ${textoPena(entrada.faixa.minimo)} a ${textoPena(entrada.faixa.maximo)}`),
      item("Circunstâncias judiciais desfavoráveis", desfavoraveis.length ? desfavoraveis.join(", ") : "nenhuma"),
      item("Critério do quantum", `${entrada.estrategia.fracao} (${ESTRATEGIAS[entrada.estrategia.tipo] || entrada.estrategia.tipo}) por circunstância`),
      item("Agravantes e atenuantes", agravantes),
      item("Causas de aumento e de diminuição", causas),
      item("Várias causas na 3ª fase", COMPOSICOES[entrada.composicao] || entrada.composicao)
    )
  );
  enunciado.hidden = false;
}

// ---------- correção ----------

function diferencaEmTexto(dias) {
  if (dias === 0) return "sem diferença";
  const abs = Math.abs(dias);
  return `${abs} ${abs === 1 ? "dia" : "dias"} ${dias > 0 ? "acima" : "abaixo"} do esperado`;
}

function renderizarCorrecao(correcao) {
  const cartoes = correcao.fases.map((fase) =>
    el(
      "article",
      { classe: `correcao-fase ${fase.correta ? "correcao-fase--certa" : "correcao-fase--errada"}` },
      el(
        "h3",
        {},
        el("span", { classe: "selo", "aria-hidden": "true", texto: fase.correta ? "✓" : "✗" }),
        ` ${fase.fase}: ${fase.correta ? "correta" : "diferente do esperado"}`
      ),
      el(
        "dl",
        { classe: "comparacao" },
        el("dt", { texto: "Sua resposta" }),
        el("dd", { texto: fase.resposta.texto }),
        el("dt", { texto: "Esperado" }),
        el("dd", { texto: fase.esperado.texto }),
        !fase.correta && el("dt", { texto: "Diferença" }),
        !fase.correta && el("dd", { texto: diferencaEmTexto(fase.diferenca_dias) })
      ),
      el("p", { classe: "comparacao__titulo", texto: "Como o motor chegou a esta pena:" }),
      el("ul", {}, fase.explicacao.map((linha) => el("li", { texto: linha }))),
      fase.observacao && el("p", { classe: "observacao", texto: fase.observacao })
    )
  );

  const gabarito = el("details", { classe: "detalhes" }, el("summary", { texto: "Ver o gabarito completo" }));
  const conteudoGabarito = el("div", { classe: "gabarito" });
  conteudoGabarito.append(renderizarResultado(correcao.gabarito, { titulo: "Gabarito" }));
  gabarito.append(conteudoGabarito);

  areaCorrecao.replaceChildren(
    el("h2", { texto: "Correção" }),
    el("p", {
      classe: `placar ${correcao.acertos === correcao.total ? "placar--total" : ""}`,
      texto: `Você acertou ${correcao.acertos} de ${correcao.total} ${correcao.total === 1 ? "fase" : "fases"}.`,
    }),
    ...cartoes,
    el("p", { classe: "enunciado__descricao" }, el("strong", { texto: "Sobre este caso: " }), casoAtual.descricao),
    gabarito
  );
  areaCorrecao.hidden = false;
  areaCorrecao.scrollIntoView({ behavior: "smooth", block: "start" });
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconder(caixaErros);
  const resposta = {};
  for (const fase of FASES) {
    const pena = lerPena(formulario.querySelector(`[data-pena="${fase}"]`));
    if (pena) resposta[fase] = pena;
  }
  if (Object.keys(resposta).length === 0) {
    mostrarErros(caixaErros, new ApiError(["Preencha a pena de pelo menos uma fase."]));
    return;
  }
  const botao = formulario.querySelector('[type="submit"]');
  botao.disabled = true;
  botao.textContent = "Corrigindo…";
  try {
    renderizarCorrecao(await chamarApi("/ensino/comparar", { entrada: casoAtual.entrada, resposta }));
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
    botao.textContent = "Corrigir";
  }
});

// ---------- escolha do caso ----------

async function carregarCaso(id) {
  esconder(caixaErros, areaCorrecao);
  formulario.reset();
  try {
    casoAtual = await chamarApi(`/exemplos/${encodeURIComponent(id)}`);
    renderizarEnunciado(casoAtual);
    formulario.hidden = false;
  } catch (erro) {
    mostrarErros(caixaErros, erro);
  }
}

seletorCaso.addEventListener("change", () => {
  if (seletorCaso.value) carregarCaso(seletorCaso.value);
});

document.getElementById("sortear").addEventListener("click", () => {
  const opcoes = [...seletorCaso.options].filter((opcao) => opcao.value && opcao.value !== seletorCaso.value);
  if (!opcoes.length) return;
  seletorCaso.value = opcoes[Math.floor(Math.random() * opcoes.length)].value;
  carregarCaso(seletorCaso.value);
});

async function iniciar() {
  try {
    const exemplos = await chamarApi("/exemplos");
    // as descrições entregam a resposta, então a lista mostra só um número por caso
    seletorCaso.replaceChildren(
      el("option", { value: "", texto: "Escolha um caso…" }),
      ...exemplos.map((exemplo, indice) => el("option", { value: exemplo.id, texto: `Caso ${indice + 1}` }))
    );
  } catch (erro) {
    seletorCaso.replaceChildren(el("option", { value: "", texto: "Casos indisponíveis" }));
    mostrarErros(caixaErros, erro);
  }
}

iniciar();
