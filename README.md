# sergius-ia-Judge: motor de dosimetria penal

Projeto de estudo de uma IA que auxilia na **dosimetria da pena** (Código Penal
brasileiro), pensado para estudantes de Direito. Hoje o repositório contém:

- o **motor de cálculo**, em Python puro, sem banco e sem LLM, que aplica o
  sistema trifásico do art. 68 do CP e devolve o passo a passo de cada fase;
- **páginas para estudantes**, em https://sergius-ia-judge.onrender.com: calcular
  uma dosimetria com o passo a passo e praticar com casos, com correção fase a fase;
- uma **API HTTP** (FastAPI), usada pelas páginas e aberta a qualquer programa,
  incluindo a **correção da dosimetria feita pelo estudante**.

> Projeto educacional. O resultado não substitui a análise de um profissional.
> Confira as regras no texto compilado vigente do Planalto e, se possível,
> valide com um professor de Direito Penal.

O plano completo do projeto está em `plano-ia-dosimetria-penal.pdf`, e o
registro do que já foi feito e dos próximos passos está em
[`docs/progresso.md`](docs/progresso.md).

## Páginas para estudantes

| Página | O que o estudante faz |
|---|---|
| [Início](https://sergius-ia-judge.onrender.com/) | Visão geral do sistema trifásico |
| [Analisar caso](https://sergius-ia-judge.onrender.com/analisar) | Descreve um caso em detalhes; o texto é anonimizado (nomes, CPF, endereços, processos...), revisado pelo próprio estudante e guardado no MySQL, com código para consultar ou excluir. É a base de estudo do agente de análise, em construção |
| [Calcular](https://sergius-ia-judge.onrender.com/calcular) | Preenche a faixa, as circunstâncias, as agravantes e atenuantes e as causas (ou carrega um dos exemplos) e vê as três penas, os alertas, o passo a passo e a fundamentação, que pode ser copiada |
| [Praticar](https://sergius-ia-judge.onrender.com/praticar) | Recebe um caso (sem a descrição, que entregaria a resposta), faz a dosimetria e recebe a correção fase a fase, com a diferença em dias, a explicação e o gabarito |
| [Como funciona](https://sergius-ia-judge.onrender.com/como-funciona) | As regras usadas pelo motor, em linguagem de estudo |

As páginas ficam em `web/` (templates HTML, CSS e JavaScript sem framework) e são
servidas pelo mesmo app da API, no mesmo contêiner. O JavaScript só chama a API
JSON, então nenhuma regra do motor é duplicada no navegador. Os textos do usuário
entram na página só como texto (`textContent`), nunca como HTML.

## Segurança e privacidade

O site é público e recebe textos que podem conter dados pessoais, então a segurança é
tratada como requisito em cada funcionalidade:

- **Anonimização antes de gravar** (`privacidade/`): nomes, CPF, CNPJ, RG, e-mails,
  telefones, CEPs, placas, endereços e números de processo viram marcadores como
  `[PESSOA 1]`. O estudante vê e confirma o texto anonimizado; **o texto original nunca
  é gravado**. Cada caso tem um código aleatório (não sequencial) para consulta e
  **exclusão** a qualquer momento (LGPD).
- **Consentimento explícito** antes de salvar; só casos **validados pelo responsável**
  serão usados para ensinar o agente.
- **Cabeçalhos de segurança** em todas as respostas (`api/seguranca.py`): CSP sem scripts
  de terceiros nem inline, proibição de exibir o site dentro de outro (frame), `nosniff`,
  política de referência e HSTS em HTTPS. Respostas com casos não ficam em cache.
- **Limites**: tamanho máximo da requisição (256 KB, verificado enquanto o corpo chega)
  e da descrição (20 mil caracteres); limite de requisições por visitante e um teto
  global por rota. O IP do visitante vem do proxy do Render e não pode ser falsificado
  pelo cabeçalho `X-Forwarded-For`.
- **Outros sites só leem** (CORS libera apenas `GET`): nenhum site de terceiros consegue
  gravar ou excluir casos pelo navegador de um visitante.
- **Erros sem detalhes internos**: falhas de banco viram uma mensagem genérica, e erros de
  validação não ecoam textos longos.
- **Banco**: consultas parametrizadas (SQLAlchemy), conexão TLS com a Aiven (com
  verificação do certificado quando `MYSQL_CA_CERT` está definido) e esquema versionado
  por migrações (Alembic).
- **Segredos fora do código**: a URL do banco e a do deploy hook ficam só nos painéis do
  Render e do GitHub. O MySQL local usa senhas aleatórias num `.env` fora do git. O CI
  procura segredos no código e reprova o build se achar algum.
- **Dependências fixadas e auditadas**: o CI roda `pip-audit` e `npm audit` e reprova
  vulnerabilidades conhecidas; o Dependabot abre PRs de atualização toda semana.
- O contêiner roda com usuário sem privilégios de root.

## Banco de dados (MySQL)

Em produção, os casos ficam no **MySQL da Aiven**. Configuração, feita uma vez:

1. Na Aiven, no serviço MySQL, aba **Databases**: crie o banco `sergius_ia_judge`.
2. Aba **Users**: crie um usuário só para este projeto (ex.: `sergius_app`). Com o
   usuário administrador, dê a ele acesso **apenas** a esse banco:
   `GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES ON sergius_ia_judge.* TO 'sergius_app'@'%';`
3. No Render, no serviço, aba **Environment**, crie:
   - `DATABASE_URL`: a *Service URI* da Aiven com o usuário, a senha e o banco acima, no
     formato `mysql://<usuario>:<senha>@<host>:<porta>/sergius_ia_judge?ssl-mode=REQUIRED`;
   - `MYSQL_CA_CERT`: o conteúdo do certificado CA da Aiven (**Overview → CA certificate**),
     para a conexão também verificar a identidade do servidor.

As migrações rodam sozinhas quando o serviço inicia. Sem `DATABASE_URL`, o site funciona
normalmente e só a gravação de casos fica indisponível.

Localmente, o `docker compose` sobe um MySQL próprio na porta 33307 (para não conflitar
com outros projetos). Antes, gere o `.env` com senhas aleatórias:

```bash
python scripts/preparar_ambiente.py
docker compose up -d mysql
```

## Usando a API

A API está publicada em **https://sergius-ia-judge.onrender.com/docs**. É a
documentação interativa: em cada rota, clique em *Try it out* e depois em
*Execute*. As rotas já vêm com exemplos preenchidos. Ela fica no plano gratuito
do Render e "dorme" sem uso, então a primeira visita depois de um tempo pode
levar cerca de um minuto.

Para rodar na sua máquina, use `docker compose up api` e abra
http://localhost:8000/docs.

| Rota | O que faz |
|---|---|
| `POST /dosimetria/calcular` | Calcula as três fases e devolve as penas, o passo a passo, os alertas e a fundamentação em texto |
| `POST /ensino/comparar` | Corrige a dosimetria de um estudante fase a fase: diz o que está certo, a diferença em dias, como o motor chegou à pena e devolve o gabarito |
| `GET /exemplos` e `GET /exemplos/{id}` | Casos prontos (os mesmos dos testes) para colar em `/dosimetria/calcular` |
| `GET /opcoes` | Valores aceitos nos campos de escolha (circunstâncias, direções, estratégias...) |
| `GET /saude` | Verificação de funcionamento |

Exemplo de chamada fora do navegador:

```bash
curl -X POST https://sergius-ia-judge.onrender.com/dosimetria/calcular   -H "Content-Type: application/json"   -d '{
    "faixa": {"origem": "CP.art155", "minimo": {"anos": 1}, "maximo": {"anos": 4}},
    "circunstancias_desfavoraveis": ["culpabilidade"],
    "agravantes_atenuantes": [{"codigo": "reincidencia", "dispositivo": "CP.art61.I",
                               "direcao": "agravante", "preponderante": true}],
    "causas": [{"codigo": "repouso_noturno", "dispositivo": "CP.art155.§1",
                "direcao": "aumento", "origem": "parte_especial", "fracao_min": "1/3"}],
    "estrategia": {"tipo": "fracao_do_intervalo", "fracao": "1/8"},
    "composicao": "cascata"
  }'
```

Sem Docker: `pip install -r requirements.txt` e `uvicorn api.app:app --reload`.

Erros de preenchimento voltam com status 422, o nome do campo e uma mensagem em
português (ex.: `"causas.0.fracao_min": "formato inválido (frações no formato
'1/3')"`). Violações das regras do motor também voltam como 422, com a explicação
(ex.: fração acima da mínima sem justificativa).

A API não tem login nem guarda dados: ela só calcula. A imagem Docker padrão
(`docker build .`) já é a da API e respeita a variável `PORT`.

### Hospedagem no Render

O arquivo `render.yaml` descreve a publicação no [Render](https://render.com),
no plano gratuito. Para publicar pela primeira vez: no painel do Render, clique
em **New → Blueprint**, conecte a conta do GitHub, escolha este repositório e
clique em **Apply**. A API deste repositório está em
https://sergius-ia-judge.onrender.com/docs.

Quem publica as versões novas é o GitHub Actions (`.github/workflows/testes.yml`):
a cada push na `main`, ele roda os testes (notebook e navegador) e, se passarem, chama o *deploy hook*
do Render com o commit exato e espera a API pública responder com esse commit
(`GET /saude` informa o commit publicado). O Render não publica sozinho
(`autoDeployTrigger: "off"` no `render.yaml`).

Configuração, feita uma vez:

1. No Render, abra o serviço → **Settings** → **Deploy Hook** e copie a URL.
2. No GitHub, abra o repositório → **Settings → Secrets and variables → Actions →
   New repository secret**, com o nome `RENDER_DEPLOY_HOOK_URL` e a URL copiada
   como valor.

A URL do deploy hook contém uma chave secreta: ela fica só nesse secret e nunca
deve ser colada em arquivos do repositório. Se vazar, gere outra no Render
(**Regenerate Hook**) e atualize o secret.

No plano gratuito, o serviço dorme depois de um tempo sem acesso, e a primeira
requisição seguinte pode levar cerca de um minuto para responder.

## O que o motor faz

| Fase | Base legal | O que acontece | Limite |
|---|---|---|---|
| 1ª: pena-base | art. 59 | Cada circunstância judicial desfavorável soma um incremento definido pela estratégia de quantum | Não sai da faixa |
| 2ª: pena intermediária | arts. 61 a 67 | Soma agravantes e subtrai atenuantes; no concurso, as preponderantes (art. 67) prevalecem | Não sai da faixa (Súmula 231 do STJ) |
| 3ª: pena definitiva | art. 68 | Aplica causas de aumento e de diminuição em frações | Pode sair da faixa |

Regras que o motor respeita:

- **Quantum configurável.** A lei não fixa quanto vale cada circunstância. O
  critério é plugável e aparece no relatório: `IntervalFraction` (padrão 1/8
  do intervalo) ou `MinimumFraction` (padrão 1/6 do mínimo).
- **Fração mínima por padrão.** Nas causas de fração variável (ex.: "de 1/3 até
  metade"), usar outra fração exige justificativa registrada (Súmula 443 do STJ).
- **Art. 68, parágrafo único.** Quando há concurso de causas da Parte Especial,
  o motor calcula as duas opções (todas as causas aplicadas ou só a que mais
  aumenta ou diminui) e deixa a escolha com o juiz.
- **Sem `float`.** Frações são guardadas como numerador e denominador, e as
  frações de dia são desprezadas uma única vez, no fim da fase (art. 11 do CP).
- **Alertas.** O resultado avisa, por exemplo, quando a Súmula 231 travou uma
  atenuante ou quando a pena definitiva ficou fora da faixa.

Convenção de unidades: a pena é guardada em dias inteiros, com 1 ano = 365 dias
e 1 mês = 30 dias. Como 12 meses somam só 360 dias, na exibição os meses param
em 11 e o excedente fica nos dias: 726 dias aparecem como "1 ano, 11 meses,
31 dias".

## Exemplo de uso

```python
from dosimetria import (
    ModifyingCause, JudicialCircumstance, LegalCircumstance, Composition, CircumstanceDirection,
    CauseDirection, PenaltyRange, Fraction, IntervalFraction, CauseOrigin, Penalty, Assessment,
    calcular_dosimetria_completa,
)

# Furto simples (art. 155): 1 a 4 anos de reclusão
faixa = PenaltyRange(Penalty.de_anos_meses_dias(anos=1), Penalty.de_anos_meses_dias(anos=4), "CP.art155")

# 1ª fase: as 8 circunstâncias do art. 59 (aqui, só a culpabilidade é desfavorável)
circunstancias = {c: Assessment.NEUTRA for c in JudicialCircumstance}
circunstancias[JudicialCircumstance.CULPABILIDADE] = Assessment.DESFAVORAVEL

# 2ª fase: reincidência (agravante preponderante, art. 67)
agravantes_atenuantes = [
    LegalCircumstance("reincidencia", "CP.art61.I", CircumstanceDirection.AGRAVANTE, preponderante=True),
]

# 3ª fase: repouso noturno, aumento de 1/3 (art. 155, §1º)
causas = [
    ModifyingCause("repouso_noturno", "CP.art155.§1", CauseDirection.AUMENTO,
                   CauseOrigin.PARTE_ESPECIAL, fracao_min=Fraction(1, 3)),
]

resultado = calcular_dosimetria_completa(
    faixa, circunstancias, agravantes_atenuantes, causas,
    estrategia=IntervalFraction(),      # 1/8 do intervalo por circunstância
    composicao=Composition.CASCATA,
)

print("Pena definitiva:", resultado.pena_definitiva)
for passo in resultado.passos:
    print(f"- {passo.fase}: {passo.valor_antes} -> {passo.valor_depois} ({passo.motivo})")
```

Saída:

```
Pena definitiva: 2 anos, 3 meses, 29 dias
- 1ª fase (pena-base): 1 ano -> 1 ano, 4 meses, 16 dias (1 circunstância(s) desfavorável(is) do art. 59 (culpabilidade), fração do intervalo (1/8) cada)
- 2ª fase (pena intermediária): 1 ano, 4 meses, 16 dias -> 1 ano, 9 meses, 2 dias (1 agravante(s) (reincidencia), 0 atenuante(s))
- 3ª fase (pena definitiva): 1 ano, 9 meses, 2 dias -> 2 anos, 3 meses, 29 dias (repouso_noturno: aumento de 1/3 (em cascata))
```

Além de `pena_definitiva` e `passos`, o `SentencingResult` traz `pena_base`,
`pena_intermediaria`, `alternativa_art68`, `criterio_quantum`, `composicao` e
`alertas`.

Para o texto completo, no formato da seção de dosimetria de uma sentença (faixa,
critério, as três fases, a opção do art. 68, parágrafo único, e os alertas), use
`gerar_fundamentacao(resultado)`.

A mesma entrada também pode ser escrita em JSON (veja os casos em
`dados/casos/dosimetrias.json`): `entrada_de_dict(dados).calcular()` devolve o
resultado, e `resultado_para_dict(resultado)` o converte de volta para JSON.

## Estrutura

```
dosimetria/              motor de cálculo (a API pública é importada de `dosimetria`)
  valores/               Fraction, Penalty, PenaltyRange
  circunstancias/        judiciais (art. 59), legais (arts. 61-67), causas (3ª fase)
  quantum/               estratégias de quantum das fases 1 e 2
  fases/                 fase1, fase2, fase3 e a dosimetria completa
  relatorio/             Passo, gerar_fundamentacao (texto) e resultado_para_dict (JSON)
  entrada.py             entrada_de_dict: o formato JSON de entrada (o mesmo da API)
  ensino.py              comparar_resposta: correção da dosimetria do estudante
sentencas/               leitor do PDF de sentenças e da dosimetria que elas declaram
api/                     API HTTP (FastAPI): app.py, casos.py, seguranca.py e esquemas.py
banco/                   MySQL: conexão (TLS), tabelas, operações e migrar.py
migracoes/               migrações do esquema do banco (Alembic)
privacidade/             anonimização das descrições antes de gravar
scripts/                 preparar_ambiente.py (gera o .env local com senhas aleatórias)
web/                     páginas: rotas.py, templates/ (HTML) e static/ (CSS e JS)
dados/casos/             casos de dosimetria com resultado esperado e anotação das sentenças (JSON)
tests/
  dosimetria_tests.ipynb notebook de testes
  navegador/             teste das páginas num navegador de verdade (Playwright)
docs/progresso.md        o que foi feito, decisões tomadas e próximos passos
```

## Testes

Os testes ficam no notebook `tests/dosimetria_tests.ipynb`. Cada seção
imprime `OK`, e qualquer `assert` que falhar interrompe a execução naquele ponto.

A seção "Casos de dosimetria" lê `dados/casos/dosimetrias.json`: são 17
dosimetrias com o resultado esperado calculado à mão, e a conta de cada uma fica
anotada no próprio arquivo. Uma vem do caso 04 de
`Conjunto de Treinamento - 10 Sentenças Judiciais.pdf`; as outras foram
construídas para cobrir as regras do motor. Para acrescentar um caso, basta
incluir um objeto no JSON.

A seção "Sentenças do conjunto de treinamento" lê o próprio PDF com o pacote
`sentencas/`, separa as 10 sentenças (ramo, tema, processo, partes, resultado,
relatório, fundamentação, dispositivo e magistrado) e as confere com a anotação
de `dados/casos/conjunto_treinamento.json`. Na única sentença penal (caso 04), o
teste extrai a dosimetria que a juíza escreveu (pena-base, pena definitiva,
dias-multa e regime) e verifica que o motor chega à mesma pena. As outras 9
sentenças são cíveis, trabalhistas, previdenciárias ou administrativas, e o teste
confirma que nelas não há dosimetria a calcular.

A seção "Páginas para estudantes" confere que as páginas respondem, que referenciam
só arquivos que existem e que o JavaScript chama só rotas que a API tem.

O teste em `tests/navegador/teste.js` usa as páginas num navegador de verdade, como
um estudante: carrega exemplos, calcula, provoca erros de preenchimento, pratica e
confere a correção, verifica que o texto digitado não vira HTML, que não há rolagem
horizontal no celular e que o console fica sem erros. No GitHub Actions ele roda com
o Chrome contra a mesma imagem Docker que vai para o Render. Localmente, com a API
rodando em `http://127.0.0.1:8000`: `cd tests/navegador && npm ci && node teste.js`
(usa o Microsoft Edge; `NAVEGADOR=chrome` para o Chrome).

A seção "API" testa todas as rotas com o `TestClient` do FastAPI: os 17 exemplos
pela rota de cálculo, a correção do estudante (inclusive aceitando a opção do
art. 68, parágrafo único) e as mensagens de erro.

### Com Docker (recomendado)

```bash
# roda o notebook de testes contra o código atual; sai com erro se algum teste falhar
docker compose run --rm testes

# abre o JupyterLab para editar e rodar os testes; o terminal mostra o endereço
# com um token aleatório gerado a cada início (http://127.0.0.1:8888/lab?token=...)
docker compose up jupyter
```

### Sem Docker

Requer Python 3.14.

```bash
pip install -r requirements-dev.txt
jupyter nbconvert --to notebook --execute --inplace tests/dosimetria_tests.ipynb
```

O motor (`dosimetria/`) não tem dependências externas. O leitor de sentenças
(`sentencas/`) usa `pypdf`, a API usa FastAPI e uvicorn, e o Jupyter (com o
`httpx`, usado nos testes da API) só é necessário para os testes.

## Próximos passos

- Reunir 10 dosimetrias de sentenças penais **reais**. Hoje só há uma: no
  conjunto de treinamento, apenas o caso 04 é penal.
- Ingestão do Código Penal (Planalto → banco) e extração dos fatos do caso via LLM.

Os detalhes estão em [`docs/progresso.md`](docs/progresso.md).

## Autor

Desenvolvido por **Sérgio Souza** ([@umdevaprendiz](https://github.com/umdevaprendiz)).

© 2026 Sérgio Souza. Todos os direitos reservados. O código está disponível para
consulta, mas não há licença de uso, cópia ou redistribuição.
