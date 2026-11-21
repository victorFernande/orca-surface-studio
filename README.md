# Orca Surface Studio

Nome atual do projeto: **Orca Surface Studio** (anteriormente Orca Wave Studio).
A versão 0.6.0 mantém os identificadores internos e os nomes de capacidades da
instalação anterior para preservar ativação, permissões e presets. O título do
estúdio já usa o novo nome.

## Superfície com o perfil selecionado — 0.6.0

Coloque a peça na placa, confira impressora e filamento no Orca, abra o Studio,
escolha **Superfície curva** e clique **Gerar superfície e abrir Preview**.
O botão prepara uma cópia, chama o próprio fatiador do Orca em segundo plano,
reconstrói Z/extrusão e abre o resultado na janela nativa. O original fica salvo.

A área central mostra o modelo antes do cálculo e continua visível se houver
erro. Ajustes de referência, inclinação e amostragem ficam recolhidos em
**Ajustes da superfície**. Veja o [fluxo e os limites atuais](docs/FLUXO_SUPERFICIE_V060.md).

O novo motor aceita a topologia do teto do Benchy, incluindo suas aberturas.
Ele usa coordenadas alinhadas ao plano de referência do teto e conserva a
curvatura residual da malha. Bico, filamento, camadas, mesa, velocidades e vazão
vêm do perfil selecionado; aquecimento, retrações, macros e transporte nativo
são preservados na cópia. Não há valores de máquina escolhidos pela marca.

A compatibilidade geral é o objetivo; nesta versão o contrato é XYZ linear,
uma peça, uma instância e um volume sólido. Esteiras e recursos que exigem
outro referencial ou comandos ainda não interpretados recebem diagnóstico.
Geometria digital válida não certifica folga do cabeçote nem deposição física.

