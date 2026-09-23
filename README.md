# sergius-ia-Judge: motor de dosimetria penal

Projeto de estudo de uma IA que auxilia na **dosimetria da pena** (Código Penal
brasileiro), pensado para estudantes de Direito. Hoje o repositório contém:

- o **motor de cálculo**, em Python puro, sem banco e sem LLM, que aplica o
  sistema trifásico do art. 68 do CP e devolve o passo a passo de cada fase;
- uma **API HTTP** (FastAPI) para qualquer pessoa usar o motor pelo navegador ou
  por outro programa, incluindo a **correção da dosimetria feita pelo estudante**.

> Projeto educacional. O resultado não substitui a análise de um profissional.
> Confira as regras no texto compilado vigente do Planalto e, se possível,
> valide com um professor de Direito Penal.

O plano completo do projeto está em `plano-ia-dosimetria-penal.pdf`, e o
registro do que já foi feito e dos próximos passos está em
[`docs/progresso.md`](docs/progresso.md).

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

Depois disso, cada push na `main` publica uma versão nova, mas só depois que o
workflow de testes do GitHub (`.github/workflows/testes.yml`) passar. No plano
gratuito, o serviço dorme depois de um tempo sem acesso, e a primeira requisição
seguinte pode levar cerca de um minuto para responder.

## O que o motor faz

| Fase | Base legal | O que acontece | Limite |
|---|---|---|---|
| 1ª: pena-base | art. 59 | Cada circunstância judicial desfavorável soma um incremento definido pela estratégia de quantum | Não sai da faixa |
| 2ª: pena intermediária | arts. 61 a 67 | Soma agravantes e subtrai atenuantes; no concurso, as preponderantes (art. 67) prevalecem | Não sai da faixa (Súmula 231 do STJ) |
| 3ª: pena definitiva | art. 68 | Aplica causas de aumento e de diminuição em frações | Pode sair da faixa |

Regras que o motor respeita:

- **Quantum configurável.** A lei não fixa quanto vale cada circunstância. O
  critério é plugável e aparece no relatório: `FracaoDoIntervalo` (padrão 1/8
  do intervalo) ou `FracaoDoMinimo` (padrão 1/6 do mínimo).
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
    CausaModificadora, CircunstanciaJudicial, CircunstanciaLegal, Composicao, Direcao,
    DirecaoCausa, Faixa, Fracao, FracaoDoIntervalo, OrigemCausa, Pena, Valoracao,
    calcular_dosimetria_completa,
)

# Furto simples (art. 155): 1 a 4 anos de reclusão
faixa = Faixa(Pena.de_anos_meses_dias(anos=1), Pena.de_anos_meses_dias(anos=4), "CP.art155")

# 1ª fase: as 8 circunstâncias do art. 59 (aqui, só a culpabilidade é desfavorável)
circunstancias = {c: Valoracao.NEUTRA for c in CircunstanciaJudicial}
circunstancias[CircunstanciaJudicial.CULPABILIDADE] = Valoracao.DESFAVORAVEL

# 2ª fase: reincidência (agravante preponderante, art. 67)
agravantes_atenuantes = [
    CircunstanciaLegal("reincidencia", "CP.art61.I", Direcao.AGRAVANTE, preponderante=True),
]

# 3ª fase: repouso noturno, aumento de 1/3 (art. 155, §1º)
causas = [
    CausaModificadora("repouso_noturno", "CP.art155.§1", DirecaoCausa.AUMENTO,
                      OrigemCausa.PARTE_ESPECIAL, fracao_min=Fracao(1, 3)),
]

resultado = calcular_dosimetria_completa(
    faixa, circunstancias, agravantes_atenuantes, causas,
    estrategia=FracaoDoIntervalo(),      # 1/8 do intervalo por circunstância
    composicao=Composicao.CASCATA,
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

Além de `pena_definitiva` e `passos`, o `ResultadoDosimetria` traz `pena_base`,
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
  valores/               Fracao, Pena, Faixa
  circunstancias/        judiciais (art. 59), legais (arts. 61-67), causas (3ª fase)
  quantum/               estratégias de quantum das fases 1 e 2
  fases/                 fase1, fase2, fase3 e a dosimetria completa
  relatorio/             Passo, gerar_fundamentacao (texto) e resultado_para_dict (JSON)
  entrada.py             entrada_de_dict: o formato JSON de entrada (o mesmo da API)
  ensino.py              comparar_resposta: correção da dosimetria do estudante
sentencas/               leitor do PDF de sentenças e da dosimetria que elas declaram
api/                     API HTTP (FastAPI): app.py (rotas) e esquemas.py (formatos)
dados/casos/             casos de dosimetria com resultado esperado e anotação das sentenças (JSON)
tests/
  dosimetria_tests.ipynb notebook de testes
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
