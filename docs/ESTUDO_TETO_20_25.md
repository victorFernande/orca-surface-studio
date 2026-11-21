# Estudo digital do teto e beiral — 0.5.0

O estudo está implementado e executado, com resultado **incompleto para
aprovação de acabamento e impressão**. Gerar Z inclinado não demonstra que o
material reproduzirá toda a superfície dentro de 0,05 mm.

## Conferência no Preview nativo

Após autorização do usuário, os seis casos de 20°/25° — planar, ZAA nativo e
regional — foram abertos no Orca normal. O gerenciador confirmou **Orca Wave
Studio 0.5.0, Activated**. O Orca estava fechado e iniciou com placa vazia;
não havia projeto aberto a salvar. Nenhum Print foi acionado.

Os pacotes regionais abriram diretamente no Preview, sem clicar em Fatiar.
Em vista frontal e com uma camada isolada, foram observadas estas sequências
durante extrusão positiva:

| Cupom | Camada do Preview | Passos | Z observado no comando (mm) |
|---|---:|---|---|
| 20° topo | 64 | 522 → 523 | 5,947468 → 6,043934 |
| 20° topo | 64 | 513 → 514 | 6,028856 → 5,931706 |
| 25° topo | 73 | 525 → 526 | 8,683010 → 8,807477 |
| 25° topo | 73 | 533 → 534 | 8,685644 → 8,562055 |

A face inferior também foi observada: papel Bridge na camada 55 do cupom
de 20° e na camada 64 do cupom de 25°, com comandos Z variáveis e E positivo.
Dez movimentos registrados na interface conferem com as linhas dos arquivos
originais. O marcador é o desenho genérico do Orca, não o envelope da SV06.
O valor Z único mostrado na régua de camadas não representa todos os pontos
da camada inclinada; a conferência usa o XYZ do marcador e o comando ativo.

As referências planar e ZAA mantiveram os degraus visíveis no beiral inferior.
O Orca mostrou avisos de incompatibilidade de filamento/mesa nos perfis frios
das referências; eles não foram removidos alterando temperaturas ou permissões.

Há uma limitação de integridade importante: a exportação nativa da referência
planar de 20° alterou comentários, data e miniaturas. Os 3.350 comandos
executáveis são iguais, mas o SHA-256 integral mudou. No projeto regional
somente fatiado, o botão Export G-code não abriu diálogo; não foi comprovada
a igualdade integral por reexportação nativa. Isso mantém a aprovação completa
da integração pendente. A captura pelo callback da versão 0.5.0 e o botão Print
nativo não foram exercitados nesta rodada.

O Orca foi deixado no regional de 25°, camada 73, passo 533, com marcador e
G-code visíveis. Imagens, observações e conferência estão em
`study/evidence/roof-study/native-preview/`, especialmente
`native-preview-audit.json` e `final-preview.png`.

## O que foi executado

Foram geradas 12 referências nativas no OrcaSlicer 2.5.1 para Windows:
cupons de 5°, 10°, 15°, 20° e 25° e o Benchy original, cada um com fatiamento
planar e Z Contouring separados. Todos passaram nas verificações de geração,
versão, perfil SV06 de 0,4 mm/PETG/camada 0,20, suporte normal e igualdade do
G-code com o conteúdo do pacote. Isso não é aprovação de cobertura.

Os cinco cupons também foram fatiados como cópias com as duas faces achatadas.
O motor regional restaurou os caminhos de modelo, suporte e viagens em XYZ,
com extrusão pelo volume da célula mapeada. Todos produziram G-code e pacote
para Preview com conteúdo idêntico. A base e os arquivos originais foram
preservados. As revisões de origem e hashes estão nos índices.

Os perfis de bancada são privados e frios: não executam aquecimento, homing,
estacionamento ou conexão real. PETG identifica o material de referência e o
cálculo, não um ensaio de deposição aquecido.

## Resultado e limites

