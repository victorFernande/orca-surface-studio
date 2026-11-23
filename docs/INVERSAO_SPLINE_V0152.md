# Inversão do campo de camadas — 0.15.2

O E2E da versão 0.15.1 encontrou `SPLINE_INVERSE` ao restaurar as trajetórias
do Benchy. O campo tinha derivada vertical positiva, mas Newton oscilava dentro
do intervalo permitido e esgotava as 40 iterações antes de convergir.

## Correção

As inversões escalar e em lote preservam as oito primeiras iterações de Newton.
Se ainda faltar convergência, passam a reduzir o intervalo por bisseção.
O número máximo de iterações usa a largura do domínio, a derivada superior
certificada do campo e a tolerância original de `1e-9`. Assim, a redução do
intervalo garante progresso para os casos em que Newton oscila.

O campo C2, a geometria de entrada, os limites de cordão do perfil, o limite
de inclinação e o orçamento geométrico de 0,02 mm permanecem os critérios do
estudo. A correção não transforma um estudo digital em aprovação física.

## Verificações

Um teste reduz a seção vertical problemática do ensaio real a um campo pequeno,
sem depender do cache local ou dos arquivos pessoais. O teste falhava antes da
correção e agora verifica as inversões escalar, em lote e com consultas preparadas
contra a raiz calculada independentemente por Brent, incluindo o resíduo de fase
abaixo de `1e-9`, a preservação de XY e a entrada intacta.

Os **291 testes Python passaram com `-W error`**. O bundle universal e o wheel
0.15.2 foram gerados, e a importação standalone do bundle passou. A reprodução
local das consultas por camada do G-code nativo anterior deixou de falhar.

No ensaio nativo, a cópia girada 180° passou da falha de inversão e foi recusada
por outro verificador: um cordão de 0,280664 mm excedia o máximo de 0,28 mm.
O espaçamento automático continua pendente. Foi então retomada manualmente a
distribuição C2 anteriormente verificada, com a mesma fatia planar preservada.
O novo processamento passou nos verificadores de deposição e movimento e
reproduziu exatamente o G-code anterior de 180°, confirmado no Preview.

O [registro do ensaio e do arquivo para revisão](TESTE_BENCHY_GIRO180_V0152.md)
distingue esses caminhos. A folga física continua inconclusiva; a publicação
no OrcaCloud permanece bloqueada pela política do projeto.
