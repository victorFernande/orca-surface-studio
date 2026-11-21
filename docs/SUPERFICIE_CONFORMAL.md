# Superfície conformal — estudo geométrico

Em 19/11/2026, o usuário esclareceu que deseja acompanhar a superfície curva das
peças na Sovol SV06. O torus de 5 mm de altura é o primeiro exemplo dessa intenção.
Ondas senoidais acrescentadas ao perímetro continuam sendo um modo separado.

## Objetivo e referência

O modelo foi lido do Orca pela API pública, com os transformadores da peça e da
instância. A cópia contém o objeto 236, chamado Torus, com dimensões próximas de
25 × 25 × 5 mm e 48.464 triângulos. O perfil selecionado era Sovol SV06/Marlin,
bico de 0,4 mm e PLA. A análise desta etapa é geométrica e não calcula material.
O projeto em edição permanece preservado.

## Método

`build_surface_study(snapshot, object_id, settings)` recebe um retrato independente
do modelo e retorna `ProcessedResult`. `SurfaceSettings` configura passo,
espaçamento entre faixas, inclinação e um envelope hipotético de bico vertical.
Não existe suposição de cilindro ou ajuste paramétrico de torus.

As linhas de varredura cruzam as faces da malha. O maior Z acessível define a
superfície superior. Intervalos sem material, faces íngremes e descontinuidades
interrompem o percurso, preservando o furo. Os segmentos são certificados contra
os cruzamentos das faces, com tolerância vertical máxima de 0,02 mm e comprimento
mínimo de 0,15 mm. Coordenadas arredondadas são incluídas nessa verificação.

O estudo testa um limite inferior de folga para ponta plana e cone truncado,
condicionado à existência de material abaixo da superfície menos uma folga
vertical definida. Essa condição não representa um fatiamento real. O envelope
não é uma medição do hotend, ventilador ou estrutura da SV06. O limite padrão de
30° serve ao estudo; não é um limite físico aprovado para a impressora.

O G-code resultante contém somente movimentos XYZ, sem extrusão, aquecimento ou
homing. Sua finalidade é inspecionar o percurso. `print_allowed` permanece falso
e o agente não recebe aprovação, mesmo se houver uma confirmação antiga de
Preview. O visor do Studio apresenta o resultado; Preview nativo e Print ficam
indisponíveis nesse modo nesta versão.

## Resultado reproduzível

```powershell
python scripts/run_surface_study.py
```

Entrada: `study/evidence/torus-5mm/project-snapshot.json`.
Saídas: `surface-report.json`, `surface-study.gcode` e `surface-studio.html`, nessa
mesma pasta. O HTML funciona offline e permite girar, aproximar e percorrer os
pontos, mostrando XYZ.

O primeiro cálculo reteve 100 trechos e 1.184 segmentos, com Z de 4,63945 a
5,00000 mm, comprimento de 404,008 mm e erro vertical máximo de 0,007866 mm.
Não há extrusão. A faixa superior aceita não representa cobertura de toda a
superfície do torus. O relatório distingue trechos excluídos e hipóteses de folga.

## Trabalho necessário para impressão

É necessário combinar base e interior planares com camadas superiores conformais,
calcular apoio e espaçamento entre depósitos, transições, extrusão e vazão. A
geometria real do cabeçote, obstáculos e limites ativos da SV06 também precisam
ser confirmados. Os caminhos de viagem do estudo não constituem aprovação de
movimento físico. Nenhum envio à impressora real faz parte desta validação.

A identificação de regiões acessíveis e a combinação de camadas planares e
conformais seguem o problema descrito em
[Ahlers et al., 3D Printing of Nonplanar Layers for Smooth Surface Generation](https://tams.informatik.uni-hamburg.de/publications/2019/case_ahlers_2019.pdf).
Os parâmetros e as verificações deste protótipo são próprios e permanecem sujeitos
à validação física.