No ZAA nativo, foram observadas extrusões não planares em partes do topo e das
paredes. Nos cupons de 10° a 25°, o papel Top Surface da região inclinada não
apresentou variação em Z, embora paredes variassem. Ele não demonstra a
correção conjunta da face inferior e do beiral.

Na auditoria regional, os erros normais máximos **amostrados no modelo estimado**
foram aproximadamente:

| Cupom | Topo (mm) | Face inferior (mm) | Aprovação |
|---|---:|---:|---|
| 5° | 0,3790 | 0,0195 | Incompleta |
| 10° | 0,3551 | 0,0389 | Incompleta |
| 15° | 0,3835 | 0,0580 | Incompleta |
| 20° | 0,2995 | 0,0767 | Incompleta |
| 25° | 0,3579 | 0,0947 | Incompleta |

Esses números são estimativas de cordões varridos com discos horizontais;
não são medições de uma impressão. O modelo não foi calibrado para PETG e
amostras não certificam o erro máximo entre pontos. Cobertura incompleta e
valores abaixo da tolerância em algumas amostras também não geram aprovação.

No testemunho do topo de 25°, o modelo de cordão encontra um microvazio XY de
aproximadamente 0,00674 mm e enxerga preenchimento 0,4 mm abaixo. A investigação
encontrou essa mesma cobertura nas trajetórias nativas do proxy; os caminhos
superiores estão mapeados corretamente. Isso não comprova um buraco físico.
Ver `regional/25/<execução>/witness-top-25.json`.

Os suportes são associados pelos rótulos nativos do objeto. Sua distância à
malha ideal e sua folga contra o **material estimado da peça** são relatadas
separadamente. Cobertura contínua, ordem de fabricação, remoção e contato com
o cordão em formação continuam sem certificado. O perfil real do cabeçote
está ausente: folga física **UNKNOWN**, sem capacidade declarada de 20°/25°.

A folga amostrada suporte → material estimado variou de 0,113 a 1,955 mm
(5°), 0,058 a 2,690 mm (10°), 0,006 a 3,451 mm (15°), −0,040 a 4,172 mm
(20°) e −0,082 a 4,853 mm (25°). Valores negativos em 20°/25° correspondem
a testemunhos de interseção **no modelo estimado**, com linhas do suporte e
da peça identificadas. Eles não foram ocultados pela distância positiva à
malha ideal nem considerados uma validação física.

O Benchy original é recusado pelo motor atual com
`REGIONAL_HOLES_OR_TOPOLOGY`: há furo, recorte ou fronteira interna. A seleção
manual de outra face não elimina a validação de topologia e transições. Não
há fallback automático para o topo parcial da versão anterior.

## Uso no Studio

1. Abra uma peça original, atualize a mesa e escolha **Superfície curva**.
2. Confira a região automática. Se necessário, escolha outra pela lista ou
   pelo mapa visto de cima. Topo, borda e face inferior são avaliados juntos.
3. O **Limite do estudo digital** restringe a geometria examinada; ele não
   representa o limite mecânico do cabeçote. Pequenas quinas nativas só são
   mantidas com a opção explícita de Preview.
4. Use **Preparar fatiamento conformal**. O Studio salva o original e abre uma
   cópia com ZAA desligado e suporte normal. Geometria incompatível é recusada.
5. Fatie no Orca e gere o percurso. Um resultado incompleto pode abrir no
   Preview, identificado como estudo e com impressão indisponível.

O mapa e o painel passaram em teste de componente isolado. Esse teste usa
uma ponte simulada e não comprova o fluxo completo de captura nativa. A
conferência visual nativa descrita acima verifica amostras dos pacotes prontos;
não substitui os gates de captura, integridade, transporte e impressão.

## Reprodução

No diretório `D:\Projects\orca-wave-studio`:

