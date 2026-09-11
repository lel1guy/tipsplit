# Porque é que o TipSplit funciona como funciona

[English](WHY.md) · **Português (PT-PT)** · [README](../README.pt-PT.md)

Decisões de projeto com as respetivas razões, para ninguém ter de adivinhar mais tarde — e
para uma versão futura não as desfazer em silêncio.

## 1. Só horas, sem pesos por função

Um empregado de bar e um ajudante com as mesmas horas recebem o mesmo dinheiro. A função é
um **rótulo** ao lado do nome, não um multiplicador.

Porque a discussão às 2 da manhã nunca é «devia receber 1,2×». É «porque é que o meu número
é aquele número?» — e as horas são a coisa nessa folha que ninguém contesta. No momento em
que um espaço quer pesos, isso é outro produto com outro problema de confiança.

## 2. Um adiantamento pertence sempre a uma semana

Os vales são dinheiro que alguém levou *durante* uma semana, por isso é essa semana que o
paga. Não existe um pote de «dívida» flutuante que ande à deriva entre semanas, e o registo
lê-se agrupado por semana, com subtotais.

Um adiantamento sem semana significaria que o dinheiro é descontado num sítio qualquer — e
quem o levou não o pode conferir com nada.

## 3. A conferência do pote existe porque as folhas de cálculo se desviam

A aplicação mostra *pool todo dividido* ou *split + €X em vales* antes de guardar. Essa
conferência existe porque uma folha de Excel real com um pote de €555 mostrava €554.95: o
arredondamento independente de cada pessoa perde cêntimos, e ninguém dá por isso até estar
um mês de dias de pagamento errado.

O TipSplit arredonda todos para baixo (para ninguém receber a mais) e distribui os cêntimos
que sobram pelo maior resto, para que os quinhões somem o pote **até ao cêntimo** — um
invariante com testes por trás.

## 4. Um adiantamento acima do quinhão de alguém é permitido, e é sinalizado

Bloqueá-lo significaria que o gerente não pode ajudar alguém numa semana má. Por isso a
aplicação permite-o, imprime `€X vale acima do ganho (dívida ao pote)` a vermelho, arredonda
o líquido para zero e deixa o espaço acertá-lo na semana seguinte. A regra é: nada fica
escondido, e a pessoa vê a mesma sinalização que o dono vê.

## 5. Uma semana fechada pode ser reaberta — com um motivo

Os erros acontecem; impedir as pessoas de corrigir só faria com que as correções se
fizessem fora dos registos. Por isso, reabrir é possível, exige um motivo escrito, e esse
motivo fica no registo de alterações com data e hora.

As correções continuam possíveis. O silêncio não.

## 6. A fórmula impressa é sem arredondamento

`470,40 € × 32 h ÷ 448 h = 33,60 €` — nunca o valor arredondado multiplicado de volta, que
está errado por um cêntimo e faz o papel parecer errado a quem o conferir com uma
calculadora.

Um comprovativo que falha a conferência da calculadora destrói exatamente a confiança para
a qual foi impresso.

## 7. A tabela da equipa mostra os adiantamentos, não só o líquido

Sem a coluna dos adiantamentos, uma pessoa com um adiantamento vê um número mais baixo do
que `hours × rate` e conclui que a casa ficou com a diferença. Essa leitura errada está a
uma captura de ecrã de distância, e é o mal-entendido mais caro que esta aplicação pode
causar.

Por isso a tabela mostra horas, quinhão, adiantamentos e líquido, mais a linha
`pool − advances = to pay now`.

## 8. A sessão de um membro da equipa é filtrada no servidor

A página da equipa nunca recebe a escala nem os adiantamentos de mais ninguém — o servidor
devolve apenas a parte dessa pessoa. Esconder isso no navegador era estar a um «ver
código-fonte» de distância de todos os salários da equipa.

O mesmo raciocínio vale para a assinatura do PIN: transporta o **papel e o id da pessoa**,
por isso um cookie de equipa não pode ser alterado para um de dono.

## 9. A interface é só em português (PT-PT)

As pessoas que introduzem horas à hora de fechar falam português, e uma interface meio
traduzida é pior do que uma língua bem feita. A documentação é bilingue; a interface não é,
até haver uma razão para um seletor de inglês suficientemente boa para justificar a
manutenção de ~60 rótulos.

## 10. Sem movimentação de dinheiro, sem POS, sem processamento salarial

O TipSplit diz-lhe quanto pagar e imprime o comprovativo; o dinheiro continua a sair da sua
mão. Integrar com caixas registadoras ou bancos implicaria obrigações ao estilo PCI e um
peso de suporte que mata um produto de uma só pessoa — e nada disso torna a divisão mais
justa.

## 11. Um ficheiro SQLite, um processo, tipos de letra do sistema

O escritório de um bar é um PC barato que pode ou não ter internet. Um ficheiro é cópia de
segurança, reposição e arquivo; tipos de letra do sistema significam que o layout não
depende de um download. Corre numa rede local com o router desligado do mundo.
