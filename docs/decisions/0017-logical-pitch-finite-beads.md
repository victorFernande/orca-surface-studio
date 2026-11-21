# ADR-0017 — Espaçamento e cordão finito nas camadas contínuas

Status: experimental; conferência nativa realizada em 21/11/2026, impressão desativada.

## Contexto

A prioridade de superfícies da ADR-0016 reduziu a inclinação dos movimentos,
mas não limitou a distância local entre camadas. O cálculo também usava a
altura de feature do Orca como passo da célula: no Benchy, pontes internas
tinham altura de 0,368782 mm em uma sequência lógica de 0,12 mm. Essa altura
não define a distância até o percurso da camada anterior.

Os comentários de altura permaneciam com os valores da fatia intermediária,
embora os movimentos e E já tivessem sido modificados. O [processador oficial
do Orca](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/libslic3r/GCode/GCodeProcessor.cpp#L4932)
usa altura e largura forçadas pelos comentários na representação do cordão.
Por isso, as lacunas do Preview anterior não constituíam uma medição física de
falta de material. Tampouco seria correto aumentar E indiscriminadamente.

## Decisão

Separar passo lógico, altura de feature e altura normal modelada. O passo vem
da diferença entre referências Z de camadas sucessivas do mesmo objeto. Para
cordões apoiados, a altura modelada é a diferença vertical finita entre as
camadas mapeadas, dividida pelo fator de inclinação da superfície local. Isso
é uma aproximação geométrica, não uma medição da aderência ou da forma real do
filamento extrudado.

Usar uma seção finita de retângulo com semicírculos, com
`A(w,h) = w*h - (1 - pi/4)*h*h`. A extrusão integra a razão entre as áreas nova
e nativa ao longo das duas meias-cordas mapeadas, preservando o fator de fluxo
que o Orca aplicou. A largura nativa é preservada; as alturas e larguras
equivalentes são emitidas nos comentários do G-code junto com o E calculado.
Os comentários são restaurados conforme necessário antes de outra peça,
impedindo vazamento de uma seção modificada para percursos preservados.

Pontes e ironing conservam a seção/fluxo nativo por comprimento do percurso
mapeado. Não recebem a dilatação de uma célula de camada que não representa
seu apoio. Isso não qualifica pontes curvas ou suspensas para impressão.

Antes da transformação final, calcular um limite superior da extensão vertical
da célula nos retângulos XY completos dos movimentos nativos, ampliados pelo
passo de amostragem. A composição usa supremos positivos do Jacobiano em
intervalos e imagens desses intervalos. Grades iniciais que dependem somente
de Z usam sua secante finita exata: um ramo vizinho que toca somente a fronteira
não pode provocar densificação repetida sem fim.

Acrescentar intervalos somente nas faixas que ultrapassam 90% da menor entre
a altura máxima do perfil e a largura local. As referências originais de
camada permanecem nos nós da grade. A cópia é recortada em células afins e
refatiada pelo próprio Orca; a inversa da mesma grade restaura a geometria.
O certificado anterior de faces/quinas é herdado pela restauração exata de
cada triângulo precedente. Os núcleos de referência são recalculados e precisam
continuar dentro de uma faixa nativa. O teto e o sólido original permanecem
preservados pelo mesmo orçamento coordenado de 0,02 mm.

Permitir no máximo quatro subdivisões por intervalo e duas tentativas de
redistribuição, com nova verificação completa da fatia final. Uma falha recusa
o resultado; não aumenta limites ou modifica o perfil para forçar aprovação.

## Consequências

O usuário mantém os quatro passos e vê a faixa de altura efetiva do cordão.
Aumentar a altura efetiva altera o volume de material por percurso; acrescentar
intervalos nas faixas excessivamente espaçadas limita essa altura. O cálculo
não equivale a aumentar a altura nominal da placa ou aplicar um multiplicador
geral de fluxo.

Os testes verificam volume/seção, E absoluto e relativo, redefinições de E,
restauração para outra peça, pontes, primeira camada, pontos interiores dos
limites de célula, nós da grade, topologia de um furo e restauração afim.
O estudo também informa cancelamento e progresso durante a conferência dos
movimentos curtos e a geração dos cordões.

Uma grade global em Z pode produzir alturas muito pequenas em outra região
da mesma camada. Elas são mostradas e contadas separadamente do limite máximo.
Se ficam abaixo do mínimo do perfil, a interface avisa e a liberação física
continua falsa. O resultado permanece somente de Preview até qualificar
deposição, suporte das pontes e envelope real do cabeçote. `print_allowed`
não é ativado por essa alteração.

## Evidência observada

O Benchy de referência recebeu 21 intervalos adicionais, passando de 399 para
420 camadas no Preview. A conferência lateral mostrou preenchimento da faixa
aberta do casco. O máximo de altura normal modelada dos cordões apoiados foi
0,24 mm, abaixo do máximo de 0,28 mm do perfil. A inclinação máxima dos
movimentos permaneceu em 17,6143°. O mínimo de 0,03304 mm ficou abaixo dos
0,07 mm do perfil; portanto, a melhoria visual não libera a impressão.

Foram aprovados 250 testes locais e três cenários de componente da interface.
O ensaio retomou a cópia certificada e correspondente da 0.11.1, verificou suas
referências e aplicou a grade afim antes de novo fatiamento nativo. Não foi
uma repetição integral dos quatro passos na interface do Orca.
O [relatório com capturas e hashes](../ESPACAMENTO_CORDOES_V0120.md) registra
essa distinção e a correspondência do arquivo ao cache nativo do Preview.
