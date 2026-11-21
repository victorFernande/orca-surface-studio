# Vaso senoidal combinado — 0.4.0

Data: 20/11/2026. Escopo: implementação e ensaio digital; sem impressão física.

## Comportamento

O modo principal do Wave Studio combina deformação radial e vertical da parede
do vaso. Os três controles são intensidade em milímetros, ondas por volta e
altura inicial. Por padrão há seis ondas e a amplitude Z vale metade da radial.
Essa proporção e a fase ficam nos ajustes avançados. A amplitude cresce
quadraticamente de zero até a intensidade escolhida, preservando a região abaixo
da altura inicial. A borda superior permanece ondulada.

O Orca fornece os contornos da peça e a extrusão de origem. A transformação é
aplicada à parede externa da seleção. A costura, a base, as peças não selecionadas,
os modos de E e as retrações seguem o arquivo capturado. Contornos radiais simples
podem variar de forma e raio entre camadas. Não é necessário um cilindro constante.
O primeiro fluxo requer uma peça na placa para preparar o processo do vaso sem
alterar o processo de outras peças. Cópias vinculadas compartilham os parâmetros.

As trajetórias são voltas de camadas convencionais com costura, não uma hélice
contínua. O modo não recria a espiral nativa do Orca e recusa essa entrada.

## Modelo de cálculo

Em coordenadas cilíndricas, com centro fixo e contorno radial simples:

```
A(z) = intensidade * ((z - início) / (topo - início))²
d = A(z) * sin(ondas_por_volta * theta + fase)
R = r + d
Z = z - proporção_Z * d
```

Essa transformação altera a forma da peça; é independente do estudo que segue
a superfície superior original. A contagem inteira de ondas e a fase espacial
mantêm o alinhamento quando a costura muda de posição.

A extrusão usa o Jacobiano volumétrico do mapa radial/Z, com interpolação linear
de amplitude dentro de cada camada original. Integramos a densidade original de
E por quadratura, dividindo nos vértices originais. Não multiplicamos somente
pelo comprimento 3D. Os testes verificam o volume de uma faixa circular contra
sua integral analítica. O modelo não comprova aderência nem a seção física do
cordão em toda inclinação.

Amostragem: passo alvo de 0,4 mm, mínimo de 0,15 mm e tolerância máxima de
0,02 mm, com limite de erro por derivadas e vértices da polilinha. Mudanças de
velocidade muito próximas da costura usam o menor avanço de todo o contorno,
permitindo integrar E sem criar segmentos artificiais curtos. Velocidades
também são reduzidas pelas estimativas de movimento de Z; elas não simulam
o planejamento interno do firmware.

## Preparação e saída

**Preparar vaso** salva primeiro o projeto original em `backups/` no armazenamento
do plugin e depois configura parede única, base de três camadas, topo aberto,
preenchimento zero, curvas lineares e comentários de identificação. O usuário
fatia no Orca e o Studio transforma uma cópia imutável da captura. A ação não
contata impressoras. O pacote fatiado passa pela mesma abertura nativa e verificação
de identidade do Preview já existentes. O agente do plugin recusa transporte
para resultados desse modo, mesmo após a verificação da prévia.

## Evidências digitais

Reprodução: `python scripts/run_sine_vase_study.py`.
O ensaio usa um vaso gerado de 30 mm de altura, com raio variável, fatiado pelo
executável OrcaSlicer 2.5.1 e perfil de bancada da SV06. Não é o vaso aberto pelo
usuário. Arquivos: `study/evidence/sine-vase/`.

- 34.663 segmentos recriados; mínimo medido de 0,291628 mm.
- Erro geométrico limitado a 0,011884 mm.
- Espaçamento vertical calculado entre 0,189692 e 0,210310 mm.
- Estimativas máximas de Z: 2,327919 mm/s e aproximadamente 50 mm/s².
- Última camada no visor isolado: Z entre 29,25002 e 30,74993 mm.
- SHA-256 do G-code da reprodução mais recente: `2d229710dbad17e2fcf045326f240d8f4342423ac73d25cb8d475eba0e2d49d0`.
- Conteúdo extraído do pacote `.gcode.3mf` idêntico ao G-code gerado.

Os testes cobrem extrusão absoluta/relativa, XYZ absoluto/relativo, preservação
de outra peça e da base, abertura de costura, volume, limites, integridade do
pacote e bloqueio de transporte. O teste headless da interface usa uma ponte
simulada e não equivale ao WebView nativo do Orca.

Resultado da suíte: 108 testes aprovados, importação do pacote universal
aprovada e conferência headless sem erros JavaScript. A versão 0.4.0 foi instalada
no perfil padrão, com backup da versão anterior e preservação byte a byte do
arquivo de ativação. Recibo: `study/evidence/sine-vase/installation.json`.

