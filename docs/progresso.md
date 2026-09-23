# Progresso do motor de dosimetria (sergius-ia-Judge)

Registro de continuidade entre sessões, complementar ao `git log`. Baseado em
`plano-ia-dosimetria-penal.pdf`.

## Estrutura do pacote `dosimetria/`

```
dosimetria/
  __init__.py        API pública reexportada (from dosimetria import ...)
  valores/           Fraction, Penalty, PenaltyRange (tipos de valor imutáveis)
  circunstancias/    judiciais.py (art. 59), legais.py (arts. 61-67), causas.py (3ª fase)
  quantum/           estrategias.py (Strategy do quantum das fases 1 e 2)
  fases/             fase1.py, fase2.py, fase3.py, completa.py
  relatorio/         passo.py (passo a passo), fundamentacao.py (texto), serializacao.py (JSON)
  entrada.py         formato JSON de entrada (entrada_de_dict), o mesmo da API
  ensino.py          comparar_resposta (correção da dosimetria do estudante)
sentencas/           leitor do PDF de sentenças (fora do motor, que não depende de PDF)
api/                 API HTTP em FastAPI (app.py e esquemas.py)
web/                 páginas para estudantes (rotas.py, templates/, static/)
dados/casos/         dosimetrias.json e conjunto_treinamento.json
```

Quem usa o motor importa sempre de `dosimetria` (ex.: `from dosimetria import
Pena`); os subpacotes são organização interna e podem mudar sem quebrar isso.

## Feito

- `dosimetria/valores/fracao.py` — `Fraction(numerador, denominador)`, imutável, nunca usa `float`.
  `aplicar(dias)` trunca o resto (art. 11 do CP — frações de dia são desprezadas).
- `dosimetria/valores/pena.py` — `Penalty(dias)`, imutável, comparável (`<`, `==`), rejeita dias
  negativos. Convenção do projeto: 1 ano = 365 dias, 1 mês = 30 dias.
- `dosimetria/valores/faixa.py` — `PenaltyRange(minimo, maximo, origem)`. `contem()` e `limitar()`
  (clamp) são a base de "não sai da faixa" nas fases 1 e 2.
- `dosimetria/circunstancias/judiciais.py` — enum `JudicialCircumstance` com as 8 do art. 59,
  e `Assessment` (favorável/neutra/desfavorável).
- `dosimetria/quantum/estrategias.py` — `QuantumStrategy` (Strategy, ABC) com duas
  implementações citadas no plano: `IntervalFraction` (padrão 1/8 do intervalo) e
  `MinimumFraction` (padrão 1/6 do mínimo). Não há default escondido: quem chama o
  motor escolhe a estratégia explicitamente.
- `dosimetria/relatorio/passo.py` — `Step` (fase, regra, dispositivo, valor_antes,
  valor_depois, motivo), a unidade do "passo a passo" do relatório.
- `dosimetria/fases/fase1.py` — `calcular_pena_base(faixa, circunstancias, estrategia)`.
  Exige as 8 circunstâncias do art. 59 (lança `ValueError` se faltar/sobrar alguma).
  Só circunstâncias desfavoráveis somam; resultado sempre dentro da faixa.
- `dosimetria/circunstancias/legais.py` — `LegalCircumstance` (código, dispositivo,
  `CircumstanceDirection.AGRAVANTE`/`ATENUANTE`, `preponderante: bool`). Bis in idem é
  responsabilidade do validador (camada de extração), não do motor.
- `dosimetria/fases/fase2.py` — `calcular_pena_intermediaria(faixa, pena_base,
  circunstancias, estrategia)`. Regras implementadas:
  - Sem concurso (só agravante, só atenuante, ou nenhuma): soma/subtrai um
    incremento por circunstância.
  - Concurso com preponderância só de um lado (art. 67 do CP: motivos
    determinantes, personalidade, reincidência) → só as circunstâncias
    preponderantes contam, o outro lado é descartado.
  - Concurso com preponderância dos dois lados ou de nenhum → compensação
    líquida (conta simples de quantas agravam menos quantas atenuam).
  - Resultado sempre dentro da faixa; em particular a atenuante nunca reduz
    abaixo do mínimo (Súmula 231 do STJ), reaproveitando `PenaltyRange.limitar`.
