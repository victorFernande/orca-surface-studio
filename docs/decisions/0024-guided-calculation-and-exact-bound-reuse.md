# ADR-0024 — Cálculo guiado sem confirmação duplicada e reutilização de limites exatos

Data: 2026-11-23. Estado: implementado para ensaio local na 0.16.0.

## Contexto

A escolha de áreas exigia avançar para uma tela e só então pedir o estudo.
Durante cálculos longos, a operação em andamento ficava em detalhes recolhidos.
A abertura também construía um catálogo de regiões que o fluxo guiado não usava.
O refinamento C2 consultava repetidamente os mesmos coeficientes das derivadas.

## Decisão

Manter as quatro etapas como indicação de estado, com o cálculo iniciado
diretamente pela etapa de áreas. Mostrar operação, tempo decorrido e cancelamento
na tela principal. Separar as ações de abrir Preview e revisar envio.
O pedido de cálculo tem um identificador devolvido no estado do controlador;
respostas atrasadas de consultas anteriores não liberam outro clique de cálculo.
Pedidos duplicados durante um trabalho ativo não substituem esse trabalho nem
mudam seu estado para erro.

Não modificar o motor de trajetórias para obter uma resposta mais rápida.
Memoizar os limites pelo suporte ativo dos nós da spline, preservando exatamente
a convenção `searchsorted(side='right')` dos extremos de cada consulta.
O conjunto de nós usado na chave contém todos os domínios das derivadas.
Assim, coordenadas na mesma célula produzem as mesmas fatias de coeficientes.
O cache é limitado a 32.768 consultas por tipo e por campo, sem persistência.
O dicionário de limites de segunda derivada é copiado ao sair do cache.

Reutilizar somente o resultado atual do controlador, para o mesmo pedido e
revisão, depois de conferir os dois conteúdos de G-code por SHA-256.
O cache não armazena autorização de impressão. Catálogos antigos passam a ser
calculados no método que os utiliza, não na abertura do fluxo guiado.

## Alternativas e consequências

Arredondar caixas, reduzir a malha, relaxar certificados ou trocar automaticamente
de método poderia acelerar mais, mas mudaria o cálculo já aprovado no Benchy.
Essas alternativas foram rejeitadas. Pintura local e peça inteira mantêm seus
métodos anteriores, e o usuário continua escolhendo explicitamente a alternativa.

Não é mostrado percentual ou prazo estimado, pois o refinamento pode acrescentar
trabalho e o fatiamento não tem duração previsível. A operação e o tempo decorrido
descrevem o estado observado. A medida de desempenho publicada é limitada à etapa
efetivamente cronometrada, sem qualificá-la como ganho do fluxo completo.

Ver [manual e evidências](../FLUXO_SIMPLES_V0160.md).
