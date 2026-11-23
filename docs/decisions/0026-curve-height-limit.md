# ADR-0026 — Limite de altura da curva em milímetros

Data: 23/11/2026. Implementado na 0.16.4.

## Contexto

O usuário pediu um controle simples no passo 1, de 0,1 a 5,0 mm, em incrementos
de 0,1 mm. Uma altura isolada não descreve o contorno, os deslocamentos laterais
nem a orientação de uma carcaça de cabeçote.

## Decisão

Adotar 5,0 mm como padrão inicial e definir o limite como a diferença máxima
de Z dentro de uma camada curva. Separar esse limite do certificado de folga,
que continua falso enquanto não houver evidência física adequada.

Restringir o intervalo dos coeficientes do campo B-spline quando necessário,
preservando a transformação inversa e os critérios de alinhamento existentes.
Conferir a diferença de Z dos percursos emitidos em cada camada lógica nos
dois modos da interface. Não recortar Z nem deformar a peça para passar.

Incluir o valor na identidade do cálculo e do cache. Rejeitar valores fora
do intervalo, fora dos incrementos, nulos explícitos e configurações que não
conciliem a geometria com o limite. Resultados legados não recebem o novo
certificado por suposição. Mudar o controle exige recalcular.

## Consequências

O usuário ganha um limite geométrico simples. A região pintada ainda usa o
contorno nativo do Orca: se ultrapassar o limite, deve ser recalculada com
outra seleção ou valor. O limite não autoriza envio silencioso, não inicia
impressão e não transforma uma pendência física em aprovação.
