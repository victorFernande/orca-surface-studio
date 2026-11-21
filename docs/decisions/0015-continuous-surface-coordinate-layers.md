# ADR-0015 — Planejar camadas nas coordenadas das superfícies

Status: implementação experimental; caso Benchy reprovado na auditoria e no Preview de diagnóstico.

## Contexto

A abrangência de Peça inteira na 0.10.1 não removia o limite de uma janela de
camada do ContourZ. Reduzir a altura das camadas ou ampliar a seleção não resolve
uma borda inclinada que precisa atravessar vários milímetros em Z dentro da
mesma camada lógica. O original deve conservar casco, cavidades, furos e quinas.

## Decisão

O modo Peça inteira usa coordenadas reversíveis de superfície. Identifica
regiões superiores extensas, ajusta referências planas ou quadráticas com pesos
de área e aplica mapas verticais de Jacobiano positivo à cópia privada do sólido.
Os campos de faces paralelas compartilham a extensão XY, evitando uma mudança
de inclinação dentro da borda adjacente. O ajuste residual da malha permanece
na cópia: não se substitui a peça por um conjunto de planos ajustados.

Uma última reparametrização monotônica alinha conjuntamente os núcleos de
superfície às faixas de corte reais. Regiões que se sobrepõem em Z são agrupadas.
Um resíduo pequeno que atravessa duas faixas ainda causaria um degrau: por isso
a verificação de alinhamento é separada da medida do ajuste geométrico.
Referências quase coincidentes também compartilham a faixa: criar dois controles
separados por poucos micrômetros comprimiria desnecessariamente o espaçamento
entre as camadas de transição.

O Orca fatia essa cópia uma vez com ContourZ desativado no projeto, objeto e
parte. A inversa restaura os percursos ao espaço original. A primeira camada
permanece plana. A extrusão usa o volume da célula entre camadas mapeadas e
integração ao longo do percurso, além dos limites do perfil ativo. Não se aplica
uma segunda deformação sobre G-code que já recebeu ContourZ.

O refinamento compartilha vértices e mantém a topologia fechada. Cada face é
conferida contra seu plano original, e as quinas são conferidas como curvas.
O orçamento coordenado inicial de 0,02 mm é repartido entre a cópia da malha e
as cordas de G-code emitidas. O erro normal não deve ser apresentado como erro
vertical, nem como certificação da qualidade física de deposição.

A cópia recebe inicialmente 0,01 mm; as cordas recebem o restante medido do
orçamento de 0,02 mm, com uma margem numérica. A primeira divisão de 0,015 mm
para a cópia deixou apenas cerca de 0,005 mm para as cordas: uma aresta de
preenchimento de 0,283 mm exigia mais precisão, mas dividi-la violaria o mínimo
de 0,15 mm. A união com os vizinhos não certificou as quinas. A solução é
refinar mais a malha intermediária, mantendo o mesmo erro total permitido.

A varredura inicial de faces usa a versão vetorizada do mesmo certificado.
As faces adaptativas continuam com a versão escalar, e as verificações de quina
são reutilizadas somente para as mesmas extremidades imutáveis. Um teste compara
ambas as fórmulas através dos ramos verticais, extensões XY e nós da grade.
Os limites de erro e de segmentos não são relaxados para acelerar o cálculo.

As ligações verticais com a base e o limite superior têm derivada igual a um,
compatível com o trecho preservado. A referência intermediária compartilha a
mesma tangente nos dois lados. Os controles de derivada de Bézier são positivos;
os limites de curvatura e as cordas usam essa mesma interpolação. Isso corrige
o salto de tangente encontrado numa extrusão nativa de 0,065 mm, que excedia
o orçamento de erro e era corretamente recusada. A exceção para preservar
arestas curtas originais continua exigindo uma corda certificada.

Cada novo vértice de estágio não linear é calculado a partir da face original,
evitando acumular o resíduo da aproximação anterior nas subdivisões. Na grade
final, cada célula é afim depois de cortar nos seus planos: sua inversa restaura
o triângulo anterior inteiro exatamente, preservando seu certificado sem repetir
o refinamento não linear. Os nós colineares redundantes não criam novos cortes.
A interface invalida resultados
de um núcleo de transição anterior, mesmo quando os controles visíveis coincidem.

As extensões laterais do campo também compartilham a primeira derivada com o
trecho interno e com a região constante externa (`hermite_c1_xyz_v2`). O ajuste
nas faces originais permanece o mesmo; a extensão gradual ocorre fora de sua
caixa XY. Isso remove o salto de tangente lateral encontrado em uma parede curta
da proa. A largura inicial é quatro vezes o passo de amostragem, sem ampliar a
tolerância geométrica ou reduzir o comprimento mínimo dos segmentos novos.

O certificado de corda usa o menor de dois limites independentes válidos: Hessiana
ao longo da caixa do trecho e envoltória de Bernstein após os cortes de ramo.
Na composição, o erro vertical é propagado pelo máximo do jacobiano no tubo de
erro local completo. Aplicar o máximo global em regiões onde o estágio é a
identidade produzia recusas excessivamente conservadoras. Testes com amostras
independentes conferem os limites através das extensões e das ligações verticais.

## Consequências

O fluxo simples continua Modelo → Áreas → Estudar movimento → Mandar para a
bandeja. Peça inteira é o padrão deste cálculo. A pintura localizada permanece
no método nativo anterior; esta versão não afirma estender o novo planejador a
qualquer máscara pintada, superfície inferior ou modelo arbitrário.

Mapas estritamente crescentes impedem inversão das camadas, mas não comprovam
folga do cabeçote, contato do bico, aderência ou espessura depositada. A geração
recusa referências incompatíveis, malha excessiva, limites de movimento ou
segmentação incompatíveis. O estudo e o Preview não liberam impressão física
automaticamente. Não há envio à impressora neste teste.

## Impedimento observado no Benchy

A referência completa com orçamento de malha de 0,01 mm produziu 602.037
segmentos. A auditoria dos movimentos emitidos mediu 52,664° em preenchimento
sólido interno, acima dos 30° do estudo. O espaçamento normal amostrado chegou a
0,954 mm, com 1.170 trechos acima da largura nominal da linha. A aproximação
geométrica, a inversibilidade e o alinhamento das referências passaram; a
deposição e as transições do resultado não foram aprovadas.

O Preview nativo abriu um pacote de diagnóstico separado, identificado HOLD.
O cache nativo manteve o mesmo hash do pacote e do G-code desse diagnóstico.
Foram observados dois extremos de Z no teto dentro da camada exibida 329,
além da borda inclinada na camada 189. A vista completa também mostrou falhas
nas ligações do casco. O fluxo de quatro passos pela interface não foi concluído:
a execução repetida foi cancelada depois da reprovação independente da referência.

O domínio vertical amplo de um estágio pode dilatar a variação lateral de outro
na composição, mesmo onde o primeiro campo tem altura XY constante. Continuidade
C1 e jacobiano positivo não limitam esse gradiente composto nem o espaçamento
de deposição. A etapa restante exige restrições conjuntas sobre o campo, com
nova validação geométrica e de percursos. A liberação física continua falsa.
Ver [evidências](../evidence/continuous-v0110-benchy.json).

## Alternativas consideradas

- Refinar apenas camadas planas: reduz a escala, preserva a causa dos degraus.
- Compor com ContourZ: mistura dois campos e invalida a análise de deposição.
- Modificar o STL original: muda a peça entregue ao usuário e dificulta conferir
  as dimensões. A modificação fica restrita à cópia intermediária reversível.
- Alterar o Orca: exigiria manter um fork; não é necessário para esta prova.
