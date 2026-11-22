# Registro da tentativa 0.13.0 — rejeitada

**Ensaio reprovado pelo usuário no Preview:** a redução global não manteve o
alinhamento solicitado do topo e do casco. O trabalho chegou a ser iniciado,
mas a SV06 foi confirmada ociosa e com aquecedores desligados após a rejeição.
Essa estratégia não deve ser usada como padrão do fluxo guiado.

Naquela tentativa, o Studio reduziu globalmente a intensidade quando o campo
completo exigia alturas incompatíveis com o perfil. Isso recuperou também os
degraus. A estratégia foi removida do produto; os números abaixo documentam
o experimento rejeitado, não a versão atual.

## O que foi experimentado

Em **Peça inteira**, o cálculo usava os limites de altura mínima e máxima do
perfil. O modelo original permanecia preservado; uma cópia intermediária era
refatiada e seus movimentos eram restaurados ao formato original.

Quando necessário, o resultado informava **suavização parcial**. Permaneciam
degraus: reduzir a intensidade do campo não equivalia a eliminar completamente
a escada em todas as bordas. O percentual apresentado media a deformação das
coordenadas de fatiamento, não a qualidade percentual do acabamento.

Uma contribuição apoiada abaixo da altura mínima ou acima da máxima impede a
conclusão dessa geração. O Studio não aumenta indiscriminadamente o material
para disfarçar lacunas. A seção de cada cordão e a extrusão são recalculadas.

## Separação das verificações

O cálculo pelo perfil limita o espaçamento. Ele não conhece automaticamente
as dimensões reais do sensor, do duto ou de um hotend modificado. Conferir o
Preview também não mede a folga física. A liberação geral de impressão pelo
plugin continua separada de um ensaio supervisionado especificamente autorizado.

## Validação de software

- 265 testes Python passaram, incluindo inversão, jacobiano, limites de
  espaçamento, preservação de furos e certificado sobre faces/quinas originais.
- Os quatro passos passaram no teste de interface com WebGL, desenho
  alternativo e largura de 390 pixels. Esse teste é de componente, não uma
  execução completa pelo Orca.
- O pacote Python e o arquivo instalável local foram gerados e importados.
- A instalação local foi atualizada preservando o estado existente. O Orca
  reiniciou com a aba **Surface Studio** disponível.

O ensaio rejeitado do Benchy utilizou uma cópia com intensidade de 0,08,
dentro do limite calculado automaticamente de aproximadamente 0,08697 para
esse projeto e seus perfis. Essa escolha mantinha parte pequena da adaptação;
não representa a solução final para acabamento sem degraus.

O início supervisionado foi aceito pelo servidor. Após a rejeição do resultado,
o pedido de cancelamento recebeu HTTP 409; a consulta seguinte confirmou a
SV06 em `Operational`, sem impressão ativa e com alvos dos aquecedores em zero.
Não se atribui a parada ao pedido de cancelamento recusado. O diário foi
marcado `REJECTED_PREVIEW_JOB_INACTIVE`, sem repetição automática.

O arquivo rejeitado não deve ser reimpresso. A correção seguinte está no
[ADR-0020](decisions/0020-smooth-joint-surface-phase.md).
