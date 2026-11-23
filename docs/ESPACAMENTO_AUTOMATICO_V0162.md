# Surface Studio 0.16.2 — espaçamento dentro do perfil

Data: 23/11/2026. Versão experimental, sem publicação no Orca Cloud.

## Uso

O fluxo permanece: escolher modelo → escolher áreas → **Calcular e preparar
Preview** → **Ver no Preview do Orca**. Não foi acrescentado um controle de
altura para o usuário compensar erros manualmente. O Studio lê os limites
mínimo e máximo do perfil selecionado no Orca.

Em **Peça inteira**, o cálculo pode agora redistribuir as camadas da cópia de
fatiamento e fatiar novamente quando os cordões apoiados saem desses limites.
Isso não modifica o modelo original nem aumenta os limites do perfil.

## Correção

O Benchy falhava no primeiro cordão acima de 0,28 mm. Corrigir somente esse
primeiro ponto deixava outros trechos do casco com alturas maiores. Uma
varredura de proposta percorre agora os caminhos nativos da peça inteira,
excluindo pontes, ironing e outros objetos. Ela estima os extremos pelo mesmo
modelo de distância normal finita usado na deposição.

A proposta balanceia altura mínima e máxima. A nova distribuição mantém o
mesmo campo de superfícies e precisa passar novamente pelos certificados das
faixas de referência. A cópia é dividida nos nós dos mapas antigo e novo antes
da troca afim; assim, a mudança não consome um novo orçamento geométrico.

O passo das camadas da cópia usa múltiplos de 0,001 mm, compatíveis com o XYZ
emitido pelo Orca. A tolerância do leitor de G-code planar não foi relaxada.
São permitidas no máximo quatro tentativas de fatiamento. Sem uma solução,
o cálculo termina com erro e não entrega um G-code final.

**A amostragem orienta a proposta; não aprova o arquivo.** A restauração final
continua verificando todos os segmentos emitidos, extrusão, largura, alturas,
inclinação, velocidades, formato e igualdade do G-code no pacote do Preview.
Os limites do perfil e suas tolerâncias anteriores foram preservados.

## Evidência automatizada

- 304 testes locais aprovados: `python -m unittest discover -s tests -q`.
- Pacote independente e wheel 0.16.2 gerados; importação fora do host aprovada.
- Reprodução offline da captura nativa do Benchy de 60 mm, perfil SV06,
  camada nominal de 0,20 mm, primeira camada de 0,24 mm, limites 0,07–0,28 mm.
- Proposta inicial: 828.451 amostras; extremos de 0,083728 a 0,326835 mm.
- Redistribuição da cópia: 0,200 → 0,169 mm, mesmo campo, referências
  novamente verificadas, novo fatiamento nativo.
- Auditoria final emitida: 0,071540684–0,265717425 mm; zero ocorrências fora
  dos limites. Pontes e ironing mantêm o modelo nativo de seção.
- SHA-256 dessa reprodução offline:
  `3b067a181d1af00ac6aa891ec0f1d3010c172b8d97b82cbb94dceaddb30caf08`.

A reprodução usou a malha refinada capturada para isolar o espaçamento.
Ela não substitui uma execução nova pelo plugin, a conferência visual no Orca
ou a verificação do cabeçote instalado. Seus arquivos continuam marcados como
não qualificados para impressão física.

## Validação nativa e física

0.16.2 instalada, Orca reiniciado com autorização e projeto preservado.
O Benchy de 60 mm já está com a proa voltada para a frente SOVOL; giro adicional
do Studio mantido em 0°. Cálculo novo iniciado pelo botão do plugin.

Conferência final do Preview, folga da carcaça traseira e eventual envio físico
ainda em andamento. Nenhuma dessas aprovações é inferida dos testes locais.
