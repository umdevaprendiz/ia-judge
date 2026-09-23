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
  Hoje todas as seções imprimem `OK`: Fracao, Pena, Faixa, Quantum, Fase 1, Fase 2.

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

## Próximo passo (Fase 3 do motor — causas de aumento e diminuição)

Base: art. 68, caput e parágrafo único, do CP. Diferença central em relação às
fases 1 e 2: **aqui a pena pode sair da faixa** (ultrapassar o máximo ou ficar
abaixo do mínimo) — não usar `Faixa.limitar` no resultado final desta fase.

Pontos do plano a implementar/decidir:
- Causas de aumento e de diminuição são frações (ex.: 1/3, 2/3, metade) aplicadas
  sobre a pena intermediária, uma de cada vez ou compostas — decidir e testar as
  duas formas de composição (sequencial vs. sobre a base original) e documentar
  a escolhida.
- Frações variáveis (ex.: "1/3 até metade"): o plano manda usar a mínima por
  padrão e só aumentar se houver justificativa registrada — a assinatura da
  função provavelmente precisa de um campo de "justificativa" opcional por
  causa aplicada.
- Concurso de causas de aumento/diminuição da Parte Especial (art. 68, parágrafo
  único): o juiz pode aplicar só a que mais aumente ou só a que mais diminua. O
  plano pede que o motor calcule e mostre as duas opções, não que escolha
  sozinho.
- Reaproveitar `Passo` para registrar cada causa aplicada (frações da Parte
  Geral, como causas de aumento genéricas, normalmente compõem com as da Parte
  Especial; as da própria Parte Especial em concurso seguem a regra acima).
- Adicionar as células de teste correspondentes no notebook, incluindo o caso de
  pena saindo da faixa (abaixo do mínimo ou acima do máximo) e o caso de
  concurso mostrando as duas opções.

Depois da Fase 3, o motor puro (Fases 1–3) estará completo e dá pra montar uma
função `calcular_dosimetria_completa` que encadeia as três fases e devolve um
`ResultadoDosimetria` com a lista de `Passo` de tudo — o próximo marco natural
antes de partir para ingestão (Planalto → banco) ou extração via LLM.