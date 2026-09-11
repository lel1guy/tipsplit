# TipSplit

[English](README.md) · **Português (PT-PT)**

Divisor semanal de gorjetas para bares, cafés e restaurantes pequenos. Entram as horas
da equipa, toda a gente vê o mesmo número e o mesmo comprovativo, os **vales**
(adiantamentos) saem da parte de cada um, e no dia de pagamento imprimem-se
comprovativos para assinar à mão.

    quinhão = pool × (horas da pessoa ÷ horas totais) − vales

Não passa dinheiro pela aplicação. É a calculadora e o comprovativo, não é a caixa.

Aplicação irmã do [BarSpec](https://github.com/lel1guy/barspec) — mesma stack, mesma
linguagem de design, produto separado.

---

## Para quem é

Casas com **5 a 30 pessoas** em Portugal/UE onde as gorjetas vão para um pote e se
dividem por horas. Substitui a folha de cálculo que o gerente refaz todas as segundas —
e, mais importante, responde à pergunta que começa todas as discussões: *«porque é que
o meu número é esse?»*

O que distingue não é a aritmética. É a **prova**: a regra da divisão à vista em cada
ecrã, comprovativos que sobrevivem a uma calculadora de bolso, adiantamentos que
pertencem sempre a uma semana e um registo de alterações do dono sem edições silenciosas.

## O que faz

- **Grelha da semana** — horas por dia (seg–dom, passos de 0,5 h), total automático e
  pré-visualização do quinhão enquanto escreve. O pool entra num só campo.
- **Divisão comprovável** — a conta vive no servidor, em `splitting.py`; o browser só
  mostra. A prova impressa mostra a fórmula sem arredondar
  (`470,40 € × 32 h ÷ 448 h = 33,60 €`), nunca um valor/hora arredondado multiplicado
  de volta.
- **Vales (adiantamentos)** — pertencem sempre a uma semana; agrupados por semana com
  subtotais na *Equipa*; a semana mostra os seus próprios adiantamentos. Não precisam de
  horas nem de motivo, e um vale sozinho põe a pessoa na tabela da semana (marcada
  *sem horas*).
- **Vale máximo** — limite opcional por adiantamento (*Definições*, `0` = sem limite),
  aplicado no servidor.
- **Dia de pagamento** — comprovativos por pessoa (vista de impressão), folha de caixa
  para o balcão, exportação da semana (Excel/CSV) e exportação anual. Imprimir uma
  semana aberta é recusado.
- **As semanas fecham** — uma semana fechada só reabre com **motivo**, e o motivo fica
  registado.
- **A página da equipa** — cada pessoa tem PIN e vê *os seus* números e a tabela da
  semana. Nada mais. Filtrado no servidor.
- **PIN do dono** — um só campo de entrada: o PIN do dono abre a gestão, o PIN de uma
  pessoa abre a página dessa pessoa.
- **Registo de alterações** — definições, gravações, fechos, reaberturas, adiantamentos,
  PINs.

## Como correr

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8001
```

Abrir http://127.0.0.1:8001 — na primeira vez pede para definir o PIN do dono e semeia
uma semana de demonstração com **nomes fictícios e horas aleatórias**. Os nomes reais
entram pela interface; a semente existe só para poder brincar com a divisão logo de
início.

Instalação nesta rede: serviço systemd `tipsplit`, a correr em `192.168.1.77:8778`.
A base de dados é SQLite simples (`tipsplit.db`); as migrações correm no arranque.

## Testes

```bash
python -m pytest tests/ -q      # 76 testes, a matemática e as regras do dinheiro
node e2e/smoke.mjs              # 59 asserções de browser, o ritual todo
```

Os testes unitários cobrem a divisão proporcional, o acerto ao cêntimo pelo resto maior,
vales, semanas sem horas, migrações a partir de uma base antiga, autenticação (hash de
PIN, adulteração de cookie, expiração), isolamento por pessoa e o limite de vale. A
suite de browser conduz a interface real contra uma base descartável: semana nova →
horas → adiantamento → fecho → comprovativos → exportações → reabertura com motivo →
entrada da equipa → 403 nos endpoints de gestão.

## Modelo de dados

| Tabela | Guarda |
|--------|--------|
| `weeks` | uma linha por semana (data da segunda, estado aberta/fechada) |
| `week_pools` | o pool de cada semana |
| `entries` | horas por pessoa por semana (seg…dom) |
| `staff` | equipa: nome, função, arquivada, `pin_hash` |
| `vales` | um registo por adiantamento: pessoa, data, **semana**, valor, motivo |
| `settings` | nome da casa, idioma, `vale_max` |
| `audit_log` | quem fez o quê, quando |

Migrações em `migrations/*.sql` com `PRAGMA user_version`. O esquema base é o antigo de
propósito, para a `001` correr em todas as instalações.

## API

Todos os endpoints excepto `/api/auth/*` e `/` exigem cookie de sessão.

| Método | Caminho | O quê |
|--------|---------|-------|
| GET | `/api/auth/status` | há PIN definido, que perfil tem esta sessão |
| POST | `/api/auth/setup` | definir o primeiro PIN do dono |
| POST | `/api/auth/login` | PIN do dono ou PIN de uma pessoa |
| POST | `/api/auth/logout` | terminar sessão |
| POST | `/api/auth/pin` | mudar o PIN do dono |
| GET/POST | `/api/staff` | equipa / acrescentar pessoa |
| POST | `/api/staff/{id}/archive` | arquivar ou reativar (o histórico fica) |
| POST | `/api/staff/{id}/pin` | dar ou apagar o PIN de uma pessoa |
| DELETE | `/api/staff/{id}` | apagar — só quem não tem histórico |
| GET | `/api/team` | equipa + adiantamentos da semana + estado do PIN |
| GET | `/api/dashboard` | os números da vista Semana |
| GET | `/api/vales` | adiantamentos (`?week_id=` filtra, `?staff_id=` filtra) |
| GET | `/api/vales/grouped` | o registo agrupado por semana, com subtotais |
| POST | `/api/vales` | registar adiantamento (semana obrigatória; limite aplicado) |
| DELETE | `/api/vales/{id}` | apagar adiantamento |
| GET/POST | `/api/weeks` | listar / criar semana pela data da segunda |
| GET/PUT/DELETE | `/api/weeks/{id}` | ler / mudar a data / apagar |
| PUT | `/api/weeks/{id}/save` | pool + todas as entradas de uma vez |
| POST | `/api/weeks/{id}/preview` | recalcular sem gravar |
| POST | `/api/weeks/{id}/lock` | fechar a semana |
| POST | `/api/weeks/{id}/unlock` | reabrir — **exige motivo** |
| GET | `/print/payslips/{id}` | comprovativos para assinar (vista de impressão) |
| GET | `/print/cashsheet/{id}` | folha de caixa para o balcão |
| GET | `/api/export/week/{id}` | exportação da semana (xlsx/csv) |
| GET | `/api/export/annual/{year}` | exportação anual |
| GET | `/api/settings` · PUT | nome da casa, idioma, limite de vale |
| GET | `/api/audit` | alterações recentes |
| GET | `/api/me` | **só sessão de equipa** — números próprios, tabela da semana, vales próprios |
| GET | `/print/me/{week_id}` | **só sessão de equipa** — o próprio comprovativo |

Uma sessão de equipa chega a `/api/me`, `/print/me/{semana}` e ao logout. Tudo o resto
responde **403** — verificado na suite de browser contra 8 endpoints.

## Modelo de segurança

- Os PINs são `pbkdf2_hmac`-SHA256 (260 mil iterações, sal por PIN). O cookie é assinado
  com HMAC e leva **perfil + id da pessoa + validade**: um cookie de equipa não se
  transforma em cookie de dono (testado, incluindo troca de id e de validade).
- Partilhar PIN é recusado nos dois sentidos — um PIN repetido significa ler o dinheiro
  de outra pessoa.
- A página da equipa nunca recebe a lista da equipa; o servidor filtra pelo id da pessoa.
- `/api/*` e `/print/*` levam `Cache-Control: no-store` — uma resposta 401 em cache já
  fez a aplicação parecer avariada logo após a configuração.

## O que de propósito não faz

- **Não move dinheiro.** Sem pagamentos, sem banco, sem POS, sem integração com salários.
- **Sem pesos por função.** A v1 divide só por horas; a função é uma etiqueta, não um
  multiplicador. (Multiplicador de fim de semana/turno está no roteiro.)
- **Sem multi-moeda.** EUR, interface em português, formatos de data e número PT.
- **Não é um sistema de salários.** Diz o que há a pagar e imprime a prova.

## Roteiro

| | |
|---|---|
| ✅ | Semanas, horas, pool, divisão comprovável, comprovativos, folha de caixa, exportações |
| ✅ | Registo de vales por semana, adiantamento opcional, limite por vale |
| ✅ | PIN, registo de alterações, reabertura com motivo, layout de telemóvel |
| ✅ | Página da equipa (números próprios + tabela da semana), navegação a sério |
| ⏭ | Pacote de demonstração: um bar fictício com 8 semanas de histórico |
| ⏭ | Botão para inglês na interface (a interface é PT-PT) |
| 💭 | Editar/remover pessoas com histórico (recalcular semanas antigas) |
| 💭 | Multiplicador de turno/fim de semana nas horas |
| 💭 | PWA para funcionar offline num telemóvel atrás do balcão |

## Stack

FastAPI + `sqlite3` simples (sem ORM) + um ficheiro HTML com JavaScript puro, tipos de
letra do sistema (sem webfonts — corre numa LAN de casa sem internet). `openpyxl` para as
exportações Excel. Idioma da interface por omissão: português (PT-PT).

---

Repositório privado. Bar-tech: `TipSplit` (este) + `BarSpec` (público).
