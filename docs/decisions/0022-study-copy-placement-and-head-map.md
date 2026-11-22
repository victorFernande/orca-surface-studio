# ADR-0022 — Posição da cópia e mapa separado do cabeçote

Status: experimental; fotos, medidas e nova conferência nativa pendentes.

## Contexto

Após o início do ensaio C2 de 60 mm, o usuário relatou que a carcaça traseira
encostou na proa. Ele aprovou o formato e os cálculos das trajetórias e pediu
preservá-los, acrescentando mapeamento do cabeçote e rotação da peça. A
hipótese de transladar todo o CAD para obter um afastamento mínimo de 4 mm
não demonstrou a folga real desse conjunto e não será reutilizada como
qualificação de segurança física.

## Decisão

Aplicar uma isometria em Z às instâncias selecionadas de uma cópia do
retrato original, em torno do centro XY dos limites efetivos. Manter malhas,
triângulos, escala, Z e objetos não selecionados. Conferir a mesa antes de
fatiar, gerar nova fatia e restaurar as trajetórias pelo mesmo motor.
O resultado conserva a revisão original como vínculo com a interface e
registra separadamente a revisão processada e a transformação aplicada.

A API pública do Orca é de leitura para o modelo. A cópia é uma operação
explícita na interface; não há setter suposto nem edição escondida do projeto
original. Mudar a orientação invalida o estudo e a pintura anterior.

Guardar os retângulos XY e alturas relativas à ponta do bico em armazenamento
local do plugin, por nome exato de perfil e diâmetro do bico. Validar limites
finitos e ordenados; rejeitar uma gravação se o perfil mudou. Não converter
desenho, altura isolada ou aprovação de trajetória em um certificado do
cabeçote completo. O mapa atual é visual, sem escolha automática de posição
ou detector de colisões. As marcações de qualificação permanecem falsas.

Acrescentar o aviso solicitado, sem diálogo ou etapa extra. Manter uma
política de publicação desativada no projeto, conferida antes de qualquer
acesso de rede do publicador Orca Cloud. Não existe opção de força no comando.

## Consequências

O usuário mantém quatro passos e pode avaliar orientações sem mudar o núcleo
C2. Ainda precisa conferir o conjunto real; o cadastro não descobre dimensões
de hardware pelo nome do perfil. Fotos identificam peças, mas não dispensam
escala e registro dos eixos. A combinação mapa/percurso e a recomendação
automática só devem ser implementadas como verificação própria, sem usar
uma heurística de direção como autorização de impressão.

O ensaio anterior tem contato físico relatado, sem atribuir a parada ao
assistente. Não será repetido automaticamente. Ver detalhes e evidências em
[MAPEAMENTO_CABECOTE_V0150.md](../MAPEAMENTO_CABECOTE_V0150.md).
