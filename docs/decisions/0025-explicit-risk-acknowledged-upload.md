# ADR-0025 — Envio com confirmação explícita dos riscos

Data: 23/11/2026. Implementado na 0.16.3. Altera a política de envio do
[ADR-0018](0018-selected-printer-send-review.md), a pedido do usuário.

## Contexto

O aviso de que deposição, transições e cabeçote ainda não estavam validados
impedia o envio de todo estudo experimental. O usuário pediu que essa pendência
física deixasse de bloquear o envio e fosse apresentada em um aviso amarelo,
permitindo que ele decidisse continuar por sua conta e risco.

## Decisão

Remover somente a exigência de `physical_validation=True` e `print_allowed=True`
da revisão de envio. Esses campos continuam registrando o estado real do estudo;
a confirmação do usuário não os altera nem certifica a impressora.

Ao abrir **Conferir envio**, mostrar uma única janela com o arquivo, o perfil
selecionado, um aviso amarelo de risco de colisão, danos e perda da peça,
**Cancelar** e **Entendi os riscos, enviar arquivo**. O texto pede conferir as
folgas, acompanhar toda a impressão e nunca deixar a máquina sem supervisão.
Os avisos seguem os sete idiomas existentes.

O botão confirma o risco somente para aquela janela e aquele arquivo. O host
exige confirmação booleana verdadeira e um identificador aleatório daquela
janela. Nenhuma autorização permanente é gravada. Pedidos repetidos ou tokens
de outra janela não iniciam outra transferência.

Permanecem os bloqueios técnicos: Preview sem conferência vigente, pacote ou
hash alterado, perfil/conexão diferente, falta de conexão/chave, adaptador ainda
não implementado e cordões fora dos limites de altura do perfil. A confirmação
dos riscos não remove essas verificações.

## Transporte e consequências

O comportamento de transporte continua sendo **upload sem seleção nem início**
no OctoPrint. A janela informa isso expressamente. Não foi acrescentado um
comando de iniciar impressão, nem repetição automática após erro ou resposta
incerta. A conexão e as credenciais ficam no host Python, fora da página.

O bloqueio físico anterior passa a ser uma decisão explícita do operador.
Isso não resolve a interferência prevista no CAD do Benchy, não transforma
um Preview em validação física e não libera a publicação no Orca Cloud.

## Verificação

305 testes locais passaram, incluindo confirmação ausente/falsa, janela antiga,
duplo clique, mudança de conexão/pacote e upload ao simulador com bytes idênticos,
`print=False` e `select=False`. A interface foi conferida em 700 e 390 px,
incluindo cores sob o tema injetado pelo Orca, um único aviso e nenhum acesso
de rede durante a abertura. Os sete idiomas passaram nas páginas e no painel.

Conferência nativa da versão instalada em andamento; nenhuma impressão real
será iniciada para testar a janela.
