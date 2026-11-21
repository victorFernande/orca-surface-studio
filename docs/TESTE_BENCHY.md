# Teste do Benchy no Wave Studio

## Teste atual 0.5.1 — 21/11/2026

O [manual com nove capturas da interface](MANUAL_BENCHY.md) registra o teste
do Benchy original pelo Studio, com o perfil real da SV06 e PLA Voolt3D.
Depois da correção de desempenho do catálogo de regiões, o botão de preparação
recusou a topologia do teto e preservou o original. Preview conformal e impressão
física do Benchy não foram atingidos. As seções abaixo são registros históricos
de outros ensaios, incluindo deformação apenas do topo; não são aprovação do
fluxo atual nem do beiral completo.

## Atualização 0.4.1: teto local e prova no Preview

O usuário confirmou que o erro visível era o teto continuar planar. O código
em desenvolvimento agora identifica o teto entre Z=38,091 e 40,28 mm, mesmo
com a chaminé chegando a 48 mm. O arquivo do plugin 0.4.1 foi instalado em
disco preservando integralmente o estado de ativação. A instância aberta ainda
executa 0.4.0; a nova interface será carregada no próximo reinício do Orca.

A normalização removeu 19 faces de área nula, soldou quatro coordenadas
exatamente duplicadas e subdividiu 11 faces vizinhas para resolver junções
colineares. Nenhum vértice foi deslocado. O refinamento acrescentou 2.980
vértices sobre as faces originais, sem alterar a superfície ocupada. Uma borda
plana protege paredes, furos e detalhes; a distância é recalculada a partir
de toda essa borda antes de suavizar o campo, evitando picos em faces finas.

O ensaio estrito conserva o mínimo de 0,15 mm para qualquer deposição
deformada e **recusa** o Benchy na linha 114878. Há quinas nativas menores
que esse mínimo que não admitem união com erro de até 0,02 mm.
Registro: `study/evidence/benchy-roof/conformal-strict/generation-status.json`.

Uma opção separada, desativada por padrão, conserva essas arestas originais
com seus XY, ajusta Z/E pelo
mesmo campo e certifica o erro da corda. Ela não subdivide essas arestas.
Os segmentos de deposição recriados continuam com mínimo de 0,15 mm.
O usuário aprovou explicitamente a exceção para este teste no Preview. O
controle **Preservar pequenas quinas** está na interface 0.4.1 e é vinculado
às configurações da cópia preparada, sem habilitação automática global.

O arquivo experimental passou na auditoria automática:

| Verificação | Resultado |
| --- | --- |
| Extrusões do teto com variação de Z | 5.695 |
| Dessas, na função superfície superior | 1.567 |
| Superfície da camada nominal 40,2 mm | Z=39,606792 a 40,2 mm; 183 subidas e 196 descidas |
| Arestas curtas nativas efetivamente alteradas | 57; menor comprimento físico 0,0141469 mm |
| Menor segmento subdividido de deposição | 0,155944 mm |
| Maior erro de corda certificado | 0,0198794 mm |
| Região acima do teto, incluindo chaminé | Nenhum deslocamento Z de deposição; extrusão total preservada |
| Região abaixo da âncora | Extrusão total preservada dentro de 0,0001 mm de filamento |
| G-code e conteúdo do pacote de Preview | SHA-256 idêntico |
| Validação do arquivo na janela do Orca | Passou, com controle novamente autorizado pelo usuário |
| Geração pelos botões da interface 0.4.1 | Pendente de carregar a nova versão e repetir a captura |
| Impressão física | Bloqueada; sem transporte |

A cópia usa preenchimento sólido estreito retilíneo, sem a conversão automática
para pequenos laços concêntricos. Esse ajuste nativo é registrado no perfil de
Preview; nenhum percurso é apagado pelo transformador para fazê-lo passar.
O projeto original permanece intacto.

Evidências em `study/evidence/benchy-roof/conformal-v041/`:
`file-audit.json`, `conformal-report.json`, `warp-summary.json`,
`benchy-conformal.gcode` e `benchy-conformal.gcode.3mf`.
SHA-256 do resultado: `542048df26e989b50a36ba138be4982438592bb26b5204483651dace77129c3a`.
São arquivos de estudo; não há liberação para impressão física.

