# TipSplit — Dev Guide

[English](DEV_GUIDE.md) · **Português (PT-PT)** · [README](../README.pt-PT.md)

Para quem mexer no código a seguir (provavelmente tu, daqui a seis meses, à 1h da manhã).

## Estrutura

| Ficheiro | Responsabilidade |
|---|---|
| `main.py` | aplicação FastAPI: todas as rotas, a barreira de PIN do dono/equipa, os cabeçalhos de segurança, as páginas de impressão |
| `splitting.py` | **todos os cálculos de dinheiro** — horas, partes, arredondamento por restos maiores, o texto do comprovativo |
| `db.py` | acesso a SQLite (sem ORM), executor de migrações, weeks/entries/staff/vales/settings/audit |
| `auth.py` | hashing de PIN (pbkdf2), o cookie de sessão assinado (função + id de staff + expiração), travão contra força bruta |
| `exporters.py` | recibos de vencimento, folha de caixa, xlsx/csv semanal + anual. **Só formatos — nunca decide dinheiro** |
| `static/index.html` | toda a interface: um só ficheiro, JS puro, CSS inline, tipos de letra do sistema |
| `migrations/*.sql` | passos de esquema, aplicados por `PRAGMA user_version` |
| `ops/seed_demo.py` | o espaço fictício (demos, capturas de ecrã) |
| `tests/`, `e2e/smoke.mjs` | conjunto de testes unitários + percurso no navegador |

Regra da casa: **a matemática do dinheiro vive em `splitting.py` e em mais lado nenhum.** O
navegador mostra o que o servidor calculou; `exporters.py` limita-se a formatá-lo. Se alguma
vez precisares de um número em dois sítios, envia-o a partir do servidor.

## Modelo de dados

```
weeks(id, start_date UNIQUE, status open|locked, closed_at, closed_by)
week_pools(week_id, pool_eur)
entries(week_id, staff_id, mon..sun)
staff(id, name, position, archived, pin_hash)          -- pin_hash '' = no PIN issued
vales(id, staff_id, date, week_id, amount, note)       -- week_id is always set
settings(key, value)                                   -- venue_name, lang, vale_max
audit_log(id, ts, actor, action, detail)
```

Migrações: acrescenta `migrations/00N_name.sql` e sobe o `LATEST` em
`tests/test_migrations.py`. O esquema base tem deliberadamente a forma **antiga** para que a
`001` seja exercitada em cada instalação nova.

## Executar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --reload --port 8778
```

`TIPSPLIT_DB` substitui o caminho da base de dados (usado pelos testes, pelo e2e e pela demo).

## Testes

```bash
.venv/bin/python -m pytest tests/ -q      # 76 unit tests (~1 min)
node e2e/smoke.mjs                        # 60 browser assertions against a throwaway DB
```

O conjunto de testes unitários cobre a matemática da divisão (partes proporcionais, acerto de
cêntimos, semanas com zero horas), os vales (semana obrigatória, teto, agrupamento, listagem
automática), as migrações a partir de uma base de dados antiga, a autenticação (hashing,
adulteração de token, expiração, isolamento por membro da equipa) e a aritmética do
comprovativo impresso.

O conjunto de testes no navegador arranca a aplicação real e percorre todo o ritual: PIN na
primeira execução → semana nova → horas → adiantamento → teto → fecho → recibos de vencimento
→ exportações → desbloqueio com um motivo → início de sessão da equipa → a página da equipa →
403s nos endpoints de gestão → disposições para telemóvel.

`e2e/smoke.mjs` reutiliza o `playwright-core` da cópia do BarSpec
(`/home/vitor/dev/barspec/node_modules`) e um Chromium de `~/.cache/ms-playwright`.
Não é preciso instalar nada nesta máquina.

**Nunca apontes os testes à base de dados em produção.** Eles copiam ou substituem o `TIPSPLIT_DB`.

## Implementação (esta rede)

```bash
sudo systemctl restart tipsplit && sleep 15 && systemctl is-active tipsplit
```

Em produção em `192.168.1.77:8778`, base de dados em `/home/vitor/dev/tipsplit/tipsplit.db`, as
migrações correm no arranque. Antes de um reinício que mexa no esquema: copia primeiro a base de dados.

## Cópia de segurança e restauro

```bash
cp tipsplit.db "tipsplit-$(date +%F).db"     # backup: the whole app is this file
```

Restaurar = parar o serviço, repor o ficheiro, iniciá-lo. Não há mais nenhum estado.

## Recuperação do PIN (PIN do dono esquecido)

Não há reposição por email — sem nuvem, sem contas. Na máquina:

```bash
sqlite3 tipsplit.db "DELETE FROM settings WHERE key='pin_hash'"
```

A barreira pede então para definir um PIN na visita seguinte. Os PINs da equipa ficam em
`staff.pin_hash`; limpa um por pessoa em *Equipa → limpar*, ou em SQL.

## Acrescentar uma funcionalidade sem quebrar a confiança

1. Alteração de dinheiro? Reproduz a aritmética num teste **primeiro**, a partir de uma página
   de recibo de vencimento real se puderes. Um erro de arredondamento é invisível até ao dia de pagamento.
2. Novo endpoint? Decide quem lhe pode aceder: dono, equipa, ou ninguém sem cookie. Acrescenta-o
   à lista de 403 do e2e se for só para o dono.
3. Novo campo numa semana ou numa pessoa? Provavelmente pertence ao payload da semana que vem do
   servidor, não ao estado do cliente.
4. Alteração de interface? Corre `node e2e/smoke.mjs`. Os testes unitários passavam a verde
   durante cinco bugs reais de interface na migração do design; só o navegador os apanhou.
5. Tudo o que escreva registos de dinheiro (adiantamentos, fechos) merece uma chamada `audit()`.

## Regerar as capturas de ecrã

```bash
rm -f /tmp/tipsplit-demo.db
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
```

Depois conduz a aplicação com um pequeno script playwright e guarda em `docs/screenshots/`. A
seed é determinística, por isso os números no README continuam verdadeiros.

## Armadilhas conhecidas

- A interface é só PT-PT, por decisão. Strings em inglês na UI são bugs — já foram encontradas
  duas vezes (`Payslips`/`Cash sheet`, `Mon…Sun`), por isso procura-as quando acrescentares texto.
- O `#gate` tem de manter `display:none !important` quando está escondido; um seletor de id
  venceu a classe uma vez e deixou a aplicação morta atrás de uma sobreposição invisível.
- Qualquer atualização que volte a desenhar um `<select>` tem de preservar a escolha do
  utilizador, e as atualizações concorrentes são agrupadas em `loadTeam()` — uma renderização
  desatualizada apontou uma vez um adiantamento à pessoa errada.
- `/api/*` e `/print/*` têm de manter `Cache-Control: no-store`: um 401 em cache fez a aplicação
  parecer avariada logo após a instalação.
