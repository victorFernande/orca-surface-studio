# ADR-0019 — Adaptação limitada pelo perfil

Status: **rejeitada**. Removida do fluxo e do código do produto; substituída pelo estudo do ADR-0020.

## Contexto

O Benchy da verificação anterior tinha cordões apoiados abaixo do mínimo de
0,07 mm do perfil e uma interferência nominal com o sensor. Aumentar E ou
multiplicar todas as alturas daquele G-code não resolve a distribuição de
camadas. O campo completo comprime algumas regiões enquanto expande outras.

## Alternativa experimentada e rejeitada

Planejar os campos sem produzir uma malha utilizável nessa etapa. Compor o
campo inversível original `F` e a identidade por `F_a.z = z + a*(F.z-z)`.
O novo jacobiano vertical é `1-a+a*J`; a inclinação XY é multiplicada por `a`.
Escolher automaticamente a maior intensidade que satisfaz limites globais
conservadores de altura normal mínima e altura vertical máxima, incluindo a
extensão XY completa dos campos. Reservar 10% abaixo da altura máxima do perfil.

Construir uma **nova cópia do sólido original**, com inversão conferida e
refinamento certificado sobre faces e quinas originais. Refatiar essa cópia
com os perfis efetivos e restaurar uma única vez XYZ e E. Não aplicar o campo
reduzido ao G-code já não planar. Preservar a divisão de erro: até 0,01 mm na
malha e o restante do orçamento total de 0,02 mm nos movimentos emitidos.

Conferir também os cordões emitidos; uma contribuição apoiada abaixo do
mínimo ou acima do máximo impede a conclusão dessa geração. A necessidade de
densificação adicional interrompe o modo reduzido nesta versão, evitando
herdar uma garantia de alinhamento que ele não oferece.

## Consequências

A intensidade controla a adaptação das coordenadas, não uma porcentagem de
qualidade. A suavização é **parcial**: podem reaparecer degraus e uma superfície
pode atravessar várias faixas nativas. O Studio deve apresentar essa condição,
sem reutilizar a afirmação de que todas as referências cabem em uma camada.
O ensaio não manteve o alinhamento solicitado do topo e do casco. Reduzir a
deformação aproximava novamente as camadas do fatiamento plano. Por isso essa
alternativa não atende ao objetivo e não deve ser selecionada automaticamente.

Os limites do perfil não descrevem o sensor, o duto ou o bico instalado.
A seleção automática não libera impressão. A folga do corpo, os movimentos
de aproximação e a deposição física continuam sendo verificações distintas.
Um ensaio supervisionado autorizado não torna o produto aprovado para produção.
