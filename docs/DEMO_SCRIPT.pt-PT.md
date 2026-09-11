# TipSplit — Guião de Demonstração (5 minutos, à frente de um espaço)

[English](DEMO_SCRIPT.md) · **Português (PT-PT)** · [README](../README.pt-PT.md)

Quatro momentos, por esta ordem. Ensaie uma vez e depois faça-o ao vivo. Tudo corre sobre o
conjunto de dados de demonstração — um espaço fictício, nunca um real.

```bash
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python -m uvicorn main:app --port 8791
# open http://localhost:8791 · owner PIN 1234 · staff PIN 2468
```

Antes de chegarem: abrir a **semana aberta** para o ecrã já estar vivo, e ter a página da
equipa em tamanho de telemóvel aberta num segundo ecrã ou no telemóvel.

---

## 1. "Isto é a sua segunda-feira" (90 s)

**No ecrã:** a vista da semana, semana aberta.

Escrever um valor de pote à frente deles, depois escrever horas em duas ou três células.
Dizer:

> "O pote é escrito pelo dono. As horas também. A divisão aparece à medida que se escreve —
> e esta barra mostra quando o pote e os quinhões batem certo até ao cêntimo."

Apontar para a linha do extrato: `886,20 € ÷ 371 h = 2,39 €/h. Regra: horas ÷ total de horas.
Nenhuma parte fica com a casa.`

> "É a fatura da equipa. O mesmo número em todos os telemóveis."

## 2. "Aquilo em que a folha de cálculo falha" (60 s)

> "Basta olhar para um Excel. Se ele arredonda cada pessoa em separado, os quinhões não
> somam o pote — um pote de €555 que paga €554.95. São cinco cêntimos, até serem um mês de
> cinco cêntimos, e depois é uma discussão."

Apontar para **Conferência ✓ OK**.

> "Aqui ninguém recebe a mais, e os cêntimos que sobram são distribuídos pela ordem. Todas
> as semanas, todas as pessoas, somam certo."

## 3. "Os adiantamentos deixam de ser um mistério" (90 s)

**Ir para:** Equipa → a lista de adiantamentos agrupada por semana.

> "Alguém leva €30 num sábado. Regista-se aqui — uma pessoa, um valor, e pertence a *esta*
> semana. Aparece sozinho na tabela da semana, para ninguém ter de se lembrar mais tarde."

Depois abrir a página da equipa (**o PIN da equipa**) no telemóvel:

> "Isto é o que a equipa vê. As horas, o quinhão, os adiantamentos e a tabela da semana
> toda. Não o salário do colega — a tabela: os mesmos números que todos os outros têm. É
> para acabar com o «então e porque é que o meu é menos?»"

## 4. "O dia de pagamento, e a prova" (90 s)

**Ir para:** uma semana fechada → **Comprovativos**.

> "Dia de pagamento: imprimir. Uma página por pessoa, com a fórmula lá —
> `470,40 € × 32 h ÷ 448 h = 33,60 €` — adiantamentos, líquido e uma linha para assinar. Se
> alguém conferir com a calculadora, dá o mesmo número. É esse o ponto."

Fechar com o registo de alterações (*Definições → Alterações recentes*):

> "E se uma semana fechada tiver de ser corrigida, exige um motivo escrito e fica nesta
> lista. Nada muda em silêncio."

---

## Perguntas que vão fazer

| Perguntam | Responder |
|---|---|
| "Paga às pessoas?" | Não. Diz quanto pagar e imprime o comprovativo. O dinheiro sai da mão do dono. |
| "Funciona com o meu POS?" | Não, de propósito. Sem POS, sem banco, sem integração de salários. |
| "Os meus dados estão na nuvem?" | Não. Um ficheiro na máquina, na rede local. Funciona com a internet em baixo. |
| "A equipa vê o salário uns dos outros?" | Veem os seus próprios números, mais a tabela da semana que os colegas também veem. Nunca as definições do pote, nunca outra semana, nunca os adiantamentos de outra pessoa. |
| "E se a internet cair?" | Nunca precisou dela. |
| "Quanto custa?" | (O preço a definir — o piloto é grátis durante 30 dias, depois uma taxa de instalação e/ou uma mensalidade.) |

## Reiniciar entre demonstrações

```bash
rm -f /tmp/tipsplit-demo.db
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
```

Determinístico: o espaço volta igual, para o ensaio continuar a corresponder.