O cupom experimental de 25° foi impresso na SV06 com PLA Voolt3D sem FP e o
usuário relatou resultado perfeito em 21/11/2026. Esse ensaio usou preparação
isolada; não equivale a validar modelos arbitrários ou o fluxo inteiro do
plugin. O [manual histórico 0.5.1 do Benchy, com capturas](docs/MANUAL_BENCHY.md)
registra a correção de desempenho e a recusa da preparação pela topologia do
teto naquela versão. Na 0.6.0, o Benchy chegou ao Preview pelo botão integrado,
com integridade confirmada e Z variável durante a extrusão. Não foi enviado à
impressora. Veja o [registro atual com capturas](docs/FLUXO_SUPERFICIE_V060.md#teste-real-pelo-botão-do-studio).


Plugin de trajetórias senoidais para OrcaSlicer 2.5.1 no Windows. A série 0.5
acrescenta o **estudo de topo, face inferior e beiral**, com cupons de 5° a 25°,
seleção automática de região e correção pelo mapa. O estudo gera trajetórias
inclinadas, mas ainda não aprova acabamento ou impressão. O motor retangular
0.5 recusava o Benchy por topologia; o novo fluxo 0.6 usa uma transformação do
sólido completo. Veja [resultados históricos](docs/ESTUDO_TETO_20_25.md).

O modo **Vaso senoidal** continua combinando ondas radiais em X/Y e subida/descida em Z
durante a extrusão. A intensidade cresce suavemente até o topo, com a região
inferior preservada. O resultado desta versão é destinado somente ao Preview.

## Vaso senoidal

1. Deixe uma peça na placa, abra o Studio e selecione **Vaso senoidal**.
2. Use **Preparar vaso no Orca**. O Studio salva uma cópia do projeto em seu
   armazenamento e prepara uma parede, base de três camadas e topo aberto.
3. Clique em **Fatiar** no Orca.
4. Ajuste **Intensidade das ondas**, **Ondas por volta** e **Começar ondas**.
   Use **Gerar e abrir Preview**. Ajustes da onda não exigem novo fatiamento.

O modo aceita contornos radiais simples de raio variável, inclusive a pequena
abertura de costura do Orca. As voltas seguem o fatiamento convencional; não são
uma hélice contínua. Alças, contornos múltiplos, preenchimento na região ondulada
e reentrâncias incompatíveis são recusados. Perfis com comandos fora do dialeto
linear de bancada também são recusados, sem ignorar comandos desconhecidos.
Veja [cálculo e validação](docs/MODO_SENOIDAL_COMBINADO.md).

Os modos anteriores **Onda XY**, **Onda Z** e **Superfície curva** continuam
disponíveis. O modo Z isolado mantém seu piloto com cilindro de parede única.

O estudo geométrico isolado de **Superfície curva**, incluído na versão 0.2.0, estuda percursos conformais
sobre a malha superior da peça. É independente das ondas senoidais. O torus real
de 25 × 25 × 5 mm foi usado como referência; o estudo preserva o furo e exclui
regiões incompatíveis com as hipóteses de inclinação e bico. Esse modo ainda não
gera deposição, base ou interior imprimíveis e não habilita Print. A preparação
conformal da versão 0.5.0 é um estudo separado de casca pareada, descrito acima. Veja
[o estudo de superfície](docs/SUPERFICIE_CONFORMAL.md).

O agente de bancada envia exclusivamente ao simulador identificado de loopback.
A cópia do fluxo integrado preserva o agente nativo configurado no perfil ativo.
A integração completa pelo botão Print e a impressão física ainda não estão validadas.
Consulte [o relatório do estudo](docs/ESTUDO_INTEGRACAO.md).

## Instalação persistente no Orca normal

O perfil padrão é diferente dos perfis isolados do estudo. A instalação persistente fica em
`%APPDATA%\OrcaSlicer\orca_plugins\orca_wave_studio\orca_wave_generator.py`.
O arquivo de ativação inicial está nessa mesma pasta. Permissões são solicitadas
pelo próprio Orca; o instalador não copia nem concede permissões do perfil de teste.

Para atualizar a instalação normal:

```powershell
python scripts/build_and_install.py --test --install-user --enable-new
```

Feche e abra o Orca normal para usar o novo código. Em uma primeira instalação,
o Orca poderá solicitar a ativação/permissões. O instalador preserva byte por byte
um `.install_state.json` já existente, incluindo as capacidades que você ocultou.
Os artefatos universais ficam em `dist/`.

## Ocultar a aba e manter o ícone

No gerenciador **Plugins**, expanda **Orca Surface Studio** e desmarque somente a
capacidade **Estúdio de Ondas Senoidais** (Pages). Mantenha
**Orca Wave Studio • Painel** (Script), **Orca Wave Studio Capture** e o agente ativos.

O ícone/comando do painel continua disponível. Ele abre o painel na primeira
execução, oculta na seguinte e volta a exibir quando acionado novamente. Dentro
do painel há também **Ocultar painel**. A página oferece **Abrir painel**.
Não desative o plugin inteiro para esconder sua página.

Essa escolha é persistida pelo Orca e mantida nas atualizações. Para plugins de
terceiros que tenham somente Pages e nenhum comando independente, o Orca 2.5.1
não oferece ocultação total mantendo o mesmo ícone da página. A alternativa nativa
é **Preferences → General → Plugins → Visible plugin pages = 1**, que reúne as
páginas em uma aba compartilhada. Outros plugins não são alterados pelo Wave Studio.

## Fluxo do protótipo

1. Adicione as peças na mesa do Orca e abra o Studio ou seu painel.
2. Atualize a mesa e escolha os objetos. Clique no nome de uma peça para editar
   seus parâmetros; a caixa de seleção determina se ela recebe o efeito.
3. Analise as sugestões. Cópias vinculadas compartilham parâmetros.
4. Use **Preparar captura**. Isso habilita comentários de objetos e seleciona a
   capacidade de captura no processo de teste. A seleção de outro processador
   de fatiamento não é combinada automaticamente nesta versão.
5. Clique em **Fatiar** no Orca. A captura precisa corresponder à placa e à revisão.
6. Gere o G-code com ondas. O resultado é escrito em uma cópia e a abertura do
   pacote fatiado na mesma janela respeita os diálogos normais de salvar/cancelar.

O acesso ao cache temporário depende da auditoria do host. O lançador de estudo
coloca TEMP/TMP sob o diretório de dados do perfil isolado, sem pedir acesso a
árvores arbitrárias. No Orca normal, confirme diretamente os pedidos de leitura
dos arquivos de fatiamento e Preview. Se a auditoria interromper o callback
enquanto aguarda essa confirmação, o Studio mantém a sessão por até três
minutos e tenta concluir a mesma leitura ao voltar ao Studio após o diálogo.
Enquanto o Studio estiver sem foco, ele não repete o pedido. Nova recusa, alteração
do arquivo, mudança de projeto ou cancelamento invalidam a captura. O plugin
não concede permissões nem aceita um arquivo de outra sessão.

## Reproduzir o estudo offline

O motor, o empacotamento, o receptor e seus testes usam a biblioteca padrão de
Python. A leitura nativa das matrizes/malhas também declara NumPy no pacote,
instalável pelo host na primeira configuração.

```powershell
python -m unittest discover -s tests -v
python scripts/run_study.py
python scripts/build_and_install.py --test
```

`study/evidence/offline/` recebe o cilindro, o G-code, o pacote fatiado, a
demonstração HTML e o relatório JSON. Os estados `PASS_OFFLINE` e
`PASS_SIMULATOR` não equivalem a aprovação na interface nativa.

## Perfil isolado e receptor para Print

```powershell
python scripts/prepare_study_profile.py
python scripts/build_and_install.py --install-root study/isolated_profile/orca_plugins --enable-new
python scripts/serve_study.py
python scripts/prepare_study_profile.py --launch
```

O receptor informa a porta local escolhida e grava sua conexão de bancada no
armazenamento do plugin de teste. Só ele recebe os uploads; não os encaminha.
Para encerrar o receptor, use Ctrl+C no terminal que o iniciou.

## Distribuição

Licença MIT. O workflow OIDC está preparado, mas não publica enquanto a variável
`ORCA_WAVE_PUBLICATION_APPROVED` não for `true`, houver uma release compatível
com a versão e o repositório estiver vinculado ao plugin no OrcaCloud.
macOS e a impressão física pelo fluxo completo do plugin permanecem pendentes.
O ensaio físico isolado do cupom de 25° está registrado separadamente acima.