- Testes: `tests/dosimetria_tests.ipynb` (notebook, não pytest — decisão do
  usuário). Rodar com:
  `py -m jupyter nbconvert --to notebook --execute --inplace tests/dosimetria_tests.ipynb`
  Hoje todas as seções imprimem `OK`: Fraction, Penalty, PenaltyRange, Quantum, Fase 1, Fase 2, Fase 3,
  Dosimetria completa, Casos de dosimetria.
- `dosimetria/circunstancias/causas.py` — `ModifyingCause` (código, dispositivo, `CauseDirection`
  AUMENTO/DIMINUICAO, `CauseOrigin` PARTE_GERAL/PARTE_ESPECIAL, `fracao_min`,
  `fracao_max` opcional, `fracao_escolhida` opcional, `justificativa`). Aplica a
  fração mínima por padrão; escolher outra exige estar no intervalo legal **e** ter
  justificativa (senão `ValueError`) — regra da seção 3.3 do plano / Súmula 443.
  Vale igualmente para aumento e diminuição (validar isso com professor: na
  diminuição, a mínima é a fração menos favorável ao réu).
- `dosimetria/fases/fase3.py` — `calcular_pena_definitiva(pena_intermediaria, causas,
  composicao)` → `Phase3Result(aplicando_todas, limitada_art68)`:
  - Não recebe `PenaltyRange`: a 3ª fase pode sair da faixa, e assim a regra de limite
    não tem como vazar para cá (responde à pergunta da Fase 2 do plano).
  - `Composition.CASCATA` (cada fração sobre a pena já modificada) ou
    `Composition.SOBRE_PENA_INTERMEDIARIA` (todas sobre a intermediária, efeitos
    somados). Sem padrão implícito, como no quantum. Na composição "sobre a
    intermediária", diminuições que somem mais de 100% dão `ValueError`.
  - Cálculo exato com `fractions.Fraction`; frações de dia desprezadas **uma
    única vez**, no fim da fase (seção 6.1 do plano). Por isso, na cascata, a
    ordem das causas não muda o resultado. Os `Step`s mostram os valores
    intermediários truncados e encadeiam (depois de um = antes do seguinte).
  - Art. 68, parágrafo único: havendo 2+ causas da Parte Especial no mesmo
    sentido, `limitada_art68` traz a alternativa com só a que mais aumenta e/ou só
    a que mais diminui (causas da Parte Geral seguem aplicadas nas duas opções);
    as descartadas aparecem como `Step` sem efeito. O motor não escolhe.
  - Sem causas: um `Step` explicando que pena definitiva = intermediária.

- `dosimetria/fases/completa.py` — `calcular_dosimetria_completa(faixa,
  circunstancias_judiciais, agravantes_atenuantes, causas, estrategia,
  composicao)` encadeia as três fases e devolve `SentencingResult` (seção 7.2
  do plano): `faixa_aplicada`, `pena_base`, `pena_intermediaria`,
  `pena_definitiva` (todas as causas aplicadas), `alternativa_art68` (a outra
  opção do art. 68, parágrafo único, quando existe), `passos` (1ª, 2ª e 3ª fases,
  encadeados), `criterio_quantum`, `composicao` e `alertas`.
  - A faixa recebida já é a aplicada (simples ou qualificada); escolher entre
    elas fica para quem monta o caso (ingestão/extração).
  - `Phase1Result` e `Phase2Result` ganharam `alertas`: pena-base travada no
    máximo, atenuante travada no mínimo (Súmula 231), agravante travada no
    máximo e concurso resolvido por preponderância (art. 67). A completa soma a
    isso: pena definitiva fora da faixa (permitido na 3ª fase) e existência das
    duas opções do art. 68, parágrafo único.
- `dosimetria/relatorio/fundamentacao.py` — `gerar_fundamentacao(resultado)`
  monta o texto da dosimetria (faixa, critério de quantum, composição, as três
  fases com cada passo, a opção do art. 68, parágrafo único, e os alertas) só a
  partir do `SentencingResult`, sem acrescentar análise nova. Os motivos das
  fases 1 e 2 passaram a nomear as circunstâncias (ex.: "(culpabilidade)",
  "(reincidencia)"). Testado na seção "Fundamentação" do notebook.

