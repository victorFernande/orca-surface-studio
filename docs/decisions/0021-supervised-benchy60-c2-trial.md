# ADR-0021 — Ensaio supervisionado do Benchy C2 de 60 mm

Status: início aceito pela SV06 em **22/11/2026, 00:36 (America/Sao_Paulo)**.
Resultado físico e acabamento ainda não avaliados. Complementa o ADR-0020;
não libera o produto para impressão geral.

## Autorização e hipóteses

O usuário pediu o Benchy original de 60 mm, com linhas contínuas seguindo as
superfícies, preservação do formato, teste no Preview e posterior início na
SV06. Rejeitou reduzir a escala e informou usar 4 mm como afastamento mínimo
do corpo do cabeçote. Após a análise condicional, confirmou novamente mesa
livre, PLA Voolt3D sem FP carregado e presença para acompanhar o início.

O ensaio usa essa hipótese de 4 mm fornecida pelo operador. Não é uma medição
independente nem confirmação do registro físico do CAD. A análise nominal do
corpo passa sob essa hipótese; o CAD original, sem deslocamento, permanece
inconclusivo para a margem de 0,5 mm. Contato bico/cordão, adesão, dimensões e
acabamento reais continuam sem calibração. Esses limites não foram removidos
nem convertidos em aprovação física no plugin.

## Arquivo conferido

O modelo mantém escala e formato, com rotação rígida de 90° na mesa. O perfil
é **Sovol SV06 0.4 nozzle -3DPrinter**, com o material escolhido pelo usuário.
O arquivo integrado teve nova fatia nativa e restauração única de XYZ/E.
O teto foi inspecionado em uma camada isolada e o casco em vista lateral.

O G-code completo, o pacote e o temporário do Preview foram idênticos:

`62c3d8f33ec2cd3f534b9e39de86d46f74cbb64336aead44d311e7b02d4e7789`

A conferência encontrou inclinação máxima de 29,3658° e alturas equivalentes
dos cordões apoiados de 0,094812–0,240000 mm, dentro de 0,07–0,28 mm. Os
segmentos restaurados atingem até 4,4722 mm/s em Z; a vazão na peça chega a
5,2584 mm³/s. A primeira camada permanece plana em 0,24 mm. Esses valores
são verificações do arquivo, não medições da deposição física.

Consultas `M851` e `M503`, sem movimentos ou aquecimento, reconfirmaram a
impressora ociosa e os limites ativos Z10 mm/s e Z100 mm/s² antes do teste.
Homing, nivelamento, purga e temperaturas do perfil foram preservados:
200 °C inicialmente, 195 °C nas demais camadas e mesa a 65 °C.

## Transporte e início

Uma cópia de transporte remove somente comentários, preservando a sequência
completa de comandos do Preview. O diário específico deste ensaio registra
intenção antes de cada tentativa e impede repetição automática de envio,
seleção ou início. A conexão é a do preset salvo com o nome exato; credenciais
e endereço não são publicados.

O primeiro e único upload não selecionou nem iniciou. A leitura de retorno
divergiu e interrompeu a sequência. A investigação constatou que o servidor
apenas acrescentou novamente 130 bytes de comentários do DisplayLayerProgress.
Foi feita reconciliação somente de leitura: a cópia recebida era exatamente
a cópia local mais aquele sufixo conhecido, com todos os comandos executáveis
idênticos. Nenhum plugin ou configuração do servidor foi alterado, e o
upload não foi repetido.

| Conteúdo | SHA-256 |
| --- | --- |
| Cópia local de transporte | `e9112e02607d60358940213663586db7b6b63e6b48ec6c88d1f3c0b661a99da1` |
| Cópia recebida, com comentários extras conferidos | `72e2d20c998e6d0c4cf0851625af48caaa90da18da3be09e480d9d3514072a96` |

Antes do início, o conteúdo recebido foi lido e conferido novamente. A
seleção foi enviada com `print=False`; o trabalho selecionado foi consultado
e correspondeu ao arquivo deste ensaio. Houve uma única solicitação de início.
O servidor aceitou e informou `Printing`, `printing=True` e o arquivo correto.
Isso comprova o início lógico observado, não a conclusão nem a qualidade da
impressão.

O envio e o início deste ensaio ocorreram pela API do OctoPrint, separados da
liberação geral do Studio. **Não validam o início pelo popup nativo do plugin.**
Os resultados do Studio continuam com `physical_validation=False` e
`print_allowed=False`; não foram alterados para contornar esse estado.

## Evidências e acompanhamento

O diário, reconciliação, consultas e cópias completas permanecem no diretório
privado de pesquisa do projeto. G-code, projetos, credenciais e endereços não
são incluídos no repositório público. O manual com capturas da inspeção está
em [CAMADAS_SUAVES_V0140.md](../CAMADAS_SUAVES_V0140.md).

Às 00:37:44, o servidor continuava em `Printing`, com o mesmo arquivo e sem
sinalizar erro. A mesa estava em 47,5 °C com alvo de 65 °C, e o bico em
149,31 °C com alvo inicial de 150 °C. Essa leitura confirmou o aquecimento
inicial; ainda não comprovou a primeira camada depositada.

Às **00:40:00**, a mesa estava em **65,29 °C** (alvo 65 °C) e o bico em
**202,01 °C** (alvo 200 °C). O trabalho correto continuava em `Printing`, sem
erro sinalizado, e a posição no arquivo havia avançado de 147 para 17.153
bytes. Essa leitura confirma aquecimento final e avanço do arquivo; não
substitui a observação da deposição e da adesão pelo operador.

Registrar separadamente avanço e observação física do operador.
Uma impressão concluída ou uma avaliação positiva desse Benchy não aprova
automaticamente outras geometrias, cabeçotes ou impressoras.
