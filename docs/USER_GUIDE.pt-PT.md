# TipSplit — Guia de utilização

[English](USER_GUIDE.md) · **Português (PT-PT)** · [README](../README.pt-PT.md)

Para quem manda na semana: o gerente, o chefe de balcão, quem fecha a caixa. Tudo o que
está aqui abaixo acontece num browser, na rede da casa — não há nada para instalar nem
internet de que precise.

**A regra por trás de tudo:**

    parte = pool × (horas da pessoa ÷ horas totais) − vales

As horas decidem a parte. Os adiantamentos que já levou saem dessa parte. Mais nada mexe
no número.

---

## 1. Só da primeira vez — definir o PIN do dono

Abra a aplicação e defina um PIN (4+ dígitos). Esse PIN é seu: abre o lado da gestão.
**Os números da semana ficam atrás dele** — ninguém lê a divisão pelo wifi do bar sem o
PIN.

Se se esquecer dele, a recuperação é feita na própria máquina (ver DEV_GUIDE) — não há
email de «esqueci-me do PIN» porque não há nuvem.

## 2. Pôr a equipa lá dentro

**Equipa → Nova pessoa** → nome + função (Bartender, Barback…). A função é uma
**etiqueta**, não um multiplicador: aparece ao lado do nome na lista, não mexe na
divisão.

Alguém sai? O **⊘** arquiva: desaparece da lista das semanas novas, mas todas as semanas
antigas mantêm o nome e o dinheiro dessa pessoa. Nunca apague quem tem histórico — a
aplicação recusa, porque isso reescreveria semanas antigas.

## 3. O ritual da semana

1. **+ Nova semana** — abre uma semana datada à segunda-feira, já com a equipa lá dentro
   e as horas a zero.
2. Escreva o **pool** da semana (o total das gorjetas, num só campo).
3. Escreva as **horas por dia** de cada pessoa (seg–dom, passos de 0,5 h). As horas somam
   sozinhas e a parte de cada um aparece a atualizar-se enquanto escreve.
4. **Veja a faixa no topo:** diz *totalmente dividido* quando o pool e as partes batem ao
   cêntimo.
5. **Guardar**. Essa semana passa a ser o registo.

A faixa amarela **«Faltam horas de N pessoas»** diz quem ainda não tem horas. Use-a antes
de fechar — fechar uma semana com horas em falta é o erro silencioso clássico.

## 4. Vales (adiantamentos)

Alguém levou 20 € da caixa num sábado. **Equipa → Adiantamento**:

| Campo | O que significa |
|-------|-----------------|
| Semana | a semana a que o adiantamento pertence (vem já a aberta) |
| Pessoa | quem levou |
| Valor € | quanto |
| Motivo *(opcional)* | «tabaco», «gasolina» — para sua memória, não é obrigatório |

Um vale **pertence sempre a uma semana** — nunca é solto — para ser a semana em que foi
levado a pagá-lo. A lista da *Equipa* mostra todos os adiantamentos agrupados por semana,
com subtotal por semana.

**Aparece em dois sítios:** a grelha da semana tem uma coluna **Vales €** (só de leitura,
porque o registo é a fonte de verdade) e a semana lista os seus próprios adiantamentos
por baixo da regra. Quem levou um adiantamento aparece na tabela da semana mesmo sem
horas — marcado **sem horas**, para não haver nada escondido.

**Vale máximo** (*Definições*) limita um adiantamento: com `50`, um vale de 50,01 € é
recusado e um de 50 € é aceite. `0` = sem limite. Baixar o limite nunca mexe nos
adiantamentos já registados — só trava os novos.

**Se um vale for maior do que a parte da pessoa nessa semana**, a aplicação di-lo a
vermelho e a diferença é *dívida ao pote*: foi paga antes do tempo, a semana não cobre,
acerta-se para a semana seguinte. Nada é bloqueado — quem decide é o gerente; a aplicação
apenas recusa mentir sobre isso.

## 5. Dia de pagamento

Abra a semana fechada e use os botões da semana:

- **Comprovativos** — uma folha por pessoa, com as horas, a fórmula, os adiantamentos e o
  líquido, e uma linha para assinar. Imprimir, entregar, assinar.
- **Folha de caixa** — a folha do balcão: quem recebe quanto, total que sai.
- **Anual (Excel)** — o ano até à data, para a contabilidade.
- **Semana** — a exportação da semana em xlsx/csv.

A fórmula impressa é de propósito sem arredondar (`470,40 € × 32 h ÷ 448 h = 33,60 €`),
para sobreviver a uma calculadora de bolso. Se alguém conferir as contas, chega ao mesmo
número que o gerente.

## 6. Fechar e reabrir uma semana

**Fechar semana** fecha-a. Uma semana fechada não se edita e pode ser impressa.

Fechou por engano, ou apareceu uma correção atrasada? **Reabrir** pede um **motivo** e
fica registado em *Alterações recentes* com a hora. É esse o objetivo: mexer numa semana
já acertada deixa sempre rasto. Imprimir uma semana aberta é recusado — feche primeiro,
pague depois.

## 7. Deixar a equipa ver os números dela

**Equipa → dar PIN** a uma pessoa (4+ dígitos, sem repetir). Diga-lhe o PIN. Ela abre o
mesmo endereço no telemóvel, escreve o PIN e cai em **As minhas gorjetas**:

- as horas, a parte, os adiantamentos e o que falta receber — e a tabela toda da
  semana, para ninguém ter de discutir a divisão
- o comprovativo próprio (assim que a semana fechar)
- o histórico de adiantamentos, por semana

Vê **exatamente os dados dela mais a tabela da semana** — nada mais. Não chega ao pool,
às definições, às outras semanas nem aos adiantamentos de outra pessoa: é o servidor que
recusa, não é só esconder no ecrã. Partilhar PIN é recusado — se dois têm o mesmo, já não
é de nenhum deles.

## 8. Definições

| Campo | O que faz |
|-------|-----------|
| Nome da casa | aparece nos comprovativos e na folha de caixa impressos |
| Vale máximo (€) | limite por adiantamento; `0` = sem limite |
| PIN do dono | mudar o seu próprio PIN |
| Alterações recentes | as últimas mudanças com hora: gravações, fechos, reaberturas, adiantamentos, PINs |

## Perguntas frequentes

**«Porque é que o X tem menos do que eu, com as mesmas horas?»** Levou um adiantamento.
Abra a semana — a coluna Vales e a lista de adiantamentos por baixo da regra mostram-no.

**«Dá para dividir por função em vez de horas?»** Nesta versão não. Só horas, por opção:
as horas são a coisa que ninguém discute num sábado à noite.

**«Isto paga às pessoas?»** Não. Nunca toca em dinheiro: diz quem recebe o quê e imprime a
prova. O dinheiro continua a sair da sua mão.

**«E se falhar a internet?»** Corre na máquina da própria casa. A internet nunca foi
precisa — funciona atrás do balcão numa rede local.

**«Posso mudar uma semana fechada?»** Pode, com motivo, e fica registado. É essa a troca:
correções continuam possíveis, o silêncio não.

## Cópias de segurança

A aplicação toda é um ficheiro SQLite (`tipsplit.db`). Vale a pena ter uma cópia noturna
antes de lhe confiar um mês de pagamentos — peça a quem instalou, ou veja o DEV_GUIDE.
