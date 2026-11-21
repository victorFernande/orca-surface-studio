# ADR-0018 — Conferência de envio pelo perfil selecionado

Status: experimental; popup observado no Orca 2.5.1 em 21/11/2026.

## Contexto

O pacote somente fatiado abre corretamente no Preview, mas não contém objetos
de modelo. O caminho legado de Print retorna antes do diálogo quando o modelo
está vazio. A API pública do Plater não expõe esse diálogo ou um comando de
envio. Inserir uma peça fictícia ou iniciar um refatiamento para contornar a
condição comprometeria a correspondência entre Preview e arquivo processado.

O pacote de referência também omite o endereço/chave de transporte. Isso não
significa que o perfil salvo deixou de ter conexão: o novo ensaio confirmou
que o perfil vivo da SV06 a disponibiliza pela API de presets. Credenciais não
devem ser acrescentadas ao HTML, aos relatórios públicos ou ao pacote somente
para fazer o botão nativo aceitar o arquivo.

## Decisão

Abrir uma janela própria, pertencente ao Orca, pela API pública
`orca.host.ui.create_window`. O botão fica no Surface Studio e funciona também
quando o projeto atual contém somente trajetórias. Não modifica o Print nativo.

Ler uma cópia da conexão do preset editado na thread principal. Se um preset
importado omitir o destino, permitir somente a conexão lembrada ou salva com
o mesmo nome exato. Um perfil normal cujo endereço foi apagado permanece sem
destino. Nunca buscar outra impressora com um endereço disponível ou combinar
endereço e chave de perfis diferentes. Guardar esses dados somente em Python;
o HTML recebe nome, tipo e indicadores de configuração, sem endereço/chave.

O diálogo identifica a bandeja e o SHA-256 extraído do pacote atual. Um arquivo
aberto manualmente pode ser conferido, mas não recebe autorização física.
Somente um resultado vigente, com Preview conferido, perfil correspondente,
`print_allowed` e `physical_validation` verdadeiros pode habilitar envio.
Alturas abaixo do mínimo também recusam o envio. Mensagens da página não
podem fornecer ou elevar essas autorizações.

Abrir a janela não faz consulta de rede. O adaptador implementado é OctoPrint,
com envio explícito de arquivo sem seleção e sem início de impressão. Outros
agentes/protocolos ficam identificados como indisponíveis; não são convertidos
silenciosamente em OctoPrint. A abertura da conferência é independente desse
suporte. Antes do transporte, reconferir seleção, conexão completa, resultado,
pacote e hash. Não repetir automaticamente uma solicitação incerta.

## Consequências e evidência

O Benchy de 420 camadas abriu no popup com o perfil da SV06 e conexão
configurada. O hash do pacote coincide com o cache nativo do Preview. O envio
permaneceu desabilitado e nenhum transporte real foi executado. O teste de
arquivo autorizado usou exclusivamente o simulador e confirmou `select=false`
e `print=false`.

Foram aprovados 259 testes locais, três cenários do passo a passo e dois
cenários de componente do popup, incluindo contraste diante do tema injetado
pelo Orca. A conferência nativa e as limitações estão no
[manual de envio](../ENVIO_PERFIL_V0121.md).
