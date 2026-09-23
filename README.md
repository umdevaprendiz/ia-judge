# sergius-ia-Judge: motor de dosimetria penal

Projeto de estudo de uma IA que auxilia na **dosimetria da pena** (Código Penal
brasileiro). Hoje o repositório contém o **motor de cálculo**, escrito em Python
puro, sem banco e sem LLM, que aplica o sistema trifásico do art. 68 do CP e
devolve o passo a passo de cada fase.

> Projeto educacional. O resultado não substitui a análise de um profissional.
> Confira as regras no texto compilado vigente do Planalto e, se possível,
> valide com um professor de Direito Penal.

O plano completo do projeto está em `plano-ia-dosimetria-penal.pdf`, e o
registro do que já foi feito e dos próximos passos está em
[`docs/progresso.md`](docs/progresso.md).

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
sentencas/               leitor do PDF de sentenças e da dosimetria que elas declaram
dados/casos/             casos de dosimetria com resultado esperado e anotação das sentenças (JSON)
tests/
  dosimetria_tests.ipynb notebook de testes
docs/progresso.md        o que foi feito, decisões tomadas e próximos passos
```

## Testes

Os testes ficam no notebook `tests/dosimetria_tests.ipynb`. Cada seção
imprime `OK`, e qualquer `assert` que falhar interrompe a execução naquele ponto.

A seção "Casos de dosimetria" lê `dados/casos/dosimetrias.json`: são 10
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

### Com Docker (recomendado)

```bash
# roda o notebook de testes contra o código atual; sai com erro se algum teste falhar
docker compose run --rm testes

# abre o JupyterLab para editar e rodar os testes
docker compose up jupyter
# -> http://127.0.0.1:8888/lab?token=dosimetria  (troque o token com JUPYTER_TOKEN)
```

### Sem Docker

Requer Python 3.14.

```bash
pip install -r requirements-dev.txt
jupyter nbconvert --to notebook --execute --inplace tests/dosimetria_tests.ipynb
```

O motor (`dosimetria/`) não tem dependências externas. O leitor de sentenças
(`sentencas/`) usa `pypdf`, e o Jupyter só é necessário para os testes.

## Próximos passos

- Reunir 10 dosimetrias de sentenças penais **reais**. Hoje só há uma: no
  conjunto de treinamento, apenas o caso 04 é penal.
- Gerar o texto da fundamentação a partir dos passos e alertas.
- Ingestão do Código Penal (Planalto → banco) e extração dos fatos do caso via LLM.

Os detalhes estão em [`docs/progresso.md`](docs/progresso.md).
