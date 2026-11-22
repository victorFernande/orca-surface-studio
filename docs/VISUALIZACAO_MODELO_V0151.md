# Visualização fiel do modelo — 0.15.1

A prévia anterior agrupava vértices até reduzir o modelo a menos de 4 mil
triângulos. Esse agrupamento alterava o contorno, podia eliminar faces e deixava
o casco e os furos do Benchy com aparência quebrada.

A prévia agora conserva todas as faces, na mesma ordem e com a mesma orientação.
Modelos maiores usam posições float32 e índices uint32 em buffers binários
indexados, com a precisão usada pela GPU. A iluminação interpola normais
ponderadas pelos ângulos dos cantos, respeitando arestas de 45° ou mais. A
superfície é opaca. Esses dados continuam exclusivos da visualização; a seleção
de áreas e o processamento usam a geometria original do projeto.

Vértices singulares com mais de 64 faces conservam a normal de cada face naquele
canto, evitando trabalho quadrático na iluminação de grandes leques de triângulos.

Cada aba/painel informa o identificador da malha que já recebeu. As consultas
periódicas passam a receber uma referência quando ela continua igual. Uma
referência desconhecida solicita novamente o estado completo; a mudança de
projeto limpa a malha anterior. Rotação e zoom reutilizam os buffers da GPU.

## Verificação local

No mesmo arquivo de referência, o Benchy passou de **3.209 para 225.154 faces
exibidas**, conservando todas as faces originais. A preparação medida caiu de
5,57 s para 1,23 s. O estado inicial ficou maior (cerca de 5,4 MB); as consultas
seguintes reutilizam a malha. Os tempos são desta execução local, sem promessa
de desempenho em outras máquinas.

Os testes verificam faces orientadas, fechamento e Euler de um cilindro denso,
posições na precisão da GPU, filtros de volumes/instâncias, imutabilidade do
projeto, arestas vivas, seleção por raio e reutilização por identificador. O
teste WebGL usa o Benchy completo, órbita, giro de 90°, troca de projeto e
reutilização dos buffers, sem acessar o Orca ou a impressora.

Para reproduzir a comparação, execute `scripts/prepare_model_preview_fixture.py`
com o 3MF e uma pasta de saída. `--source-tree` permite preparar a referência a
partir de outra revisão. Execute `scripts/check_model_preview_ui.cjs` com os
dois HTMLs e a pasta de evidências. `WAVE_PLAYWRIGHT` seleciona a instalação
local do Playwright. Os modelos e capturas locais ficam fora do Git.

A versão instalada entra em uso após fechar e reabrir o OrcaSlicer. A conferência
nativa desta revisão ainda depende desse reinício. A alteração não libera
impressão física nem a publicação no OrcaCloud.