Na janela nativa foram observadas a captura por objeto, a geração com 0,20 mm
e a abertura do pacote na aba Preview. A abertura passou pelo diálogo nativo
**Open as project**. Na camada lógica 40, o marcador mostrou Z=8,085, 8,093
e 8,024 mm ao avançar a extrusão da parede externa; entre essas amostras, o
G-code exibiu Z=8,09999 mm com E positivo. O arquivo gerado, o conteúdo do
pacote e o cache nativo lido depois da aprovação do usuário tinham SHA-256
`31fcabcc739f664a436d6043aa2d64321af91b63d0820394377a47da53e0b158`.
Registro: `study/evidence/sine-vase-small/native-gui-first/observation.json`.
Essa comparação independente não é um recibo emitido pelo controlador: a
versão inicialmente carregada invalidou a sessão enquanto o usuário aprovava
o acesso. A retomada foi corrigida e recebeu testes de alteração de arquivo,
mudança de projeto, cancelamento e expiração durante a espera. O retry retém
o modelo, a placa, a revisão e o caminho originais; não concede permissões.
O segundo ensaio emitiu o recibo nativo de identidade, com SHA-256
`7405acb8b7c3d0256a21c5168b8641935497385c63256efc874d09293a132dbf`,
preservado em `study/evidence/sine-vase-small/native-gui-verified/`.
Esse ensaio também revelou chamadas sobrepostas durante o diálogo modal,
que acumularam pedidos de leitura. A correção bloqueia a reentrada e só
retoma leituras pendentes quando o Studio volta a ter foco, após o diálogo.
O ciclo nativo final aprovou essa correção: uma captura, um pedido de acesso
à captura, uma geração e um pedido de acesso ao Preview, sem refatiar após a
confirmação e sem pedidos duplicados. A volta à aba do Studio concluiu cada
leitura. O recibo final, o relatório e os eventos estão em
`study/evidence/sine-vase-small/native-gui-final/`.
SHA-256 comum ao G-code, ao conteúdo do pacote e ao cache nativo:
`a35addf12d7d150f0aedd1ed41cf3989cb243854052cd4a81a08f03aa32958da`.
O Preview foi deixado na camada 40, vista frontal, marcador durante extrusão
da parede externa, mostrando Z=8,024 mm depois de passar pelo pico de
aproximadamente 8,100 mm. Os testes também simulam o laço modal aninhado.

Depois do reinício, a aba do Studio permaneceu ativa e a intensidade de
0,20 mm foi preservada durante a atualização/análise da mesa. A preparação
também passou a rearmar a captura sem exigir atualizar a mesa manualmente.
O teste evita a criação de um arquivo aleatório para localizar a pasta TEMP,
mantendo os pedidos nativos para os arquivos de fatiamento efetivamente lidos.

Pendente: captura do vaso real e validação do envelope do cabeçote.
O plugin não declara compatibilidade física universal com impressoras.

## Calibração progressiva solicitada pelo usuário

O objetivo é chegar a pequenos modelos físicos e ampliar o envelope de trabalho
à medida que a geometria real do cabeçote e os resultados forem confirmados.
O vaso digital de 30 mm é uma referência de software; não é um ensaio físico
aprovado nem o tamanho inicial obrigatório.

Foi produzido também um corpo de prova digital com 8 mm de altura, seis ondas,
intensidade radial 0,20 mm e Z de 0,10 mm, em
`study/evidence/sine-vase-small/`. Ele passou pelo fatiador nativo em modo CLI,
com 6.943 segmentos, erro calculado de até 0,011843 mm e espaçamento vertical
de 0,194367 a 0,205633 mm. O pacote mantém os mesmos bytes do G-code e
continua bloqueado para transporte. Isso não é aprovação física.

Reprodução:
`python scripts/run_sine_vase_study.py --height 8 --amplitude 0.2 --output study/evidence/sine-vase-small`.
O reuso do fatiamento agora verifica hashes da malha/configuração e do arquivo
de origem antes de aceitar o cache.

Sequência prevista:

1. Registrar o cabeçote instalado na SV06: ponta, bloco aquecedor, dutos,
   ventiladores e demais partes próximas, com distâncias à ponta do bico.
   Distinguir medidas confirmadas de estimativas.
2. Gerar pequenos corpos de prova com base plana, ondas suaves e região de
   atuação limitada. Conferir extrusão, descidas e deslocamentos no Preview.
3. Antes de liberar impressão, verificar a folga do conjunto ao longo dos
   percursos contra o material já depositado. Pequenas dimensões externas,
   isoladamente, não comprovam ausência de colisões.
4. Fazer um ensaio físico somente com autorização explícita, mantendo o perfil
   e os parâmetros do corpo de prova identificados. Aprovação física é manual;
   uma simulação não deve concedê-la.
5. Alterar uma variável por etapa: amplitude, altura/faixa não planar ou tamanho
   do modelo. Registrar defeitos e folga observada antes de ampliar novamente.

Essa sequência orienta o desenvolvimento. Ainda não há um verificador completo
do cabeçote nem liberação de impressão implementados. Permanece a instrução de
não enviar arquivos à impressora e de pedir autorização antes do controle da UI.

Referência conceitual: [FullControl overview](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/tutorials/colab/overview_colab.ipynb).
FullControl não foi incorporado como dependência do plugin nesta implementação.
