# Camadas contínuas no Surface Studio — estudo experimental

O modo **Peça inteira** passa a calcular as camadas em relação às superfícies
da peça. O objetivo é percorrer as bordas inclinadas da proa e da popa e o teto
do Benchy na mesma camada lógica, em vez de voltar periodicamente a um plano
horizontal. O modelo original continua preservado.

**Estado da validação:** implementação experimental, com 239 testes locais
aprovados e verificação dos quatro passos em três condições de interface.
A geração completa e o Preview do Benchy ainda estão em validação. Esses
testes não são uma liberação para impressão física.

## Como usar

1. Coloque o modelo na mesa, escolha a impressora e o filamento no Orca e abra
   **Surface Studio**. Selecione o modelo e avance.
2. Em **Selecionar áreas**, use **Peça inteira** para o novo cálculo. A opção
   **Escolher na peça** continua disponível com o acabamento localizado anterior.
3. Clique **Continuar** e **Estudar movimento**. A peça permanece visível enquanto
   o cálculo prepara e fatia uma cópia privada. Aguarde a conclusão.
4. Confira o resultado e clique **Mandar para a bandeja**. Se o Orca apresentar
   o diálogo de importação, escolha **Open as project** para abrir o pacote já
   fatiado no Preview.

### Passos conferidos no Orca

Seleção do Benchy original, com o perfil da SV06 e o PLA Voolt3D selecionados:

![Selecionar o modelo no Surface Studio](images/continuous-v0110/01-modelo.jpg)

Seleção de **Peça inteira** para estudar teto e bordas compatíveis juntos:

![Escolher peça inteira](images/continuous-v0110/02-peca-inteira.jpg)

Um único botão inicia o estudo; a peça original permanece visível:

![Iniciar o estudo de movimento](images/continuous-v0110/03-estudar.jpg)

No Preview, examine uma camada isolada nas bordas e no teto. O Z precisa variar
durante a extrusão dentro dessa camada. Deslocar uma camada horizontal inteira
ou apenas reduzir a altura das camadas não comprova o novo comportamento.

## O que o cálculo preserva e verifica

- Cópia intermediária reversível, com XY preservado, furos e primeira camada plana.
- Perfil de impressora e filamento selecionado, incluindo início/fim, limites
  de movimento, vazão e transporte nativo.
- ContourZ desligado na cópia: há um único mapeamento de volta ao formato original.
- Referências de faces paralelas alinhadas e núcleos de superfície na mesma faixa
  de corte, sem apagar os pequenos chanfros presentes no STL.
- Certificados geométricos das faces e das quinas, com orçamento inicial conjunto
  de 0,02 mm para a cópia da malha e as cordas emitidas.

O ajuste de uma superfície tem resíduos próprios. Sua medida não é apresentada
como porcentagem da peça lisa. Paredes verticais, pequenas regiões não usadas
como referência e superfícies inferiores não recebem uma promessa de acabamento
sem marcas. Uma máscara pintada ainda usa o método localizado anterior.

## Impressão

Este estudo não inicia impressão. O resultado mantém a liberação física
desativada até conferir cabeçote, contato do bico, deposição, suportes e ordem
dos percursos. Aproximadamente 8 mm de afastamento informados pelo usuário e o
sucesso do cupom de 25° não certificam automaticamente o Benchy completo.

Veja a decisão técnica em [ADR-0015](decisions/0015-continuous-surface-coordinate-layers.md).
