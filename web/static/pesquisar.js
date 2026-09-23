// Página Pesquisar na lei: busca nos artigos da base de legislação (GET /fontes/buscar).
import { cartaoDeDispositivo, chamarApi, el, esconder, mostrarErros } from "./comum.js";

const formulario = document.getElementById("form-busca");
const campoConsulta = document.getElementById("q");
const seletorLei = document.getElementById("lei");
const caixaErros = document.getElementById("erros");
const caixaAvisos = document.getElementById("avisos");
const areaResultados = document.getElementById("resultados");

async function pesquisar(consulta, lei) {
  esconder(caixaErros, caixaAvisos);
  const parametros = new URLSearchParams({ q: consulta });
  if (lei) parametros.set("lei", lei);
  const botao = formulario.querySelector('[type="submit"]');
  botao.disabled = true;
  botao.textContent = "Pesquisando…";
  try {
    const resposta = await chamarApi(`/fontes/buscar?${parametros}`);
    if (resposta.avisos.length) {
      caixaAvisos.replaceChildren(el("ul", {}, resposta.avisos.map((aviso) => el("li", { texto: aviso }))));
      caixaAvisos.hidden = false;
    }
    areaResultados.replaceChildren(
      el("h2", { texto: resposta.resultados.length ? "Artigos encontrados" : "Nada encontrado" }),
      el(
        "ol",
        { classe: "lista-resultados" },
        resposta.resultados.map((resultado) => el("li", {}, cartaoDeDispositivo(resultado, resultado.trecho)))
      )
    );
    areaResultados.hidden = false;
    // o endereço guarda a busca, para poder voltar a ela ou compartilhar
    history.replaceState(null, "", `/pesquisar?${parametros}`);
  } catch (erro) {
    esconder(areaResultados);
    mostrarErros(caixaErros, erro);
  } finally {
    botao.disabled = false;
    botao.textContent = "Pesquisar";
  }
}

formulario.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const consulta = campoConsulta.value.trim();
  if (consulta.length < 2) {
    mostrarErros(caixaErros, new Error("Escreva pelo menos duas letras."));
    return;
  }
  pesquisar(consulta, seletorLei.value);
});

async function iniciar() {
  try {
    const leis = await chamarApi("/fontes/leis");
    seletorLei.append(...leis.map((lei) => el("option", { value: lei.lei, texto: `${lei.nome} (${lei.artigos} artigos)` })));
  } catch {
    // sem a lista, a busca continua funcionando em todas as leis
  }
  const inicial = new URLSearchParams(location.search);
  if (inicial.get("q")) {
    campoConsulta.value = inicial.get("q");
    if (inicial.get("lei")) seletorLei.value = inicial.get("lei");
    pesquisar(campoConsulta.value, seletorLei.value);
  }
}

iniciar();
