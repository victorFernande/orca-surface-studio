# ADR-0016 — Ordenar transições por dependência e extensão

Status: experimental; validação de referência em andamento.

## Contexto

Na 0.11.0, o Benchy apresentou uma faixa muito inclinada no casco frontal.
As superfícies eram processadas apenas pela altura. A extensão XY constante de
um campo não produz inclinação lateral fora de sua região, mas sua transição
vertical ainda estica as camadas. Pela regra da cadeia, esse estiramento pode
amplificar a inclinação criada por uma superfície processada depois.

## Decisão

Conservar a ordem de altura entre regiões cujas caixas XY se encontram,
incluindo a extensão lateral de ambos os campos. Entre as regiões disponíveis
sem dependências pendentes, priorizar os marcos planos e depois as superfícies
com maior extensão vertical. Os empates conservam a ordem original de altura.

Isso permite calcular a região inclinada frontal antes de uma referência
traseira mais curta, sem codificar o nome Benchy, posições fixas ou um perfil
específico. A referência mais alta é identificada pela altura original, e não
pela última posição na nova ordem de processamento.

A interpolação Hermite C1, a inversão, os certificados das faces e quinas e o
orçamento de 0,02 mm permanecem iguais aos da ADR-0015. A versão do campo muda
para `hermite_c1_xyz_v3`: resultados anteriores precisam ser recalculados.
Não se aumenta o limite de inclinação nem se altera a classificação visual
dos movimentos para esconder a faixa de overhang.

## Consequências

A prioridade é uma heurística geométrica, não uma prova universal de menor
inclinação para todos os sólidos. O alinhamento das referências, os Jacobianos
positivos, a malha, as cordas emitidas e a inclinação final continuam sujeitos
às auditorias completas. Uma falha interrompe o resultado integrado.

Não há novos controles: o usuário mantém os quatro passos existentes. A
aprovação digital não qualifica folga do cabeçote, deposição ou impressão física.
O estado de impressão continua bloqueado até essas verificações.

O registro de referência da 0.11.0 permanece histórico. A comparação desta
mudança será registrada separadamente, com capturas reais do Preview.