```powershell
python -m unittest discover -s tests -v
python scripts/run_roof_baselines.py
python scripts/run_regional_shell_study.py
python scripts/audit_roof_matrix.py
python scripts/run_study.py --output study/evidence/roof-study/transport-regression
python scripts/build_and_install.py --test
```

Os dois primeiros geradores usam o executável local do Orca em modo sem janela,
perfil privado e arquivos de referência. A auditoria apenas relê os resultados.
`reprocess_roof_matrix.py` regenera a transformação a partir de fatias nativas
persistidas, sem refatiar, preservando o índice anterior.

O transporte de regressão usa um cilindro sintético independente: geração,
pacote reaberto, extração pelo agente e recebimento no simulador apresentaram
o mesmo SHA-256. Não houve envio do cupom regional nem do Benchy a uma impressora.
O botão Print nativo desta versão não foi exercitado.

Evidências principais:

- `study/evidence/roof-study/baselines/baseline-index.json` — 12 referências.
- `study/evidence/roof-study/regional/regional-index.json` — cinco resultados.
- `study/evidence/roof-study/regional/assessment-index.json` — medições finais,
  hashes e impedimento do Benchy; fonte preferencial para números completos.
- `study/evidence/roof-study/ui/ui-validation.json` — componente da interface.
- `study/evidence/roof-study/transport-regression/study-results.json` — simulador.

## Revisão em frentes e referências

A execução foi dividida em geometria/motor, fatiamento/artefatos e revisão
independente. A revisão encontrou e motivou correções no catálogo do segundo
objeto e na comparação entre suporte e material depositado. Também foi
corrigida a emissão de Z de arestas curtas quando E não muda; há regressões
específicas para esses casos e para o Jacobiano abaixo da casca.

O [artigo de Ahlers](https://tams.informatik.uni-hamburg.de/publications/2019/case_ahlers_2019.pdf)
fundamenta a análise de camadas não planares e a distinção entre qualidade e
colisão. A projeção de cascas superiores descrita ali não resolve automaticamente
a face inferior deste estudo. O
[GCodeBending](https://github.com/CNCKitchen/GCodeBending/tree/73ff8766fe67cf2bd1e794c08736ccbd4201cc01)
inspira a distinção entre deformar deliberadamente um objeto e restaurar sua
geometria original. O
[FullControl](https://github.com/FullControlXYZ/fullcontrol/tree/588ecfe7551c7c75e6307ddfeac302f563346b4c)
permite descrever trajetórias e estados; ele não substitui o solucionador de
regiões, o modelo de deposição ou o envelope real do cabeçote. Nenhum código
externo desses projetos foi incorporado ao motor.

Para os vídeos enviados, foram consultados os materiais textuais disponíveis,
descrições, capítulos e código associado. Não foi obtida transcrição integral
nem realizada observação integral dos vídeos; não se apresenta essa etapa como
análise audiovisual completa.

O código nativo estudado é o Orca na revisão
[`eef7710`](https://github.com/OrcaSlicer/OrcaSlicer/tree/eef7710cb102fdb51a9bcdbd9efd61047f44774a).
O CAD nominal da SV06 tem procedência no
[repositório oficial Sovol](https://github.com/Sovol3d/SV06-Fully-Open-Source/tree/75f8a0da6ff822c67b6aff62cfa85c7a441e2271).
Ainda não foi convertido e registrado à ponta real do bico; nomes de peças e
dimensões de catálogo não foram usados para inventar esse registro.

## Impedimento para a etapa seguinte

O estudo comprova a geração reproduzível dos cupons, mas não aprova seu
acabamento dentro de 0,05 mm. São necessários um modelo de cordão verificável,
certificação contínua das superfícies/bordas, suporte e contato temporal, além
de uma transformação regional que represente os furos e as transições do
Benchy. Um envelope real do cabeçote registrado ao TCP e o ensaio físico
comparativo continuam sendo gates separados. O produto não está pronto para
imprimir qualquer modelo 3D.
