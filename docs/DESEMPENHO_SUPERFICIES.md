# Desempenho das superfícies — otimização parcial

A meta solicitada é terminar o caminho completo em menos de 30 segundos.
**Essa meta ainda não foi atingida no Benchy.** Os resultados abaixo medem
etapas separadas; não representam uma execução completa nova dentro do Orca.

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
`screw_corner_standard`, `tool_rugged` e `pencil` ainda demandaram 3–7 s.
Os demais casos do Box ficaram abaixo de 0,70 s. Essa triagem não substitui
medição da resposta visual na aba ou sidebar.

## Verificação e pendências

318 testes locais passaram com avisos tratados como erros. Incluem igualdade
entre certificados escalares e em lote, nós e seus vizinhos representáveis,
curvas completas, mudança de campos, volumes, orientação de arestas,
fechamento, Euler, cancelamento e limites do refinamento. Bundle independente,
variante `_any.py` e wheel foram construídos e inspecionados sem instalação.

Ainda falta executar o fluxo completo com a nova cópia, desde o clique até o
pacote final, medir memória e confirmar aba/sidebar dentro do Orca. O caminho
retido ainda excede 30 s sozinho; preparação rápida não significa caminho
completo rápido. O otimizador frio, eventuais novas distribuições de camada,
fatiamentos e auditorias também precisam entrar no orçamento final.

Esta alteração permanece em revisão e não foi instalada, lançada ou publicada
no OrcaCloud. O checkout usado pelo aplicativo e seus arquivos foram preservados.
