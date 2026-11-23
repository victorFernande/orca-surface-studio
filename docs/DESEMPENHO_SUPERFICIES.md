# Desempenho das superfícies — otimização parcial

A meta solicitada é terminar o caminho completo em menos de 30 segundos.
**Essa meta ainda não foi atingida no Benchy.** Os resultados abaixo medem
etapas separadas e uma execução completa pela linha de comando do Orca.
Não medem o tempo do clique até a resposta dentro da interface.

## Mudanças

- Refinamento conforme por rodadas, compartilhando os mesmos vértices nas
  duas faces de cada aresta. Nenhum vértice original é movido ou removido.
- Certificados completos de derivadas e curvatura calculados em lote. Os
  intervalos de suporte preservam a convenção exata nos nós da spline.
- Um limite global completo aceita faces suficientemente pequenas; as demais
  recebem o limite local mais preciso. A tolerância continua igual.
- A separação por planos usa um filtro vetorizado e conserva a construção
  original das interseções e a ordem das faces.
- Consultas de coordenadas incluem viagens entre deposições. A conferência
  preliminar de arestas curtas prepara somente os pontos necessários.
- Altura normal e escala volumétrica compartilham uma consulta por célula.
  Os caches são limitados e invalidados quando os campos são substituídos.
- Propostas reutilizadas ainda têm referências verificadas novamente. Evita-se
  apenas repetir a mesma avaliação e a amostragem exclusiva do otimizador.

Não há nova dependência, redução da malha original para prévia, alteração do
perfil, ampliação de tolerâncias ou remoção da auditoria final de cordões.

## Medições locais de 23/11/2026

Windows, Intel Core i7-9700, Python 3.14. Comparação com o código `3fda61e`.
Os tempos são observações desta máquina, sem garantia para outros computadores.

### Preparação da malha

Mesmo Benchy de entrada com 225.154 faces, mesmo campo C2 e mesmo orçamento
de erro de 0,01 mm. A grade fixa de 0,198 mm foi usada somente para comparar
esta etapa; não é a grade final de 0,169 mm do caminho retido abaixo.

| Etapa | Referência | Otimizada |
| --- | ---: | ---: |
| Preparação da malha após leitura | 150,54 s | 21,05 s |
| Faces da cópia preparada | 553.014 | 521.678 |

A triangulação pode mudar. O refinamento conserva as superfícies de origem,
as quinas e o limite completo de interpolação; não é uma decimação.
O tempo não inclui planejamento frio, fatiamento, restauração ou empacotamento.

### Restauração de um fatiamento retido

O teste leu um fatiamento nativo já existente para isolar a restauração e a
auditoria. Não usou a nova malha acima nem executou o aplicativo.

- Restauração concluída: **121,31 s**.
- 464.783 segmentos de deposição.
- Alturas suportadas: 0,071540684–0,265717426 mm; perfil de 0,07–0,28 mm.
- Zero ocorrências abaixo/acima dos limites do perfil.
- G-code idêntico, byte por byte, ao resultado retido:
  `8ac3b0e376a530cffe8fc0fd71dc009ba828098d10374861ce4125c74f10a1d4`.

O caso mantém o modelo finito de cordão e as regras próprias de pontes e
ironing. Identidade digital não é uma qualificação de impressão física.

### Fluxo completo novo, sem proposta em cache

Uma segunda verificação partiu do 3MF retido, reconstruiu seu snapshot e
calculou um campo novo. Usou perfil e workspace próprios para executar o
OrcaSlicer instalado em segundo plano, sem controlar a janela aberta.

**Resultado: 503,12 s (8 min 23 s). A meta de 30 s foi reprovada.**

Principais custos, já incluídos no total:

| Etapa | Tempo |
| --- | ---: |
| Planejar coordenadas e preparar a cópia | 283,13 s |
| Duas passagens do otimizador, dentro da etapa anterior | 223,51 s |
| Dois fatiamentos nativos | 16,68 s |
| Restaurar caminho, extrusão e conferir cordões | 128,63 s |
| Auditar o caminho final | 11,83 s |

O resultado teve 465.582 segmentos de deposição. Uma redistribuição de 0,200
para 0,169 mm manteve os cordões suportados entre 0,071541478 e 0,266292116 mm,
com zero ocorrências fora dos limites originais de 0,07–0,28 mm. O orçamento
geométrico total permaneceu em 0,02 mm e o pacote final preservou os bytes do
G-code. SHA-256: `ba7aab3e21cd27a507dfa8c7af20475b45f468165fd805c8011d912f46608a8e`.

Este é um caminho novo, diferente do caso de restauração retida acima. Não
há uma comparação completa controlada com o código anterior: não se deve
inferir ganho percentual do fluxo inteiro a partir desses testes separados.
O projeto aberto não foi alterado, e não houve contato com a impressora.

### Triagem dos demais geradores

Geração das malhas em qualidade completa, importação medida separadamente,
sem navegador, interface do Orca, exportação ou impressão. Cada caso foi
executado duas vezes; tabela mostra o maior tempo da primeira execução.

| Gerador | Casos | Maior tempo |
| --- | ---: | ---: |
| Gear | padrão + 12 presets | 0,112 s |
| Vase | padrão + 12 presets, somente vaso | 0,129 s |
| Thread | padrão + 12 presets | 0,126 s |
| Box | padrão + 8 presets | 6,96 s |

Mason 86 foi corretamente recusado sem confirmação dimensional. No Box,
`screw_corner_standard`, `tool_rugged` e `pencil` demandaram 3–7 s para
reconstruir as malhas diretamente. O caminho usado pela interface já utiliza
recursos revisados e caches limitados: outro teste com
`BoxStudioController._preview_payload()` nos mesmos nove casos mediu até
**0,749 s na primeira preparação**, incluindo a codificação das malhas.
A reutilização do payload ficou abaixo de 0,001 s.

Esses tempos não incluem transporte para a WebView, renderização ou GPU.
O modelo reforçado envia aproximadamente 76 MB de malhas codificadas; sua
resposta visual em máquinas mais simples ainda precisa ser medida.

## Verificação e pendências

318 testes locais passaram com avisos tratados como erros. Incluem igualdade
entre certificados escalares e em lote, nós e seus vizinhos representáveis,
curvas completas, mudança de campos, volumes, orientação de arestas,
fechamento, Euler, cancelamento e limites do refinamento. Bundle independente,
variante `_any.py` e wheel foram construídos e inspecionados sem instalação.
Os mesmos testes e a construção passaram na
[CI de Windows, macOS e Linux](https://github.com/victorFernande/orca-surface-studio/actions/runs/45175387666).

A cópia preparada do Benchy também foi conferida: um componente, Euler -8,
zero arestas abertas/inconsistentemente orientadas e zero faces de área nula.
O Euler e o número de componentes foram preservados; os furos não foram fechados.

Ainda falta medir memória, confirmar aba/sidebar e cronometrar desde o clique
dentro do Orca. O fluxo completo isolado e a restauração retida excedem 30 s;
preparação rápida não significa caminho completo rápido. O planejamento frio
e o processamento de cada trecho continuam sendo os principais alvos.

Esta alteração permanece em revisão e não foi instalada, lançada ou publicada
no OrcaCloud. O checkout usado pelo aplicativo e seus arquivos foram preservados.
