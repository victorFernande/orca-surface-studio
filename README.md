# Orca Surface Studio

Nome atual do projeto: **Orca Surface Studio** (anteriormente Orca Wave Studio).

A **0.16.3 experimental** permite enviar estudos com validação física pendente
após confirmar um **aviso amarelo de uso por conta e risco**. Mantém a conferência
do Preview, do arquivo e da conexão. O envio ao OctoPrint não inicia impressão
automaticamente. Veja o [fluxo e as capturas](docs/ENVIO_POR_CONTA_RISCO_V0163.md).

A **0.16.2 experimental** redistribui as camadas sem aumentar os limites do
perfil. Veja o [teste do Benchy e seus limites físicos](docs/ESPACAMENTO_AUTOMATICO_V0162.md).

A **0.16.1 experimental** destaca o aviso de risco, com título maior e texto
explícito sobre colisões, danos à impressora e supervisão durante toda a impressão.
Veja o [aviso e as capturas](docs/AVISO_RISCO_V0161.md).

A **0.16.0 experimental** inicia o cálculo diretamente na escolha de áreas,
mostra operação e tempo decorrido e separa **Preview** de **Conferir envio**.
Evita verificações repetidas sem alterar a precisão do campo C2.
Veja o [fluxo simples e a medição com o Benchy](docs/FLUXO_SIMPLES_V0160.md).

A **0.15.3** remove o menu **Mais opções** e a interface antiga, mantendo o
fluxo de quatro etapas. Acrescenta um seletor persistente com sete idiomas
para o banner e os avisos de Preview. Veja o [uso e os testes](docs/INTERFACE_AVISOS_V0153.md).

A **0.15.1** preserva todas as faces na visualização do modelo, com iluminação
suave nas curvas, arestas vivas e superfície opaca. O Benchy de referência é
exibido com seus 225.154 triângulos, em vez da redução anterior a 3.209.
Veja a [comparação e os testes da prévia](docs/VISUALIZACAO_MODELO_V0151.md).
A visualização também passou na [conferência direta no Orca Windows, com
capturas](docs/TESTE_ORCA_VISUALIZACAO_V0151.md), incluindo giro, zoom e seleção.

A **0.15.0 experimental** acrescenta giro da cópia e cadastro visual do
cabeçote por impressora, preservando o motor de trajetórias. O usuário aprovou
o formato do Benchy, mas relatou contato da carcaça traseira com a proa no
ensaio anterior. Novo ensaio e verificação nativa continuam pendentes.
**A publicação no Orca Cloud está bloqueada por solicitação do usuário.**
Veja o [uso, aviso e limites do mapa](docs/MAPEAMENTO_CABECOTE_V0150.md).

A **0.14.0 em estudo** substitui os campos sequenciais por um campo suave
conjunto, com verificação do interior das faces, material pelo perfil e
invalidação dos resultados antigos. O Benchy de 60 mm recebeu um ensaio
supervisionado específico com início aceito na SV06 e posterior relato de
contato da carcaça traseira com a proa. A liberação física dessa posição foi
reprovada. Veja o [registro e o uso em quatro passos](docs/CAMADAS_SUAVES_V0140.md)
e os [limites desse ensaio](docs/decisions/0021-supervised-benchy60-c2-trial.md).

A **0.13.0 experimental foi reprovada no Preview pelo usuário**: a redução
global de intensidade não manteve o alinhamento desejado do topo e do casco.
O ensaio físico não permanece ativo, e a estratégia não deve ser o padrão do
fluxo guiado. Veja o [registro da tentativa](docs/ADAPTACAO_PERFIL_V0130.md).

**Auditoria do Benchy anterior na SV06, com hipótese de 4 mm:** o arquivo 0.12.0 foi
reprovado para liberação. Foi reproduzida uma interferência condicional com
o CAD do sensor, e 52 camadas contêm trechos abaixo da altura mínima do perfil.
O envio continua bloqueado. Veja a
[verificação, suas hipóteses e a reprodução](docs/VERIFICACAO_BENCHY_SV06_4MM.md).

A **0.12.1 experimental** acrescenta **Enviar para impressora…** no próprio
Studio. O diálogo usa a conexão do perfil selecionado, identifica o arquivo e
abre mesmo para um Preview sem modelo na bandeja. O Benchy foi conferido até
esse popup, sem envio real. Suas pendências físicas continuam bloqueando o
envio. Veja o [manual e as capturas](docs/ENVIO_PERFIL_V0121.md).

A **0.12.0 experimental** ajusta o espaçamento, a seção do cordão e a extrusão
localmente. O Benchy recebeu 21 intervalos adicionais e a faixa aberta do casco
apareceu preenchida na conferência lateral do Preview. O fluxo permanece em
quatro passos. **A impressão continua bloqueada:** há alturas modeladas de
0,033 mm, abaixo dos 0,07 mm mínimos do perfil. Veja o
[teste, as capturas e os limites](docs/ESPACAMENTO_CORDOES_V0120.md).