### Conferência nativa do resultado conformal

O pacote abriu diretamente no Preview da mesma janela, sem refatiamento,
com perfil **Orca Wave SV06 conformal bench**, bico 0,4 mm e material de
bancada **OWS Generic PLA Bench**. Essa simulação não valida PETG físico.
Na camada única 201, nominal Z=40,2 mm, o controle horizontal mostrou:

| Movimento nativo | Função | Z no marcador | Extrusão no comando |
| --- | --- | --- | --- |
| 900 | Top surface | 39,623 mm | E=0,00822564 |
| 901 | Top surface | 39,607 mm | E=0,0081173 |
| 903 | Top surface | 39,610 mm | E=0,00496561 |

Há descida e subida durante a deposição da mesma camada, confirmadas tanto
no marcador quanto nos comandos selecionados. A vista frontal ampliada
mostrou a trajetória variando em altura. As preferências de câmera usadas
para enquadrá-la foram restauradas: zoom sobre o mouse desativado e arrasto
esquerdo novamente em Rotate. O Preview ficou aberto nesse trecho.

O arquivo temporário efetivamente carregado pelo Orca também tem SHA-256
`542048df26e989b50a36ba138be4982438592bb26b5204483651dace77129c3a`,
igual ao G-code gerado e ao conteúdo do pacote. A observação está em
`conformal-v041/native-gui-observation.json`. O relatório automático permanece
como registro imutável da etapa anterior à GUI. Não foi clicado Print.

A instalação está registrada em `install-v041/installation.json`, com cópia
do bundle anterior para reversão. O novo bundle tem SHA-256
`179f56ddf7c30c2d5dd097bf84ff45b12920edf21615a7cb5523c0807b58bb0f`.
O teste de componente da nova interface confirmou que a opção começa
desmarcada, é enviada como booleano na preparação e permanece vinculada
à sessão de fatiamento. Isso não substitui o ensaio dos botões 0.4.1 no Orca.

Reprodução da proposta digital (não envia à impressora):

```powershell
python scripts/run_conformal_study.py --snapshot study/evidence/benchy-roof/project-snapshot.json --output study/evidence/benchy-roof/conformal-v041 --name benchy-conformal --retain-native-short-edges
python scripts/audit_benchy_conformal.py
```

Sem `--retain-native-short-edges`, permanece a recusa estrita. Os 117 testes
unitários passaram, incluindo proteção de detalhes altos, preservação da
superfície, limites da transição, certificação de cordas e exceção explícita.
Nenhum resultado deste ensaio aprova modelos arbitrários ou folga do cabeçote.

## Registro anterior: versão instalada 0.4.0

Data: 20/11/2026. Versão instalada: 0.4.0. Perfil: SV06, bico de 0,4 mm,
camada de 0,20 mm. Ensaios automático e na janela com OrcaSlicer 2.5.1,
sem contato com impressora ou impressão física.

## Resultado

**O fatiamento convencional passou. O modo de superfície curva ainda não
processa o teto do Benchy como solicitado.** O teste não aprova uso geral em
modelos arbitrários.

