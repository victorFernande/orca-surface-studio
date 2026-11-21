# Estudo de integração — resultado observado

Data: 19/11/2026. Versão do protótipo: 0.2.0. As observações nativas do cilindro
foram realizadas durante a série 0.1.1; o estudo conformal é a adição da 0.2.0.

## Evidência e limites

| Etapa | Resultado | Evidência |
|---|---|---|
| Registro e página nativa | Observado na GUI | O Orca carregou as capacidades da versão 0.1.0 no perfil isolado e exibiu a aba do Studio. |
| Leitura de peça real | Observado na GUI | O Studio reconheceu a esfera adicionada à mesa, seu ID, uma cópia e dimensões de aproximadamente 22 × 22 × 22 mm. Isso não valida o modo Z para esferas. |
| Captura nativa após Fatiar | Observado na GUI | Cilindro de 40 × 40 × 8 mm capturado automaticamente, com ID da peça, placa e revisão da interface confirmada antes/depois do fatiamento. Configuração efetiva registrada separadamente. A matriz de múltiplas peças/placas continua pendente de observação nativa. |
| Motor X/Y e Z | Aprovado em bancada | Testes de coordenadas/extrusão, cilindro sintético, limites geométricos e seleção por objeto. Sem validação física do depósito. |
| Pacote somente fatiado | Onda Z observada no Preview real | O cache identificado no log do visualizador contém os mesmos 573.722 bytes e SHA-256 `ed2f94dc6570d7d005098286dd0a7b92061febb55efb87366b09bb0fbe2cf6f2` do resultado gerado. Na camada 20, o marcador do nozzle mostrou Z 4,115 mm descendo até 3,961 mm. A confirmação assíncrona reforçada do plugin ainda precisa de novo ciclo nativo. |
| Agente e OctoPrint simulado | Aprovado em bancada | Conexão, prontidão, mesa, SHA-256, POST único, rejeição, cancelamento e recibo incerto exercitados no receptor local. |
| Botão Print do Orca | Pendente | A chamada do agente foi exercitada por Python. O acionamento pelo diálogo nativo não foi concluído. |
| Impressão física | Não executada | Nenhum arquivo ou comando de impressão foi enviado à SV06. |

O usuário interrompeu uma rodada de controle com Escape. Uma autorização posterior
permitiu a continuação. O último Print abriu o diálogo, mas não havia máquina com
acesso local registrado; não houve envio pelo botão. A impressão física não foi
executada.

Em seguida, o usuário esclareceu que deseja acompanhar a superfície curva,
usando um torus de 25 × 25 × 5 mm. Esse cálculo foi separado das ondas Z:
[estudo de superfície conformal](SUPERFICIE_CONFORMAL.md). Nesta etapa ele produz
somente percurso geométrico, com Print bloqueado.

## Artefatos reproduzíveis

Execute `python scripts/run_study.py`. O relatório
`study/evidence/offline/study-results.json` registra a versão, parâmetros,
medidas do motor e os hashes da geração, reabertura do pacote, extração pelo
agente e recebimento no simulador. O arquivo tem 1.080.455 bytes no cenário
atual de dois cilindros, com somente o objeto 100 selecionado.

Os testes incluem placas distintas, objetos homônimos e cópias, mudanças de
transformação e configuração de volume, geração antiga terminando depois de
outra geração, cancelamento e preservação de estado de extrusão. Um arquivo
já processado pelo Studio é recusado como entrada de nova deformação.

Os testes do navegador usaram Chromium isolado. Eles verificaram WebGL 2,
reprodução XYZ, camada isolada, parâmetros individuais, invalidação de
resultados, painel compacto, contraste com o tema do host e ações do painel.
Não foram usados como substituto do teste de Print no Orca.

## Correções durante a implementação

- A instalação somente no perfil de teste desaparecia quando o Orca era aberto
  pelo perfil normal. A versão 0.1.1 foi instalada também no perfil padrão com
  estado inicial de ativação, sem copiar permissões.
- O estado de capacidades existentes é preservado integralmente em atualizações.
- Saídas são separadas por captura, parâmetros e hash; um worker antigo não
  substitui o pacote de outra placa com os mesmos bytes de G-code.
- Configurações por volume e cópias não imprimíveis foram incluídas nos testes.
- Alterações externas invalidam a aprovação mesmo durante uma abertura pendente.
- O painel pode ser ocultado e reaberto pelo comando Script independente da página.

## Próximos critérios de aprovação nativa

1. Na versão instalada, capturar um novo fatiamento do cilindro de parede única;
   repetir com duas peças, cópias e segunda placa selecionada.
2. Confirmar leitura do cache sob a auditoria do host e correspondência com a
   revisão efetiva. Uma leitura negada permanece erro explícito.
3. Abrir o pacote gerado, isolar uma camada e observar a subida e descida com
   extrusão. Confirmar ausência de refatiamento e testar salvar/cancelar.
4. Acionar Print pelo agente do Studio com receptor local identificado e comparar
   os quatro hashes, incluindo a trajetória realmente aberta no viewer.
5. Incluir um pós-processador que modifique os bytes e confirmar recusa antes do POST.
6. Antes de qualquer ensaio físico, confirmar os limites ativos e a geometria real
   do cabeçote. Velocidade, aceleração e tempo atuais são estimativas comandadas.

## Fontes fixadas

OrcaSlicer 2.5.1, commit `eef7710cb102fdb51a9bcdbd9efd61047f44774a`.

- [Modelo e transformações](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/slic3r/plugin/host/PluginHostModel.cpp).
- [Grafo de fatiamento](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/slic3r/plugin/host/PluginHostSlicing.cpp).
- [Agentes Python](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/slic3r/plugin/pluginTypes/printerAgent/PrinterAgentPluginCapability.cpp).
- [Capacidades independentes](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/slic3r/GUI/PluginsDialog.cpp).
- [Agrupamento de páginas](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/slic3r/GUI/Preferences.cpp).
- [Deposição não planar, Ahlers et al.](https://tams.informatik.uni-hamburg.de/publications/2019/case_ahlers_2019.pdf).