A **0.11.1 experimental** reduz a amplificação das transições no casco do
Benchy: a maior inclinação emitida caiu de **52,7° para 17,6°**, confirmada no
Preview com o perfil da SV06. O fluxo continua em quatro passos. **Ainda há
lacunas e o indicador de espaçamento piorou; o Benchy não está liberado para
imprimir.** Veja a [comparação, as capturas e os limites](docs/CASCO_TRANSICOES_V0111.md).

A **0.11.0 experimental** muda o cálculo de **Peça inteira** para camadas em
coordenadas reversíveis das superfícies. O Orca fatia uma cópia intermediária
sem ContourZ e o Studio restaura os percursos e a extrusão ao formato original.
O fluxo permanece em quatro passos. Veja o [manual e o estado da validação](docs/CAMADAS_CONTINUAS_V0110.md).
A pintura localizada continua no método anterior. O estudo mantém a liberação
física desativada; não há promessa de compatibilidade com qualquer geometria.
**Na 0.11.0, o Benchy não foi aprovado:** o diagnóstico encontrou transições de
52,7° e espaçamento excessivo entre camadas. O Preview observado é de estudo;
o fluxo completo pelo plugin e a impressão continuam pendentes.

A **0.10.1** deixa **Peça inteira** disponível no passo Selecionar áreas,
incluindo o teto e as bordas compatíveis sem marcar cada região. O teste nativo
passou de 166 para 2.260 movimentos com Z variável, com máximo de 25,79° e a
malha original preservada. **Ainda há degraus residuais**: o pedido de eliminar
todos eles continua pendente. Veja o [teste, as capturas e o limite encontrado
no motor atual](docs/PECA_INTEIRA_V0101.md).

A **0.10.0** reduz os degraus com acabamento automático nas faixas selecionadas,
sem deformar a malha. No novo teste pelo plugin, a maior transição de extrusão
do Benchy caiu de **63,36° para 26,12°**, com camadas locais de **0,07 mm**.
Os quatro passos continuam iguais. Veja o [teste no Preview, com capturas e
limitações físicas](docs/ACABAMENTO_BENCHY_V0100.md). O resultado ainda não
certifica uma superfície sem degraus ou autoriza impressão física.

O [teste de uso completo com o Benchy na 0.9.1](docs/TESTE_USUARIO_BENCHY_V091.md)
registra seleção das bordas, estudo, reprodução e conferência de Z durante
extrusão no Preview, com capturas nativas. Nenhuma impressão foi iniciada;
o resultado mantém as limitações físicas e os degraus residuais.

A **0.9.1** renomeia a aba para **Surface Studio** e usa um ícone de trajetória
subindo a **30°**, com seta e bico, também no cabeçalho. Veja a
[captura nativa e os detalhes da atualização](docs/IDENTIDADE_V091.md).

A **0.9.0** abre em um [passo a passo de quatro etapas](docs/PASSO_A_PASSO_V090.md):
**selecionar modelo → selecionar áreas → estudar movimento → mandar para a bandeja**.
O modelo permanece visível durante o processo. O estudo fica no Studio; somente
no último passo o resultado abre no Preview do Orca. Esse botão não inicia impressão.
As opções anteriores continuam em **Mais opções**.

A 0.8.0 acrescenta a [seleção das áreas das paredes por clique em 3D](docs/SELECAO_PAREDES_V080.md).
É possível acrescentar/remover áreas e gerar o Preview pela mesma tela. O teste
de linha de comando confirmou contorno nas áreas escolhidas, mas encontrou
transições de aproximadamente 63°; **este Benchy ainda não está liberado para
imprimir**. A seleção, a geração e o Preview foram conferidos na interface nativa,
que também indicou trechos de 62,8° e manteve a advertência de impressão pendente.

A 0.7.1 usa uma [autorização de leitura única para o cache do Preview](docs/PERMISSOES_PREVIEW.md),
aprovada e salva pelo próprio Orca. Isso reduz pedidos por arquivo; não aprova
automaticamente janelas de segurança nem libera impressão física.
A versão 0.6.0 mantém os identificadores internos e os nomes de capacidades da
instalação anterior para preservar ativação, permissões e presets. O título do
estúdio já usa o novo nome.

## Superfícies locais — 0.7.0 em validação

A versão 0.7.0 acrescenta **Acompanhar superfícies locais**, usando o contorno
em Z nativo do Orca na malha original. Esse é o padrão de **Superfície curva**;
o alinhamento experimental ao teto continua como método avançado separado.
O objetivo é reduzir degraus nas bordas superiores curvas de cada novo arquivo,
sem deformar a peça ou repetir o mapa do teto do Benchy em outras regiões.

O candidato Benchy foi gerado com o perfil real, com XYZ/E nativos preservados
e conferência de 26 campos. O limite nominal calculado para o corpo do cabeçote
SV06 foi positivo, mas isso não certifica o bico, o cabeçote instalado ou a
deposição. **O arquivo continua sem liberação física**. O Preview foi conferido
na 0.7.1, incluindo Z variável na extrusão da borda da proa; ainda há degraus
residuais. Veja o [teste nativo com capturas](docs/VALIDACAO_NATIVA_V071.md)
e os [resultados e limites](docs/SUPERFICIES_LOCAIS_V070.md).

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
