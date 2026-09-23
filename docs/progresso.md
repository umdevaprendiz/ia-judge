# Progresso do motor de dosimetria

Registro de continuidade entre sessões, complementar ao `git log`. Baseado em
`plano-ia-dosimetria-penal.pdf`.

## Feito

- `dosimetria/fracao.py` — `Fracao(numerador, denominador)`, imutável, nunca usa `float`.
  `aplicar(dias)` trunca o resto (art. 11 do CP — frações de dia são desprezadas).
- `dosimetria/pena.py` — `Pena(dias)`, imutável, comparável (`<`, `==`), rejeita dias
  negativos. Convenção do projeto: 1 ano = 365 dias, 1 mês = 30 dias.
- `dosimetria/faixa.py` — `Faixa(minimo, maximo, origem)`. `contem()` e `limitar()`
  (clamp) são a base de "não sai da faixa" nas fases 1 e 2.
- `dosimetria/circunstancias.py` — enum `CircunstanciaJudicial` com as 8 do art. 59,
  e `Valoracao` (favorável/neutra/desfavorável).
- `dosimetria/quantum.py` — `EstrategiaQuantum` (Strategy, ABC) com duas
  implementações citadas no plano: `FracaoDoIntervalo` (padrão 1/8 do intervalo) e
  `FracaoDoMinimo` (padrão 1/6 do mínimo). Não há default escondido: quem chama o
  motor escolhe a estratégia explicitamente.
- `dosimetria/passo.py` — `Passo` (fase, regra, dispositivo, valor_antes,
  valor_depois, motivo), a unidade do "passo a passo" do relatório.
- `dosimetria/fase1.py` — `calcular_pena_base(faixa, circunstancias, estrategia)`.
  Exige as 8 circunstâncias do art. 59 (lança `ValueError` se faltar/sobrar alguma).
  Só circunstâncias desfavoráveis somam; resultado sempre dentro da faixa.
- `dosimetria/agravantes_atenuantes.py` — `CircunstanciaLegal` (código, dispositivo,
  `Direcao.AGRAVANTE`/`ATENUANTE`, `preponderante: bool`). Bis in idem é
  responsabilidade do validador (camada de extração), não do motor.
- `dosimetria/fase2.py` — `calcular_pena_intermediaria(faixa, pena_base,
  circunstancias, estrategia)`. Regras implementadas:
  - Sem concurso (só agravante, só atenuante, ou nenhuma): soma/subtrai um
    incremento por circunstância.
  - Concurso com preponderância só de um lado (art. 67 do CP: motivos
    determinantes, personalidade, reincidência) → só as circunstâncias
    preponderantes contam, o outro lado é descartado.
  - Concurso com preponderância dos dois lados ou de nenhum → compensação
    líquida (conta simples de quantas agravam menos quantas atenuam).
  - Resultado sempre dentro da faixa; em particular a atenuante nunca reduz
    abaixo do mínimo (Súmula 231 do STJ), reaproveitando `Faixa.limitar`.
- Testes: `tests/dosimetria_tests.ipynb` (notebook, não pytest — decisão do
  usuário). Rodar com:
  `py -m jupyter nbconvert --to notebook --execute --inplace tests/dosimetria_tests.ipynb`
  Hoje todas as seções imprimem `OK`: Fracao, Pena, Faixa, Quantum, Fase 1, Fase 2, Fase 3.
- `dosimetria/causas.py` — `CausaModificadora` (código, dispositivo, `DirecaoCausa`
  AUMENTO/DIMINUICAO, `OrigemCausa` PARTE_GERAL/PARTE_ESPECIAL, `fracao_min`,
  `fracao_max` opcional, `fracao_escolhida` opcional, `justificativa`). Aplica a
  fração mínima por padrão; escolher outra exige estar no intervalo legal **e** ter
  justificativa (senão `ValueError`) — regra da seção 3.3 do plano / Súmula 443.
  Vale igualmente para aumento e diminuição (validar isso com professor: na
  diminuição, a mínima é a fração menos favorável ao réu).
- `dosimetria/fase3.py` — `calcular_pena_definitiva(pena_intermediaria, causas,
  composicao)` → `ResultadoFase3(aplicando_todas, limitada_art68)`:
  - Não recebe `Faixa`: a 3ª fase pode sair da faixa, e assim a regra de limite
    não tem como vazar para cá (responde à pergunta da Fase 2 do plano).
  - `Composicao.CASCATA` (cada fração sobre a pena já modificada) ou
    `Composicao.SOBRE_PENA_INTERMEDIARIA` (todas sobre a intermediária, efeitos
    somados). Sem padrão implícito, como no quantum. Na composição "sobre a
    intermediária", diminuições que somem mais de 100% dão `ValueError`.
  - Cálculo exato com `fractions.Fraction`; frações de dia desprezadas **uma
    única vez**, no fim da fase (seção 6.1 do plano). Por isso, na cascata, a
    ordem das causas não muda o resultado. Os `Passo`s mostram os valores
    intermediários truncados e encadeiam (depois de um = antes do seguinte).
  - Art. 68, parágrafo único: havendo 2+ causas da Parte Especial no mesmo
    sentido, `limitada_art68` traz a alternativa com só a que mais aumenta e/ou só
    a que mais diminui (causas da Parte Geral seguem aplicadas nas duas opções);
    as descartadas aparecem como `Passo` sem efeito. O motor não escolhe.
  - Sem causas: um `Passo` explicando que pena definitiva = intermediária.

Testes: a seção "Fase 3" do notebook cobre furto noturno, pena acima do máximo e
abaixo do mínimo, fração sem justificativa/fora do intervalo, cascata x sobre a
intermediária, arredondamento único (365·7/6·7/6 = 496, não 495), roubo com
concurso de pessoas + arma de fogo + tentativa (duas opções), concurso de
diminuições. Todas as seções imprimem `OK`.

## Decisões de projeto tomadas nesta sessão

- Stack 100% Python (o plano original previa Java/Spring Boot; o usuário pediu
  para trocar tudo para Python).
- Testes em notebook Jupyter, não em arquivos `pytest` (preferência explícita do
  usuário).
- Motor construído antes da ingestão (inverte a ordem do plano original: Fase 2
  do PDF antes da Fase 1), porque o motor não depende de banco nem de LLM — só
  precisa de `FatosDoCaso` preenchido à mão nos testes.
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

O motor puro (Fases 1–3) está completo. Próximo marco:
- `calcular_dosimetria_completa(faixa, circunstancias_judiciais,
  agravantes_atenuantes, causas, estrategia, composicao)` encadeando as três
  fases e devolvendo `ResultadoDosimetria` (seção 7.2 do plano): faixa aplicada,
  pena-base, intermediária, definitiva (ou as duas opções do art. 68, parágrafo
  único), lista completa de `Passo`, `criterio_quantum` e `alertas` (ex.: Súmula
  231 travou a atenuante).
- Reproduzir no notebook ao menos 10 dosimetrias reais (critério de pronto da
  Fase 2 do plano), tiradas de sentenças ou manuais.
- Depois: ingestão (Planalto → banco) ou extração via LLM.