Foi usado o modelo de peça única do repositório original
[CreativeTools/3DBenchy](https://github.com/CreativeTools/3DBenchy), também
indicado pela [página oficial de downloads](https://www.3dbenchy.com/download/).
A geometria foi posicionada no centro da mesa, sem mudar a escala ou forma.

## Evidência observada

O arquivo 3MF original contém 112.569 vértices e 225.154 triângulos; sua caixa
mede aproximadamente 60 × 31 × 48 mm. O Orca gerou o pacote convencional e
G-code, encerrando o processo com código zero. Foram contadas 240 camadas.
Na inspeção dos movimentos XYZ absolutos/E relativos nativos, nenhum dos
90.798 movimentos XY com E positivo variou Z. Na faixa Z=35–40 mm, 772
movimentos de superfície superior também mantiveram Z constante. Isso é
fatiamento planar, não aprovação de um percurso conformal.

O modo conformal atual recusou a malha com **“Triângulo degenerado na malha.”**
O diagnóstico encontrou 19 triângulos de área nula no 3MF. A malha do pacote
exportado pelo Orca depois do fatiamento foi extraída e testada novamente:
a recusa persistiu. Também foi baixado o STL original para distinguir os
arquivos de referência: ele tem 225.706 faces, das quais 563 têm área nula
segundo o mesmo limiar numérico. Nenhum desses arquivos foi reparado ou
substituído silenciosamente para obter aprovação.

Há um impedimento geométrico independente da qualidade da malha. A âncora
global padrão é `Z máximo − 1,2 mm`, isto é, Z=46,8 mm neste modelo. A faixa
fica junto à chaminé; o teto abaixo dela não pertence à região de atuação.
Alterar somente esse valor não implementa uma seleção de superfícies locais:
é necessário tratar suas fronteiras, cavidades, paredes, transições e ordem
de deposição.

O leitor estrito do Studio também recusou o G-code convencional com
**“Recuperação de retração misturada à deposição do perímetro.”** Esse erro
é uma limitação do leitor do Studio; não significa que o fatiamento do Orca
seja inválido. A contagem de movimentos acima é somente um diagnóstico do
arquivo; não libera essa entrada para transformação ou transporte.

## Arquivos e reprodução

- `study/evidence/benchy-roof/capability-report.json`: resultados e limites.
- `study/evidence/benchy-roof/source.json` e `stl-source.json`: origem e hashes.
- `study/evidence/benchy-roof/project-snapshot.json`: modelo original posicionado.
- `study/evidence/benchy-roof/native-roundtrip-snapshot.json`: malha reexportada pelo Orca.
- `study/evidence/benchy-roof/native-baseline/benchy-planar.gcode.3mf`: Preview convencional.
- `study/evidence/benchy-roof/native-baseline/plate_1.gcode`: G-code convencional.
- `study/evidence/benchy-roof/native-gui-observation.json`: resultado observado na janela.
- `study/evidence/benchy-roof/native-gui-events.json`: eventos nativos da falha conformal.

O teste principal pode ser repetido com:

```powershell
python scripts/run_benchy_probe.py --slice-baseline
```

Os campos adicionais do relatório sobre a malha reexportada e a inspeção de
movimentos foram obtidos na análise complementar dos arquivos preservados.
O comando principal recria a análise inicial e o fatiamento de referência.

## Conferência na janela autorizada pelo usuário

Antes de abrir o Benchy, o projeto existente de um vaso com perfil Anycubic
foi salvo em `study/evidence/benchy-roof/before-benchy-gui-20261120.3mf`.
Essa cópia tem 12.935.201 bytes e sua integridade ZIP foi conferida.

O Benchy foi aberto com o perfil de teste SV06. No Studio, a peça recebeu
ID 152, com dimensões mostradas de 60 × 31 × 48 mm. A ação **Superfície
curva → Preparar fatiamento conformal** salvou o backup e terminou com a
mensagem **“Triângulo degenerado na malha.”** O evento nativo
`flat_model_failed` confirmou a mesma causa. Não foi criada uma malha
achatada nem um G-code conformal para o teto.

O fatiamento convencional foi executado também pelo botão nativo do Orca e
abriu no Preview com 240 camadas e altura máxima de 48 mm. Ao final foi
observada a camada isolada 186, Z=37,2 mm, na região do teto, com caminhos
planares de preenchimento. O usuário ajustou essa vista durante a conferência.
A captura do Wave Studio não estava configurada para esse fatiamento
convencional; ele não foi apresentado como uma captura conformal aprovada.

SHA-256 do 3MF original:
`74ec6ee3dba54a4973bad319c13e4d7df20a860ef82209912adceedeb8e8e643`.
SHA-256 do G-code convencional observado:
`aff572609421a8c10780d59185f7c850c93febae2fa83735c1b5c3e1a922f864`.

## Implicação para a próxima implementação

O caminho para esse caso é reconhecer superfícies superiores locais, escolher
o teto preservando a chaminé e as cavidades, gerar camadas/transições apoiadas
e verificar as trajetórias contra a geometria do cabeçote. A normalização da
malha e o tratamento de retrações também precisam de critérios e testes.

O vaso senoidal e a projeção de trajetórias sobre o teto têm funções diferentes.
Não foi aplicado o modo de vaso ao Benchy nem gerado um percurso sem extrusão
para apresentá-lo como impressão conformal. A conferência na janela foi
concluída após a autorização explícita do usuário para controlar a máquina.
