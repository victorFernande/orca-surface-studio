# Verificação do Benchy na SV06 — hipótese de 4 mm

Data: 21/11/2026. Plugin instalado: 0.12.1. OrcaSlicer: 2.5.1 Windows.

**Resultado: o arquivo atual não foi liberado para envio ou impressão.**
O cálculo encontrou uma interferência condicional com o sensor e trechos
abaixo da altura mínima do perfil. Nenhum arquivo foi enviado, nenhuma
impressão foi iniciada e o G-code aprovado visualmente não foi alterado.

## Hipótese informada pelo usuário

O usuário indicou usar **4 mm** como afastamento conservador entre a ponta do
bico e as partes do cabeçote. Esse valor foi usado como hipótese de geometria,
sem convertê-lo em uma medição ou registro confirmado do cabeçote instalado.
O usuário também informou que não há capa de silicone; ela foi excluída do
estudo do corpo. O contato do próprio bico com o depósito continua separado.

O arquivo verificado é `HOLD-bead-v0120.gcode`, de 420 camadas, 48 mm,
perfil **Sovol SV06 0.4 nozzle -3DPrinter** e PLA Voolt3D. Seu SHA-256 é
`15889cc23c002c9af889d6e6f9f381e659137f6cc352baa248a1e8c4d746b3be`.

## Corpo do cabeçote e material anterior

Primeiro foi calculado o limite vertical conservador sobre 825.823 movimentos
lineares do corpo da impressão, incluindo deslocamentos. Em alguns momentos,
há material anterior até 10,314526 mm acima da posição atual do bico. Com um
piso de corpo de 4 mm, o limite global resulta em -6,314526 mm.

**Esse número é inconclusivo, não uma profundidade de colisão.** Ele inclui
material distante em X/Y. Por isso foi necessária uma busca espacial com a
montagem CAD nominal da [fonte oficial da Sovol](https://github.com/Sovol3d/SV06-Fully-Open-Source/tree/75f8a0da6ff822c67b6aff62cfa85c7a441e2271).

O CAD coloca a parte mais baixa do sensor a aproximadamente 2,173 mm da ponta
nominal. Para também testar a hipótese mais favorável de 4 mm, o registro do
TCP foi deslocado em 1,827019 mm ao longo do eixo do bico. Isso mantém os
sólidos e a posição lateral relativa do cabeçote, mas é **um registro
hipotético**, não uma alteração feita na máquina ou uma medida de sua montagem.

Foi encontrado um ponto do depósito anterior estritamente dentro do sólido
CAD do sensor nesse registro de 4 mm. A conferência não se limita à
sobreposição de caixas: o classificador do sólido retornou **IN**.

| Dado | Movimento atual | Material anterior |
|---|---|---|
| Linha no G-code HOLD | 700.627 | 695.180 |
| Camada lógica, contagem da interface | 142 | 141 |
| Função | Parede interna | Parede externa |
| X, Y | 92,512; 113,347095 mm | 119,217; 97,318 mm |
| Z do bico/ponto estimado | 11,863003 mm | 15,8875136 mm |

O ponto anterior fica 4,0245106 mm acima do bico atual e também coincide
lateralmente com o sensor no CAD. Esse valor não é uma medição da penetração
ou da menor distância entre superfícies. A posição do cabeçote instalado e a
forma real do filamento extrudado continuam sem registro/calibração física.

O material é aproximado por pontos no interior do cordão estimado: extremos
e meio de movimentos anteriores, a uma profundidade de
`min(0,02 mm; 0,2 × HEIGHT emitido)`. O ponto encontrado pertence a uma camada
lógica anterior já concluída. A busca foi amostrada; um resultado sem ponto
não aprovaria a peça. Um ponto positivo é suficiente para reprovar **esse
modelo nominal/estimado** para liberação automática.

## Altura de camada e material

A leitura das seções efetivamente emitidas no G-code encontrou:

| Verificação | Resultado |
|---|---|
| Altura equivalente dos cordões apoiados | 0,033047–0,24 mm |
| Faixa do perfil | 0,07–0,28 mm |
| Movimentos apoiados abaixo do mínimo | 65.611 |
| Camadas com esses movimentos | 52 |
| Distribuição por função | 37.977 internos, 25.959 externos, 1.675 de preenchimento |
| Camadas com conflito para simples multiplicação das alturas atuais | 30 |

Os 65.611 movimentos desta leitura não são o mesmo indicador das 66.032
ocorrências amostradas do cálculo da 0.12.0. As seções emitidas representam
alturas equivalentes por segmento; o cálculo anterior também considera
subcontribuições dentro deles. Pontes e ironing foram mantidos separados.

Na camada 106, por exemplo, as alturas atuais variam de 0,034252 a 0,208112 mm.
Multiplicá-las por pelo menos 2,0437 levaria o mínimo a 0,07 mm; o máximo só
admite um fator de 1,3454 para permanecer até 0,28 mm. Portanto, uma simples
escala proporcional de altura/material não resolve essa camada. Essa análise
não prova que todo novo planejamento ou refatiamento seja impossível; indica
que a distribuição local precisa ser recalculada. Não foi feito um novo
refatiamento nesta auditoria.

A inclinação máxima anterior de 17,6143° e a velocidade Z calculada de
4,4721 mm/s estão dentro dos limites usados no estudo. Isso não substitui a
conferência do sensor: um componente afastado lateralmente pode atingir uma
região mais alta mesmo quando a inclinação de cada movimento está limitada.

## Reproduzir a interferência

O [registro do ponto](evidence/benchy-sv06-floor4-witness.json) contém as
coordenadas, linhas e hash do componente CAD. O script de reprodução
reconstrói os pontos lendo os movimentos de origem e classifica novamente
o sólido. Ele recusa outro G-code, outro componente ou ponto inconsistente.
Não tem operação de impressora nem opção de autorização.

No ambiente local de CAD usado neste projeto:

```powershell
$env:PYTHONPATH = 'D:/Projects/orca-wave-studio/.venv/Lib/site-packages'
.research/sv06-physical-preflight/cad-env/Scripts/python.exe scripts/verify_head_witness.py `
  --gcode .research/benchy-clearance/bead-v0120/HOLD-bead-v0120.gcode `
  --assembly .research/sv06-physical-preflight/assembled-components.json `
  --record docs/evidence/benchy-sv06-floor4-witness.json `
  --cad-root .research/sv06-physical-preflight `
  --output .research/benchy-readiness-v0121/replayed-witness.json
```

O script exige numpy e OCP. O G-code, o manifesto da montagem e os BREP usados
na auditoria são artefatos locais do estudo, não acompanham um clone público
limpo. Seus hashes são conferidos antes de aceitar a reprodução. O ensaio
retornou `REPRODUCED_NOMINAL_INTERFERENCE`, mantendo `physical_validation`
e `print_allowed` falsos.

O [resumo sanitizado da auditoria](evidence/benchy-sv06-readiness-4mm.json)
separa o limite vertical inconclusivo, a interferência condicional reproduzida
e as alturas abaixo do perfil. A versão instalada e o arquivo permanecem
inalterados. Ainda é necessário replanejar os percursos e o espaçamento local
e, depois, qualificar deposição e cabeçote. O sucesso do cupom de 25° não
qualifica automaticamente esse Benchy completo.
