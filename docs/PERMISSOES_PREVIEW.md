# Permissão única para o cache do Preview — 0.7.1

O Studio não aprova suas próprias permissões e o controle automatizado não
responde às janelas de segurança do Orca. A primeira decisão continua com o
usuário. Para evitar um pedido diferente a cada G-code temporário, a 0.7.1
declara uma autorização de **somente leitura** para:

```text
%TEMP%\orcaslicer_model\*
```

O Orca mostra o caminho absoluto correspondente durante o carregamento do
plugin. Se o usuário concordar e aprovar, o próprio Orca salva a decisão. Os
novos arquivos dessa pasta não precisam de aprovação individual enquanto o
caminho e a autorização salva permanecerem iguais. Mudança de ambiente,
revogação de acesso ou remoção do estado de permissões pode exigir nova decisão.

O escopo inclui a árvore de temporários de modelos do Orca, não apenas o G-code
atual. Não inclui o restante de `%TEMP%`, Documentos, Downloads ou todo o disco.
Não é solicitado acesso de escrita nem acesso irrestrito. O instalador não
edita o arquivo de permissões. Arquivos negados pelo host continuam negados.

A declaração usa apenas o caminho absoluto informado pelo ambiente, sem sondar
a pasta criando arquivos e sem chamar o armazenamento do plugin durante a
descoberta. Caminho ausente, relativo ou ambíguo conserva o comportamento de
permissão por arquivo em vez de ampliar o acesso silenciosamente.

As verificações de processo, placa, nome do cache, ciclo de abertura e SHA-256
continuam ativas. A autorização de pasta permite ler; não significa que um
arquivo diferente pode ser aceito como resultado. O plugin também não transforma
essa autorização de leitura em aprovação de impressão.

Quando uma janela de permissão estiver aberta por mais de três minutos, a
0.7.1 pausa o prazo de conferência enquanto aguarda a decisão do usuário.
Ao voltar ao Studio, retoma a mesma identidade de importação e compara os
conteúdos. Arquivo alterado, projeto trocado e nova recusa continuam impedindo
a validação. O tempo de processamento sem pedido de acesso pendente continua
limitado; não há repetição automática indefinida dos pedidos de permissão.

O seletor de método também passa a usar pintura HTML explícita, evitando o
texto claro sobre fundo branco observado no WebView nativo do Windows.

## Estado

Implementação e testes preparados. A instalação e a autorização única na janela
do Orca ainda precisam ser concluídas pelo fluxo acompanhado. A janela antiga
de acesso a um arquivo específico não é aprovada por essa alteração de código;
ela precisa ser respondida diretamente pelo usuário.
