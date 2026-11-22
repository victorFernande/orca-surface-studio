# ADR-0020 — Camadas por um campo suave conjunto

Status: implementação experimental; aprovação do Benchy e liberação física separadas.

## Problema

O usuário precisa de linhas contínuas que acompanhem a inclinação local,
com espaçamento regular e formato preservado. Campos sequenciais comprimiram
camadas perto de transições. A redução global de intensidade da tentativa
0.13.0 recuperou folga, porém recuperou também os degraus; foi rejeitada.

## Decisão

Propor um único campo `phi(x,y,z) = z + delta(x,y,z)`, com `delta` representado
por B-splines cúbicas de continuidade C2. Resolver conjuntamente as referências
superiores compatíveis e a suavidade do campo. Impor margem nula nas bordas e
na base para conservar a primeira camada plana. Manter `d(phi)/dz > 0` por
limites completos dos coeficientes derivados; inverter Z por método protegido.

Uma segunda proposta acrescenta restrições nos pontos críticos da superfície
e do interior sólido, amostrado por raios que preservam as cavidades.
O otimizador só propõe: seu estado de convergência não aprova o arquivo. As
referências incluem interiores de faces subdivididas a até 1,2 mm em XY.
Intervalos completos da Hessiana em cada subtriângulo original devem provar
que pelo menos 90% da área da referência cabe em uma faixa nativa;
resíduos e pequenos chanfros originais não são achatados no objeto final.

O núcleo de quantis ponderados ajuda a escolher a grade, mas não substitui
esse certificado completo. O identificador `reference_certificate_version=2`
invalida o resultado anterior que examinava somente vértices. Restrições nos
pontos de material mantêm reserva para interpolação; os limites finais do
cordão são avaliados na fatia emitida, não deduzidos apenas desses pontos.

Fatiar uma nova cópia nas coordenadas `phi`, com o perfil selecionado no Orca,
e restaurar XYZ e E uma única vez. Não deformar um G-code já não planar.
Refinar faces e quinas usando limites completos da Hessiana C2 e do inverso,
reservando até 0,01 mm para a cópia e o restante de 0,02 mm para as cordas.
Separar os segmentos nos pontos de mudança da grade Z composta.

O passo alvo permanece 0,4 mm e o mínimo dos segmentos recriados 0,15 mm.
Movimentos nativos menores só são preservados pela exceção explícita existente
e por seu certificado geométrico. Não diminuir esses limites para concluir
uma geração que falhou.

Recalcular a seção de deposição e E com o espaçamento finito entre camadas.
Recusar contribuições apoiadas fora dos limites de altura do perfil. Pontes
e ironing mantêm seu modelo nativo. Os testes atuais desse modelo verificam
contribuições discretas, não certificam a deposição física contínua.

## Cache e interface

O cache guarda somente uma proposta do campo. Sua chave inclui a malha em
coordenadas efetivas, altura nominal/inicial, limites de camada, inclinação,
extensão das referências e revisão do planejador. Reutilizar exige validar
o campo e as referências; cópia geométrica, fatia e movimentos são conferidos
novamente. Não reutilizar autorização física, arquivo liberado ou credenciais.

O usuário conserva quatro passos: modelo, áreas/peça inteira, estudar movimento,
mandar para a bandeja. Resultados dos kernels antigos e resultados sem o
certificado de referência atual exigem novo estudo.
A pintura localizada continua no método local existente.

Inversões e derivadas podem ser calculadas em lote por camada para reduzir
o tempo. Consultas adaptativas ausentes do cache numérico usam o mesmo método
escalar protegido; esse cache não muda a função nem autoriza uma impressão.

## Conferência nominal do corpo do cabeçote

Uma rotina independente acompanha todo movimento linear etiquetado e acumula
envoltórias superiores dos cordões já depositados e do cordão atual. Caixas
do corpo do cabeçote são varridas sobre esse material. Um pai conservador só
dispensa seus filhos quando prova a margem exigida. O limite global de altura
também só evita a consulta espacial quando prova essa mesma margem: um valor
positivo microscópico não basta. Sobreposição é inconclusiva; não comprova
colisão. O estudo usa margem nominal de 0,5 mm e não altera a liberação física.

## Limites

O núcleo de referência não é toda a malha. Alturas aceitas no perfil não
significam espaçamento perfeitamente constante, ausência de colisão ou
imprimibilidade de qualquer modelo. Uma caixa do cabeçote sobreposta à
envoltória de material é inconclusiva; folga nominal positiva depende do
modelo e do registro físico fornecidos. Bico e formação do cordão permanecem
verificações distintas. O resultado geométrico continua `print_allowed=False`.

Dependências numéricas: NumPy, SciPy e OSQP, declaradas tanto no script PEP 723
quanto no wheel. Referências de implementação: [NdBSpline](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.NdBSpline.html),
[BSpline](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.html)
e [API Python do OSQP](https://osqp.org/docs/interfaces/python.html).
