# Estudo do FullControl para o Orca Wave Studio

Revisão inicial: 19/11/2026. Complemento experimental: 20/11/2026. Revisão estudada:
`588ecfe7551c7c75e6307ddfeac302f563346b4c`, de 09/10/2026.
Em 19/11 a revisão foi estática. Em 20/11 o gerador de extrusão foi importado
em ambiente Python isolado para um ensaio numérico, sem executar procedimentos
de inicialização, enviar comandos ou modificar o plugin instalado no Orca.
O artigo foi lido integralmente e suas figuras das páginas 3 a 5 foram conferidas.
As legendas automáticas em inglês do tutorial foram obtidas e analisadas;
essa análise textual não equivale a uma conferência visual do vídeo.
O controle da janela do Orca permanece suspenso até autorização do usuário.

## Conclusão

O FullControl é um candidato a gerador opcional de G-code e a referência para a
descrição explícita de trajetórias. O Studio ainda precisaria planejar o percurso
conformal a partir da malha, calcular volumes locais e validar a interação com a
peça já depositada. A integração permanece uma proposta, sem código incorporado.

## Capacidades confirmadas

| Recurso | Evidência na revisão fixada | Aplicação no Studio |
|---|---|---|
| Pontos XYZ e movimentos com/sem extrusão | `fullcontrol/gcode/point.py` | Emitir os segmentos já calculados sobre a superfície. |
| Volume e estados de extrusão | `fullcontrol/gcode/extrusion_classes.py:101–133` | Converter volumes locais em E absoluto ou relativo. |
| Seção retangular, arredondada, circular ou manual | `fullcontrol/extrusion_classes.py:14–33` | Descrever a seção local de cada trecho e comparar modelos de deposição. |
| Perfil da Sovol SV06 | `fullcontrol/devices/cura/settings/sovol_sv06.py` e `devices/cura/library.json:526` | Ponto de partida para um perfil auditado da máquina do usuário. |
| Seleção do perfil Cura | `fullcontrol/gcode/state.py:56–59` | O identificador disponível é `Cura/Sovol SV06`. |
| Visualização dos percursos e do cordão | `fullcontrol/visualize/` | Comparação adicional com o Preview nativo do Orca. |
| Exemplo não planar | `models/nonplanar_spacer.ipynb` | Referência de construção de trajetórias, transições e parâmetros. |

A [documentação principal](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/README.md)
define um fluxo de trajetórias desenhadas explicitamente em Python. O exemplo
do espaçador calcula anéis ondulados por fórmulas; ele não projeta o percurso
sobre o STL de uma peça arbitrária.

## Limites relevantes