Testes: a seção "Fase 3" do notebook cobre furto noturno, pena acima do máximo e
abaixo do mínimo, fração sem justificativa/fora do intervalo, cascata x sobre a
intermediária, arredondamento único (365·7/6·7/6 = 496, não 495), roubo com
concurso de pessoas + arma de fogo + tentativa (duas opções), concurso de
diminuições.
A seção "Dosimetria completa" cobre um roubo com as duas opções do art. 68,
parágrafo único, o encadeamento dos passos das três fases, e os alertas de
Súmula 231, de agravante travada no máximo, de pena definitiva acima do máximo e
de pena-base travada no máximo. Todas as seções imprimem `OK`.

- `dados/casos/dosimetrias.json` — conjunto de 17 dosimetrias com resultado
  esperado calculado à mão (a conta fica anotada no campo `conta` de cada caso),
  no espírito da tabela `caso_benchmark` do plano. A seção "Casos de dosimetria"
  do notebook lê o arquivo, monta as entradas do motor e compara pena-base,
  intermediária, definitiva, alternativa do art. 68 e alertas. Para acrescentar
  um caso, basta incluir um objeto no JSON; não é preciso mexer no notebook.
  - 1 caso vem de sentença: `treinamento-04` (caso 04 do
    `Conjunto de Treinamento - 10 Sentenças Judiciais.pdf`).
  - 9 foram construídos primeiro, para cobrir as regras: repouso noturno, roubo com duas
    majorantes (composição sobre a intermediária), homicídio tentado com
    compensação reincidência x confissão, tráfico privilegiado com Súmula 231,
    estelionato com quantum de 1/6 do mínimo, preponderância do art. 67,
    agravante travada no máximo, concurso formal e Súmula 443.
  - 7 construídos depois, para combinações que faltavam: furto noturno e
    privilegiado (aumento e diminuição especiais em sentidos opostos, sem o
    concurso do art. 68), arrependimento posterior (art. 16) com 2/3
    justificados, crime continuado (art. 71) com 1/3 pelo critério do STJ de 5
    crimes, compensação simples entre agravante e atenuante não
    preponderantes, homicídio qualificado com atenuante preponderante
    (menoridade) vencendo a agravante, tráfico com duas diminuições especiais
    (§4 e art. 41, as duas opções do art. 68) e tráfico majorado (art. 40, VI)
    e privilegiado em cascata. Todos bateram com a conta à mão sem ajuste no
    motor.
- `dados/casos/conjunto_treinamento.json` — índice das 10 sentenças do PDF de
  treinamento. **Só o caso 04 é penal**; os outros 9 (consumidor, família,
  trabalho, locação, trânsito, previdenciário, saúde, contratos) não têm pena a
  calcular e ficam anotados como exemplos negativos para a etapa de extração.
- Docker: `Dockerfile` (python:3.14-slim, usuário sem root, com as
  dependências de `requirements-dev.txt`) e `docker-compose.yml` com dois
  serviços. `docker compose run --rm testes` executa o notebook contra o código
  atual (pasta montada só para leitura, cópia executada em `/tmp`) e sai com erro
  se algum assert falhar. `docker compose up jupyter` abre o JupyterLab em
  `http://127.0.0.1:8888` com um token aleatório gerado a cada início e mostrado
  no terminal (antes havia um token fixo, `dosimetria`, no compose; foi removido
  para não haver credencial no repositório público). A porta só escuta em
  127.0.0.1. O motor em si não tem
  dependências; `requirements.txt` só traz o `pypdf`, usado pelo leitor de
  sentenças. O `.dockerignore` deixa o PDF do conjunto de treinamento entrar na
  imagem, porque os testes o leem.
