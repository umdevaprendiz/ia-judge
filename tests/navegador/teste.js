// Teste das páginas num navegador de verdade (Playwright), usando-as como um estudante.
//   cd tests/navegador && npm ci
//   BASE=http://127.0.0.1:8000 node teste.js          (usa o Microsoft Edge instalado)
//   NAVEGADOR=chrome BASE=... node teste.js           (usa o Google Chrome; é o que o CI faz)
// As fotos de tela vão para tests/navegador/fotos/ (ignorada pelo git).
const { chromium } = require("playwright-core");
const path = require("path");

const BASE = process.env.BASE || "http://127.0.0.1:8000";
const FOTOS = path.join(__dirname, "fotos");
require("fs").mkdirSync(FOTOS, { recursive: true });
const falhas = [];
const verificar = (condicao, mensagem) => {
  console.log(`${condicao ? "ok  " : "FALHA"} ${mensagem}`);
  if (!condicao) falhas.push(mensagem);
};

(async () => {
  const navegador = await chromium.launch({ channel: process.env.NAVEGADOR || "msedge", headless: true });
  const contexto = await navegador.newContext({ viewport: { width: 1280, height: 900 } });
  const pagina = await contexto.newPage();
  const errosConsole = [];
  // os 422 são provocados de propósito pelos testes de erro; qualquer outro erro conta
  pagina.on("console", (m) => m.type() === "error" && !m.text().includes("status of 422") && errosConsole.push(m.text()));
  pagina.on("pageerror", (e) => errosConsole.push(String(e)));

  // ---------- Início ----------
  await pagina.goto(`${BASE}/`);
  verificar((await pagina.title()).includes("sergius-ia-Judge"), "Início: título da página");
  verificar(await pagina.locator('nav a[aria-current="page"]', { hasText: "Início" }).count() === 1, "Início: menu marca a página atual");
  await pagina.screenshot({ path: `${FOTOS}/1-inicio.png`, fullPage: true });

  // ---------- Calcular: exemplo carregado e cálculo ----------
  await pagina.goto(`${BASE}/calcular`);
  await pagina.waitForFunction(() => document.querySelector('[name="faixa_origem"]').value === "CP.art155");
  verificar(await pagina.locator('[name="circunstancia"]').count() === 8, "Calcular: 8 caixas de circunstâncias");
  verificar(await pagina.locator('[name="circunstancia"][value="culpabilidade"]').isChecked(), "Calcular: exemplo marcou culpabilidade");
  verificar(await pagina.locator("#agravantes .linha").count() === 1, "Calcular: exemplo trouxe 1 agravante");
  verificar(await pagina.locator("#causas .linha").count() === 1, "Calcular: exemplo trouxe 1 causa");
  await pagina.click('button[type="submit"]');
  await pagina.locator("#resultado").waitFor({ state: "visible" });
  const definitiva = await pagina.locator(".pena--destaque .pena__valor").textContent();
  verificar(definitiva === "2 anos, 3 meses, 29 dias", `Calcular: pena definitiva exibida (${definitiva})`);
  verificar((await pagina.locator(".passo").count()) === 3, "Calcular: 3 passos no passo a passo");
  verificar((await pagina.locator(".fundamentacao").textContent()).startsWith("DOSIMETRIA DA PENA"), "Calcular: fundamentação exibida");
  verificar((await pagina.locator(".fundamentacao").textContent()).includes("Faixa aplicada (CP.art155)"), "Calcular: dispositivo da faixa chega ao resultado");
  verificar((await pagina.locator(".resultado__contexto").textContent()).startsWith("Faixa CP.art155:"), "Calcular: contexto mostra o dispositivo da faixa");
  await pagina.screenshot({ path: `${FOTOS}/2-calcular-resultado.png`, fullPage: true });

  // ---------- Calcular: exemplo com duas opções do art. 68 e alertas ----------
  await pagina.selectOption("#exemplo", "construido-02");
  await pagina.waitForFunction(() => document.querySelectorAll("#causas .linha").length === 2);
  await pagina.click('button[type="submit"]');
  await pagina.locator(".pena", { hasText: "Opção do art. 68" }).waitFor();
  verificar(await pagina.locator(".aviso--alerta li").count() >= 1, "Calcular: alertas exibidos no roubo com duas majorantes");

  // ---------- Calcular: erro de preenchimento ----------
  await pagina.locator('#causas .linha [name="fracao_min"]').first().fill("1,3");
  await pagina.click('button[type="submit"]');
  await pagina.locator("#erros").waitFor({ state: "visible" });
  const textoErro = await pagina.locator("#erros").textContent();
  verificar(textoErro.includes("Causa 1 · fração mínima"), `Calcular: erro aponta o campo (${textoErro.trim().slice(0, 90)})`);
  verificar(await pagina.locator("#resultado").isHidden(), "Calcular: resultado some quando há erro");
  await pagina.screenshot({ path: `${FOTOS}/3-calcular-erro.png` });

  // ---------- Calcular: regra do motor (fração acima da mínima sem justificativa) ----------
  await pagina.locator('#causas .linha [name="fracao_min"]').first().fill("1/3");
  await pagina.locator('#causas .linha [name="fracao_escolhida"]').first().fill("1/2");
  await pagina.click('button[type="submit"]');
  await pagina.waitForFunction(() => document.querySelector("#erros").textContent.includes("exige justificativa"));
  verificar(true, "Calcular: regra da justificativa (Súmula 443) aparece para o estudante");

  // ---------- Calcular: adicionar e remover linhas, limpar ----------
  await pagina.click('[data-adicionar="agravante"]');
  const linhasAntes = await pagina.locator("#agravantes .linha").count();
  await pagina.locator("#agravantes .linha [data-remover]").last().click();
  verificar(await pagina.locator("#agravantes .linha").count() === linhasAntes - 1, "Calcular: adicionar e remover linha");
  // campo obrigatório vazio: a API recusa com mensagem em português
  await pagina.fill('[name="faixa_origem"]', "");
  await pagina.click('button[type="submit"]');
  await pagina.waitForFunction(() => document.querySelector("#erros").textContent.includes("Faixa · dispositivo: não pode ficar vazio"));
  verificar(true, "Calcular: dispositivo vazio é recusado com mensagem clara");
  await pagina.click("#limpar");
  verificar(await pagina.locator("#causas .linha").count() === 0 && (await pagina.inputValue('[name="faixa_origem"]')) === "", "Calcular: limpar esvazia o formulário");

  // ---------- Calcular: conteúdo digitado não vira HTML ----------
  await pagina.selectOption("#exemplo", "construido-01");
  await pagina.waitForFunction(() => document.querySelector('[name="faixa_origem"]').value === "CP.art155");
  await pagina.fill('#agravantes .linha [name="codigo"]', '<img src=x onerror="window.injetado=1">');
  await pagina.click('button[type="submit"]');
  await pagina.locator("#resultado").waitFor({ state: "visible" });
  verificar(await pagina.evaluate(() => window.injetado === undefined && !document.querySelector("#resultado img")), "Calcular: texto do usuário não é interpretado como HTML");

  // ---------- Praticar ----------
  await pagina.goto(`${BASE}/praticar`);
  await pagina.waitForFunction(() => document.querySelectorAll("#caso option").length > 1);
  verificar(await pagina.locator("#resposta").isHidden(), "Praticar: formulário fica escondido até escolher um caso");
  const nomesCasos = await pagina.locator("#caso option").allTextContents();
  verificar(!nomesCasos.some((n) => n.includes("Súmula") || n.includes("preponderante")), "Praticar: lista de casos não entrega a resposta");
  await pagina.selectOption("#caso", "construido-01");
  await pagina.locator("#enunciado").waitFor({ state: "visible" });
  verificar((await pagina.locator("#enunciado").textContent()).includes("CP.art155"), "Praticar: enunciado mostra a faixa");
  verificar(!(await pagina.locator("#enunciado").textContent()).includes("Furto simples em repouso noturno"), "Praticar: enunciado não mostra a descrição antes da correção");
  await pagina.screenshot({ path: `${FOTOS}/4-praticar-enunciado.png`, fullPage: true });

  // resposta sem nada preenchido
  await pagina.click('#resposta button[type="submit"]');
  verificar((await pagina.locator("#erros").textContent()).includes("pelo menos uma fase"), "Praticar: pede ao menos uma fase");

  const preencher = async (fase, anos, meses, dias) => {
    const grupo = pagina.locator(`[data-pena="${fase}"]`);
    await grupo.locator('[name="anos"]').fill(String(anos));
    await grupo.locator('[name="meses"]').fill(String(meses));
    await grupo.locator('[name="dias"]').fill(String(dias));
  };
  await preencher("pena_base", 1, 4, 16);
  await preencher("pena_intermediaria", 1, 9, 2);
  await preencher("pena_definitiva", 2, 4, 0);
  await pagina.click('#resposta button[type="submit"]');
  await pagina.locator("#correcao").waitFor({ state: "visible" });
  verificar((await pagina.locator(".placar").textContent()) === "Você acertou 2 de 3 fases.", "Praticar: placar 2 de 3");
  verificar(await pagina.locator(".correcao-fase--errada").count() === 1, "Praticar: uma fase marcada como errada");
  verificar((await pagina.locator(".correcao-fase--errada").textContent()).includes("1 dia acima do esperado"), "Praticar: mostra a diferença em dias");
  verificar((await pagina.locator("#correcao").textContent()).includes("Furto simples em repouso noturno"), "Praticar: descrição aparece depois da correção");
  await pagina.locator("#correcao details summary").click();
  verificar(await pagina.locator("#correcao .fundamentacao").isVisible(), "Praticar: gabarito abre com a fundamentação");
  await pagina.screenshot({ path: `${FOTOS}/5-praticar-correcao.png`, fullPage: true });

  // opção do art. 68 aceita como certa
  // simula a latência da internet neste pedido, como no site publicado (onde o bug apareceu)
  await pagina.route("**/exemplos/construido-02", async (rota) => {
    await new Promise((resolver) => setTimeout(resolver, 1500));
    await rota.continue();
  });
  await pagina.selectOption("#caso", "construido-02");
  // trocar de caso esconde o enunciado anterior até o novo chegar (evita corrigir contra o caso errado)
  verificar(await pagina.locator("#resposta").isHidden(), "Praticar: formulário some enquanto o novo caso carrega");
  await pagina.locator("#enunciado").waitFor({ state: "visible" });
  verificar((await pagina.locator("#enunciado").textContent()).includes("CP.art157"), "Praticar: enunciado é o do caso novo");
  await preencher("pena_definitiva", 6, 8, 3);
  await pagina.click('#resposta button[type="submit"]');
  await pagina.locator(".placar").waitFor();
  verificar((await pagina.locator(".placar").textContent()) === "Você acertou 1 de 1 fase.", "Praticar: opção do art. 68 aceita como correta");

  // ---------- Como funciona ----------
  await pagina.goto(`${BASE}/como-funciona`);
  verificar((await pagina.locator("h1").textContent()) === "Como funciona", "Como funciona: página abre");

  // ---------- celular e tema escuro ----------
  const celular = await navegador.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
  const paginaCelular = await celular.newPage();
  await paginaCelular.goto(`${BASE}/calcular`);
  await paginaCelular.waitForFunction(() => document.querySelector('[name="faixa_origem"]').value === "CP.art155");
  const largura = await paginaCelular.evaluate(() => document.documentElement.scrollWidth);
  verificar(largura <= 390, `Celular: sem rolagem horizontal (largura ${largura}px)`);
  await paginaCelular.screenshot({ path: `${FOTOS}/6-celular-calcular.png`, fullPage: true });

  const escuro = await navegador.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "dark" });
  const paginaEscura = await escuro.newPage();
  await paginaEscura.goto(`${BASE}/calcular`);
  await paginaEscura.waitForFunction(() => document.querySelector('[name="faixa_origem"]').value === "CP.art155");
  await paginaEscura.click('button[type="submit"]');
  await paginaEscura.locator("#resultado").waitFor({ state: "visible" });
  await paginaEscura.screenshot({ path: `${FOTOS}/7-escuro-resultado.png`, fullPage: true });

  verificar(errosConsole.length === 0, `Sem erros no console do navegador ${errosConsole.length ? JSON.stringify(errosConsole) : ""}`);
  await navegador.close();
  console.log(falhas.length ? `\n${falhas.length} FALHA(S)` : "\nTODAS AS VERIFICAÇÕES PASSARAM");
  process.exit(falhas.length ? 1 : 0);
})().catch((erro) => {
  console.error(erro);
  process.exit(2);
});