O [cálculo padrão de extrusão](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/fullcontrol/gcode/extrusion_classes.py#L101-L133)
usa comprimento 3D multiplicado pela área vigente. Isso não determina por si só
a quantidade correta de material quando a transformação comprime camadas ou
muda o espaçamento transversal. O Studio pode fornecer uma área manual coerente
com o volume planejado: para volume de segmento ΔV e comprimento 3D L, A=ΔV/L.
O volume precisa ser calculado antes, considerando a transformação e a deposição.
Esse vínculo foi exercitado no ensaio numérico de 20/11 descrito ao final.
O ensaio verifica transporte de volume pelo emissor, não a deposição física.

Não foi identificado um fluxo pronto que receba a malha do Orca e resolva
automaticamente base, interior, acabamento conformal, apoios e preservação de
furos. O componente de STL examinado no laboratório exporta uma malha do cordão
gerado a partir dos percursos. Isso não substitui o planejamento sobre a malha
da peça recebida.

O [roadmap](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/roadmap.md#L35)
lista detecção de colisões como trabalho posterior. Portanto, o estudo não assume
verificação pronta de folga entre bico, ventilação, estrutura e material depositado.

O [exportador 3MF experimental](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/lab/fullcontrol/controlcode_formats/steps2controlcode.py#L69-L90)
aceita apenas `bambulab_x1` nesse caminho e usa um pacote modelo. Ele não comprova
abertura, identidade de placa, integridade ou Print da SV06 no Orca. Nosso
empacotador e a conferência do arquivo efetivamente aberto continuariam necessários.

O perfil SV06 existente inclui inicialização, purga e encerramento. Esses comandos
não foram aprovados para a máquina física do usuário. Perfil existente significa
disponibilidade de configuração, não validação de hardware ou de qualquer impressão.
Para a SV06, o planejador usaria XYZ, sem exigir os módulos multieixos do laboratório.

## Integração proposta

1. Manter no Orca a leitura das peças, configurações e geração da estrutura planar.
2. Manter no Studio a análise da malha e o planejamento conformal com XYZ, volume,
   velocidade, transições e limites explícitos.
3. Comparar um adaptador FullControl com o gerador atual usando os mesmos segmentos
   planejados, sem alterar a geometria ou o volume-alvo para favorecer um gerador.
4. Manter o pacote próprio para o Preview do Orca e a conferência de hashes.

O primeiro ensaio de integração seria somente digital: usar o torus de 5 mm,
comparar endpoints, volume total, E absoluto/relativo, retrações, região inferior
preservada, furos, limites de Z e comportamento do Preview. Inicialização e purga
automáticas do FullControl precisam ser controladas no ensaio, para não introduzir
movimentos fora dos segmentos planejados. Nenhum envio à impressora real é previsto.

## Dependências e licença

O `pyproject.toml` declara Python >=3.10, NumPy, Pydantic e Plotly. Isso é compatível
com o requisito nominal de versão Python do Studio, mas não foi verificada a
execução no ambiente embutido do Orca. Uma eventual adoção deve fixar a revisão e
testar essas dependências de forma isolada.

O repositório distribui seu código sob
[GPLv3](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/license).
O Studio atualmente declara MIT. A forma de incorporar e distribuir a dependência
precisa ser definida com atenção às licenças; esta revisão não fez uma análise
jurídica nem alterou a licença do Studio.

## Complemento de 20/11: tutorial e cálculo do topo

A API oficial do GitHub confirmou que `master` permanece na revisão indicada
acima. O ensaio usa essa cópia local e não instala FullControl no Orca.

### Tutorial: resumo por tempos

[Quick-start introduction to FullControl (python version), Andy Gleadall](https://www.youtube.com/watch?v=qaQe-YgDPgo).
Duração: 10min54s. Fonte da análise: 267 segmentos de legendas automáticas;
podem conter erros de reconhecimento. Este quadro é uma síntese, não uma
transcrição literal nem uma descrição visual verificada.

| Tempo aproximado | Conteúdo |
|---|---|
| 00:00–01:39 | Repositório, tutoriais, Google Colab e execução das células. |
| 01:40–02:58 | Lista de pontos, extrusão ligada/desligada, prévia e edição. |
| 02:59–03:25 | Perfil, parâmetros, geração e download do G-code. |
| 03:26–03:55 | Exemplos de pontos gerados por expressões matemáticas. |
| 03:56–05:40 | Organização dos tutoriais, estados e funções geométricas. |
| 05:41–06:23 | Modelo inicial de projeto: parâmetros, percurso, prévia, exportação. |
| 06:24–08:28 | Conceitos gerais, conversões, anotações e repetições geométricas. |
| 08:29–09:01 | Demonstração experimental de cinco eixos. |
| 09:02–10:54 | Pastas do projeto e recomendação de explorar os exemplos no Colab. |

### Artigo: método e limites

[Ahlers et al., 2019](https://tams.informatik.uni-hamburg.de/publications/2019/case_ahlers_2019.pdf),
seções III–V e figuras 5–8: classificar regiões superiores por inclinação e folga,
reorganizar suas camadas de acabamento, gerar percursos planos e projetá-los
verticalmente sobre as faces. Inserir pontos nas interseções das arestas evita
cordas que atravessem a curvatura. O artigo também corrige extrusão e verifica
colisões; a implementação descrita não cobre outros modelos, suportes e saias.
Os limites exemplificados para Ultimaker 2 não são limites da SV06.

A equação 1 propõe `theta_th = atan(altura_de_camada / largura_de_extrusão)`;
com 0,20 e 0,45 mm, calculamos 23,9625°. Isso é um critério de qualidade,
não aprovação mecânica. A equação 4 usa `cos(atan(dz/L3D))`. A leitura do
[emissor](https://github.com/Zip-o-mat/Slic3r/blob/nonplanar/xs/src/libslic3r/GCode.cpp#L593),
de [Line::angle](https://github.com/Zip-o-mat/Slic3r/blob/nonplanar/xs/src/libslic3r/Line.cpp#L68)
e de [Point::distance_to](https://github.com/Zip-o-mat/Slic3r/blob/nonplanar/xs/src/libslic3r/Point.cpp#L187)
confirmou esse denominador na versão consultada. Ele não equivale a usar
o ângulo geométrico `atan2(dz,LXY)`; essa distinção exige verificação ao
adaptar o modelo de volume, sem substituição silenciosa da fórmula.

### Ensaio executado e interpretação para o Studio

Arquivo de resultados internos: `.research/review_20261120/calculation_results.json`.
As coordenadas abaixo foram recalculadas sobre os triângulos do retrato salvo
do torus real, sem abrir ou manipular sua janela. Não representam vértices
observados no Preview nem a inspeção do vaso atual.

| X (mm) | Y (mm) | Z superior na malha (mm) |
|---|---|---|
| 119 | 110 | 4,790768 |
| 120 | 110 | 4,999983 |
| 121 | 110 | 4,790297 |

O ponto central do furo, (110,110), não tem cobertura. Uma trajetória não deve
unir regiões separadas atravessando esse vazio com extrusão.

O ensaio do emissor FullControl usou uma faixa matemática de dois segmentos,
com X de 0 a 10 mm e Z de 5 a 6 e novamente 5 mm. No modelo retangular
didático com largura 0,45 mm e espaçamento vertical 0,20 mm, o volume-alvo
por comprimento projetado é 0,900000 mm³. Área constante multiplicada pelo
comprimento 3D resultou em 0,917824 mm³. Fornecer a área manual
`A_segmento = volume_alvo_segmento / comprimento_3D_segmento` ao mesmo emissor
resultou em 0,900000 mm³. Os dois movimentos emitidos tinham E positivo;
o erro de arredondamento do volume reconstruído de E foi menor que 0,000002 mm³.

Esses números verificam um contrato do gerador. Não estabelecem um modelo
universal de cordão: o planejador deve determinar o volume local a partir do
espaçamento real, largura, direção, inclinação e transições.

Para a interface, a proposta derivada do estudo continua sendo selecionar a
peça, escolher **Acompanhar topo** e usar **Gerar e abrir Preview**. A região
elegível deve aparecer antes da geração; a preparação intermediária deve ser
gerenciada pelo Studio. Este fluxo ainda não foi implementado ou validado
com o vaso nesta revisão.

Há uma distinção a tornar visível: um vaso aberto com borda horizontal pode
não oferecer variação Z no topo. Seguir sua parede ao longo de toda a altura
é outro problema de planejamento; acrescentar ondas modifica a forma. O
exemplo `nonplanar_spacer` define sua própria geometria por fórmulas e não
resolve automaticamente esses casos para qualquer STL.

O protótipo atual aplica uma transformação suave a uma faixa superior;
isso não implementa toda a classificação e reorganização de regiões do artigo.
Também rejeita faces inferiores/cavidades acima da âncora. Essa restrição é
um possível impedimento para alguns vasos, ainda sem diagnóstico da peça atual.
Não houve alteração do motor, instalação do plugin, controle da interface ou
envio à impressora nesta revisão.

### Notebook overview indicado pelo usuário

Em 20/11 também foi lido o
[overview_colab.ipynb](https://github.com/FullControlXYZ/fullcontrol/blob/588ecfe7551c7c75e6307ddfeac302f563346b4c/tutorials/colab/overview_colab.ipynb),
com 58 células, obtido diretamente do repositório. Não foi executado o notebook
inteiro, seu instalador Colab nem o exemplo multieixos.

Dois exemplos XYZ são especialmente relevantes. Na seção II, a célula 14
alterna `i*layer_height` e `i*layer_height/2` entre os quatro pontos da volta.
Para i=10 e altura 0,2 mm, isso produz Z=2,1,2,1 mm. A célula 16 constrói
uma hélice cujo raio e altura oscilam; uma avaliação independente de suas
fórmulas encontrou 4.534 segmentos descendentes em 9.999 segmentos. São
trajetórias não planares explícitas, diferentes de fatiar automaticamente
uma malha. Os exemplos finais com eixos B e C são um caso multieixos distinto.

A seção de visualização afirma que o gráfico é gerado da lista de passos,
sem reler G-code. Portanto, a prévia FullControl e o Preview Orca precisam
ser confrontados com o arquivo emitido. A lista compartilhada pode alimentar
ambas as saídas; ainda são necessárias verificações da conversão.

Aplicação proposta: o usuário escolhe a peça e o efeito; o Studio calcula a
lista de passos. Acompanhamento do topo usa pontos derivados da malha, enquanto
uma hélice ondulada é uma geometria de percurso escolhida. Não exigir edição
de Python, coordenadas ou células do Colab na interface do usuário.