- `sentencas/` — leitura do `Conjunto de Treinamento - 10 Sentenças Judiciais.pdf`
  com `pypdf`. `ler_sentencas(pdf)` separa as 10 sentenças pela marca
  "CASO NN DE 10" e devolve `CourtDecision` (número, órgão, ramo, tema, processo,
  classe, partes, resultado, relatório, fundamentação, dispositivo, magistrado,
  cargo). `extrair_dosimetria_declarada(sentenca)` lê, por regras, o parágrafo
  "Dosimetria:" do dispositivo de uma sentença penal: pena-base, pena
  definitiva (entende "2 (dois) anos", "5 anos, 3 meses e 10 dias"),
  dias-multa e regime inicial. Para sentenças não penais, devolve `None`. Isso
  não é a extração com LLM do plano; serve de referência para testar o motor.
  A seção "Sentenças do conjunto de treinamento" do notebook confere as 10
  sentenças com `dados/casos/conjunto_treinamento.json` e, no caso 04, verifica
  que o motor chega à pena declarada pela juíza (2 anos). Antes os testes só
  usavam números do caso 04 transcritos à mão, sem ler o PDF.
- Formato JSON único de entrada e saída: `dosimetria/entrada.py`
  (`entrada_de_dict(dados)` → `SentencingInput`, com `.calcular()`) e
  `dosimetria/relatorio/serializacao.py` (`resultado_para_dict`: penas em
  `total_dias` + anos/meses/dias + texto, passos, alertas e fundamentação).
  Faixa em `{"anos", "meses", "dias"}` e frações como `"1/3"`; erros de formato
  viram `ValueError` com o campo e as opções válidas. Os casos foram movidos
  para `dados/casos/`, e cada um agora tem `entrada` (nesse formato) e
  `esperado`. O notebook usa esse conversor em vez de ter o seu próprio, e a
  seção "Entrada e saída em JSON" testa as mensagens de erro e o JSON de saída.
- `dosimetria/ensino.py` — `comparar_resposta(resultado, pena_base=...,
  pena_intermediaria=..., pena_definitiva=...)` corrige só as fases
  respondidas. Para cada uma, diz se está correta, a diferença em dias e como o
  motor chegou à pena. Na definitiva, aceita também a opção do art. 68,
  parágrafo único.
- API em FastAPI (`api/`), pedida para que estudantes universitários possam
  usar o motor. Rotas: `POST /dosimetria/calcular`, `POST /ensino/comparar`,
  `GET /exemplos`, `GET /exemplos/{id}` (os casos de `dados/casos/`), `GET
  /opcoes`, `GET /saude` e a documentação interativa em `/docs`, com exemplos
  preenchidos. Erros de validação voltam com status 422, o campo e a mensagem
  em português; violações de regra do motor (`ValueError`) também voltam como
  422 com a explicação. CORS está liberado para qualquer origem, sem login e
  sem guardar dados.
  - Docker: o `Dockerfile` tem os alvos `api` (padrão, imagem de ~208 MB,
    respeita a variável `PORT`) e `dev` (com Jupyter). `docker compose up api`
    sobe a API em `http://localhost:8000/docs`. Verificado com chamadas HTTP
    reais ao container.
  - Testes: a seção "API" do notebook usa o `TestClient` do FastAPI.
- Hospedagem: a primeira tentativa foi no Microsoft Azure (Container Apps, com a
  imagem no GitHub Container Registry). O login na Azure CLI funcionou, mas a
  conta não tinha nenhuma assinatura ativa ("No subscriptions found"), e o
  usuário decidiu trocar para o **Render**. O `render.yaml` (Blueprint) publica
  a API no plano gratuito, região virginia, a partir do `Dockerfile` (o Render
  compila o último estágio, que é o alvo `api`), com health check em `/saude`
  e `autoDeployTrigger: checksPass`: só publica depois que o workflow
  `.github/workflows/testes.yml` passar. O workflow agora só roda os testes;
  os jobs de publicação da imagem e de deploy no Azure foram removidos. Ficou
  no GitHub Container Registry uma imagem pública da API publicada durante a
  tentativa com o Azure; ela não é usada pelo Render.
- **API publicada no Render:** https://sergius-ia-judge.onrender.com/docs.
  Verificado pela internet: `/saude` e `/docs` respondem, os 10 casos de
  `dados/casos/dosimetrias.json` dão a pena definitiva esperada via `POST
  /dosimetria/calcular`, `/ensino/comparar` corrige (2/3 no exemplo), os erros
  de validação saem em português, o `§` chega correto e o CORS responde ao
  preflight de outra origem (`access-control-allow-origin: *`).
