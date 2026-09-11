# TipSplit

[English](README.md) · **Português (PT-PT)**

Repartidor semanal de gorjetas para **bares, cafés e restaurantes** — escreva as horas,
obtenha uma parte com que ninguém discute, entregue comprovativos que sobrevivem a uma
calculadora de bolso.

    parte = pool × (horas da pessoa ÷ horas totais) − vales

Feito por **Vitor Vareiro.** Inglês? Leia isto em [English](README.md).

## Capturas de ecrã

| A semana — horas a entrar, parte comprovável a sair | Dia de pagamento — comprovativos com a fórmula |
|---|---|
| ![Vista da semana: pool, a grelha de horas de Seg–Dom por pessoa, a coluna de vales, o líquido por pessoa e a declaração de equidade](docs/screenshots/semana.png) | ![Comprovativos impressos: uma página por pessoa com as horas, a fórmula por arredondar, os adiantamentos e o líquido a assinar](docs/screenshots/comprovativos.png) |
| **Uma semana fechada — trancada, com os ficheiros do dia de pagamento** | **Equipa — lista do pessoal, estado do PIN, vales por semana** |
| ![Uma semana trancada: grelha só de leitura, o selo de fecho e os botões Comprovativos / Folha de caixa / Excel / CSV](docs/screenshots/semana-fechada.png) | ![Vista de equipa: a lista com a função, os saldos de vales por semana e o estado do PIN de cada pessoa](docs/screenshots/equipa.png) |
| **O que a equipa vê — os seus próprios números** | **Definições — casa, limite de vales, registo de alterações** |
| ![A página do funcionário no telemóvel: as horas, a parte e os vales da própria pessoa e a tabela da semana inteira](docs/screenshots/minhas-gorjetas.png) | ![Definições: nome da casa, o limite de vales, o PIN do dono e a lista de alterações recentes](docs/screenshots/definicoes.png) |

*Capturas de computador e telemóvel do conjunto de dados de demonstração — uma casa
fictícia, 8 semanas de histórico. Reproduza-as exatamente com `ops/seed_demo.py`
(ver Pacote de demonstração).*