- Deploy pelo GitHub Actions: o workflow `testes.yml` virou "Testes e deploy".
  Depois dos testes, num push na `main`, o job `deploy` chama o deploy hook do
  Render (`secrets.RENDER_DEPLOY_HOOK_URL`, que nunca vai para o repositório)
  com `&ref=<sha>` e espera até `GET /saude` responder com esse commit (campo
  `commit`, lido de `RENDER_GIT_COMMIT`). No `render.yaml`, `autoDeployTrigger`
  passou a `"off"`. Se o secret faltar, o job falha com uma mensagem explicando
  o que configurar.
- **Páginas para estudantes** (`web/`), pedidas porque devolver só JSON seria
  pouco para estudantes. Ficam no mesmo repositório e no mesmo contêiner da API
  (decisão discutida com o usuário: um deploy só, sem CORS e sem versões
  descasadas), em arquivos separados: `web/rotas.py` (rotas `/`, `/calcular`,
  `/praticar`, `/como-funciona`), `web/templates/` (Jinja2, layout `base.html`)
  e `web/static/` (`estilo.css` com tema claro e escuro, `comum.js`,
  `calcular.js`, `praticar.js`, `icone.svg`). JavaScript sem framework e sem
  build; ele só chama a API JSON e insere texto via `textContent`. O `GET /`
  deixou de ser JSON e virou a página inicial; as rotas da API não mudaram. Os
  arquivos estáticos levam `?v=<commit>` para não ficarem presos no cache após
  um deploy.
  - Praticar: a lista mostra "Caso N" e o enunciado só os fatos, porque as
    descrições entregam a resposta; a descrição aparece depois da correção. A
    opção do art. 68, parágrafo único, conta como certa.
  - Bug encontrado no teste com navegador e corrigido: o campo do dispositivo da
    faixa se chamava `origem`, o mesmo nome do campo "Previsão" das causas, e com
    uma causa na tela o valor era lido vazio. Agora ele se chama `faixa_origem`,
    e a API recusa `origem`, `codigo` e `dispositivo` vazios (`min_length=1`,
    mensagem "não pode ficar vazio").
  - Testes: a seção "Páginas para estudantes" do notebook, e
    `tests/navegador/teste.js` (Playwright, 32 verificações), que roda no job
    `navegador` do GitHub Actions com o Chrome, contra a imagem Docker da API.
    O deploy só acontece se `testes` e `navegador` passarem.

## Decisões de projeto tomadas nesta sessão

- Stack 100% Python (o plano original previa Java/Spring Boot; o usuário pediu
  para trocar tudo para Python).
- Testes em notebook Jupyter, não em arquivos `pytest` (preferência explícita do
  usuário).
- Motor construído antes da ingestão (inverte a ordem do plano original: Fase 2
  do PDF antes da Fase 1), porque o motor não depende de banco nem de LLM — só
  precisa de `FatosDoCaso` preenchido à mão nos testes.
- Convenção de unidades: **1 ano = 365 dias** e 1 mês = 30 dias (decisão do
  usuário; a alternativa de 1 ano = 360 dias foi descartada). Como 12 meses
  somam só 360 dias, na exibição os meses param em 11 e o excedente fica nos
  dias: 726 dias = "1 ano, 11 meses, 31 dias" (antes saía "1 ano, 12 meses,
  1 dia"). A decomposição continua exata e volta para o mesmo total de dias.
- Estratégias de quantum não têm valor padrão implícito no motor: cada chamada a
  `calcular_pena_base`/`calcular_pena_intermediaria` recebe a estratégia
  explicitamente.

## Cuidado: duas sessões do Claude Code na mesma pasta

Durante esta sessão havia outra sessão do Claude Code (`mll-judicial-34`) rodando
na mesma pasta e fazendo o mesmo trabalho em paralelo (duplicando commits). O
usuário decidiu fechá-la e seguir só nesta sessão. Se ao retomar amanhã houver
mais de uma sessão aberta nesta pasta, confirme com o usuário antes de continuar
para não duplicar trabalho de novo.

## Próximo passo

- **Conjunto real ainda insuficiente**: o critério de pronto do plano pede 10
  dosimetrias *reais*; hoje há 1 (caso 04). Substituir os casos construídos por
  sentenças penais reais conforme forem aparecendo.
- Se o uso da API pública crescer, avaliar um limite de requisições por IP.
- Depois: ingestão (Planalto → banco) ou extração via LLM.