## Início rápido

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --port 8778      # http://localhost:8778
```

A primeira visita pede que defina o **PIN do dono** — e cria uma semana descartável com
pessoal fictício, para poder brincar logo com a parte. Os nomes reais entram pela
interface.

Quer isto cheio de histórico? Crie a casa fictícia (8 semanas, 12 pessoas, vales em
curso, uma semana aberta):

```bash
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python -m uvicorn main:app --port 8791
# owner PIN 1234 · one staff PIN 2468
```

## O que faz

- **A semana é um só ecrã**: pool a entrar, horas por dia (Seg–Dom, passos de 0,5 h),
  vales, líquido a sair — com uma parte ao vivo enquanto escreve. A verificação do pool
  diz *pool todo dividido* quando os quinhões e o pool batem ao cêntimo.
- **A matemática vive no servidor** (`splitting.py`) e o navegador só a apresenta.
  Arredondamento pelo maior resto: todos arredondam por baixo, os cêntimos que sobram são
  distribuídos, por isso os quinhões somam sempre o pool. Nada de 0,05 € a escapar como
  numa folha de cálculo.
- **Os vales (adiantamentos) pertencem a uma semana** — nunca a flutuar. Agrupados por
  semana com subtotais; a semana mostra os seus próprios vales; ninguém precisa de horas
  nem de um motivo para levar um, e um vale sozinho põe essa pessoa na tabela da semana
  (marcada como *sem horas*).
- **Vale máximo** — limite opcional por vale (*Definições*, `0` = sem limite), imposto no
  servidor, sem nunca reescrever vales já registados.
- **As semanas fecham.** Uma semana fechada não pode ser editada e pode ser impressa.
  Reabrir exige um **motivo**, que fica registado no registo de alterações.
- **Papelada do dia de pagamento**: comprovativos por pessoa com a fórmula por arredondar
  (`470,40 € × 32 h ÷ 448 h = 33,60 €`) e uma linha para assinar, uma folha de caixa para
  a caixa, exportação semanal (xlsx/csv) e uma exportação anual. Imprimir uma semana
  aberta é recusado.
- **A equipa tem a sua própria página**: um PIN cada um. Veem **as suas** horas, o
  a parte, os vales, o comprovativo e *a tabela inteira da semana* — mais nada. Filtrado
  no servidor, não escondido no navegador.
- **Portão do PIN do dono + registo de alterações**: um só campo de início de sessão (PIN
  do dono → gestão, PIN de funcionário → a página dessa pessoa). As gravações, os fechos,
  as reaberturas, os vales e as alterações de PIN ficam registados.
- **Corre numa LAN da casa** sem internet: um ficheiro HTML, JS puro, tipos de letra do
  sistema, SQLite. Sem nuvem, sem contas, sem passo de compilação.

## API

Todos os endpoints exceto `/api/auth/*` e `/` precisam de um cookie de sessão. Uma sessão
de funcionário acede a `/api/me`, `/print/me/{week}` e ao logout — tudo o resto é **403**.

| Método | Caminho | O quê |
|---|---|---|
| GET | `/api/auth/status` | se há um PIN definido, que papel tem esta sessão |
| POST | `/api/auth/setup` · `/login` · `/logout` · `/pin` | primeiro PIN · iniciar sessão (dono ou funcionário) · sair · alterar o PIN do dono |
| GET/POST | `/api/staff` | lista do pessoal / adicionar uma pessoa |
| POST | `/api/staff/{id}/archive` · `/pin` | arquivar ou reativar (histórico mantido) · emitir ou limpar um PIN |
| DELETE | `/api/staff/{id}` | eliminar — só alguém sem histórico |
| GET | `/api/team` · `/api/dashboard` | lista do pessoal + vales desta semana + estado do PIN · os números da vista da semana |
| GET/POST/DELETE | `/api/vales`, `/api/vales/grouped`, `/api/vales/{id}` | vales: listar, agrupar por semana com subtotais, registar, eliminar |
| GET/POST | `/api/weeks` | listar / criar uma semana pela sua segunda-feira |
| GET/PUT/DELETE | `/api/weeks/{id}` | ler / mover a data / eliminar |
| PUT/POST | `/api/weeks/{id}/save` · `/preview` · `/lock` · `/unlock` | guardar pool+horas · recalcular sem guardar · fechar · reabrir (motivo obrigatório) |
| GET | `/print/payslips/{id}` · `/print/cashsheet/{id}` | comprovativos a assinar · folha de caixa |
| GET | `/api/export/week/{id}` · `/api/export/annual/{year}` | exportações xlsx/csv |
| GET/PUT | `/api/settings` · `/api/audit` | casa, idioma, limite de vales · alterações recentes |
| GET | `/api/me` · `/print/me/{week_id}` | **só funcionários** — os seus números, tabela da semana, os seus vales, o seu comprovativo |

## Operações

Um ficheiro SQLite (`tipsplit.db`) e um processo. Ao vivo aqui: unidade systemd `tipsplit`
no `:8778`; as migrações correm no arranque (`migrations/*.sql` + `PRAGMA user_version`).
Publicações: tirar uma cópia da base de dados, fazer pull, reiniciar, verificar, fazer
push. Faça cópia de segurança do ficheiro todas as noites antes de confiar nele um mês de
dias de pagamento — ver o [Guia de programador](docs/DEV_GUIDE.md).

### Pacote de demonstração — "Bar Onda" (fictício)

Uma casa inventada de raiz, para não se tomar emprestado nada real: 12 pessoas com padrões
de turnos, 8 semanas de histórico, 7 fechadas com comprovativos, 21 vales espalhados pelas
semanas e uma semana aberta para brincar. Determinístico — a mesma semente em cada
execução, para que capturas e demonstrações não fujam.

```bash
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python -m uvicorn main:app --port 8791
# owner PIN 1234 · staff PIN 2468 (Ana Teixeira)
```

Ensaie-o com o [guião de demonstração](docs/DEMO_SCRIPT.md) de 5 minutos — os quatro
momentos, por ordem, com o que dizer.

## Roadmap / estado

Entregue: o ritual da semana, a parte comprovável, vales por semana com limite, fecho e
reabertura com motivo, comprovativos/folha de caixa/exportações, o portão do PIN do dono
com registo de alterações, a página própria da equipa, disposição para telemóvel e este
conjunto de documentação (78 testes + 63 asserções de navegador).

Já entregue desde então: **botão PT-PT/inglês** em *Definições* — a interface, a regra da
divisão e os comprovativos impressos seguem-no (um recarregamento mantém a escolha); as
exportações de folha de cálculo ficam em português. A interface começa em PT-PT, porque
quem escreve as horas ao fechar a casa fala português. A seguir: aquilo que uma casa real
pedir primeiro. Deliberadamente **fora** de âmbito: movimento de dinheiro, integrações com
POS ou processamento salarial,
multimoeda, pesos por função. O plano do produto vive no vault
(`Projects/Bar-Tech-Venture/tipsplit/TipSplit-Vision-and-Dev-Plan.md`).

## Documentação

| | EN | PT-PT |
|---|---|---|
| Este ficheiro | [README.md](README.md) | [README.pt-PT.md](README.pt-PT.md) |
| **Guia do utilizador** — o ritual semanal, vales, dia de pagamento, PINs, FAQs | [USER_GUIDE.md](docs/USER_GUIDE.md) | [USER_GUIDE.pt-PT.md](docs/USER_GUIDE.pt-PT.md) |
| **Guia de programador** — arquitetura, esquema, testes, publicação, recuperação de PIN | [DEV_GUIDE.md](docs/DEV_GUIDE.md) | [DEV_GUIDE.pt-PT.md](docs/DEV_GUIDE.pt-PT.md) |
| **Porquê** — o raciocínio por trás das regras | [WHY.md](docs/WHY.md) | [WHY.pt-PT.md](docs/WHY.pt-PT.md) |
| **Guião de demonstração** — 5 minutos à frente de uma casa | [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | [DEMO_SCRIPT.pt-PT.md](docs/DEMO_SCRIPT.pt-PT.md) |

## Licença

**GNU AGPL-3.0** — ver [LICENSE](LICENSE). Podes usar, estudar, modificar e alojar o
TipSplit à vontade; se correres uma versão modificada como serviço em rede, a AGPL obriga a
publicar as tuas alterações.

**Licença comercial disponível a pedido** — para integrar o TipSplit num produto fechado, ou
oferecê-lo como serviço alojado sem as obrigações de divulgação do código da AGPL, fala
comigo (licenciamento duplo; os direitos de autor são meus).

As mesmas condições da aplicação irmã [BarSpec](https://github.com/lel1guy/barspec): uma
aberta, ambas com licenciamento duplo.
