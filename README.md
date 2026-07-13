# Sistema de Finanças Pessoais

Backend Flask com PostgreSQL para controle de gastos, importação de planilhas e acompanhamento financeiro.

## Pré-requisitos

- Python 3.11+
- Docker e Docker Compose

## Setup

1. Clone o repositório e entre na pasta do projeto.

2. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:

```bash
copy .env.example .env
# Linux/macOS: cp .env.example .env
```

5. Suba o PostgreSQL:

```bash
docker compose up -d
```

6. Aplique as migrations do banco:

```bash
python migrate.py
```

7. Inicie a aplicação:

```bash
python run.py
```

A aplicação estará disponível em `http://localhost:5000`.

## Health check

Verifique se a aplicação e o banco estão funcionando:

```bash
curl http://localhost:5000/health
```

Resposta esperada (200):

```json
{"status": "ok", "database": "connected"}
```

## Testes

```bash
# Unitários (não exigem Postgres)
pytest tests/test_health.py tests/test_auth.py tests/test_transacoes.py tests/test_importacao.py tests/test_resumo_mensal.py tests/test_orcamentos.py tests/test_dashboard.py

# Integração (exige docker compose up)
pytest -m integration
```

## Transações

Após login, a tela principal fica em:

- Transações: `http://localhost:5000/transacoes`

Cadastro manual de gastos, importação de planilha (`.csv` ou `.xlsx`) com perfis multi-formato e filtros por data, categoria e pago estão na mesma tela. Veja [Fase 3 — Cadastro manual](docs/fase-3.md), [Fase 4 — Upload de planilha](docs/fase-4.md), [Fase 7 — Filtros](docs/fase-7.md) e [Fase 8 — Perfis de importação](docs/fase-8.md).

## Resumo mensal

Após login, acesse:

- Resumo mensal: `http://localhost:5000/resumo-mensal?ano=2026`

Registre renda, investimento, rendimentos e patrimônio mês a mês. Veja detalhes em [Fase 5 — Dados mensais](docs/fase-5.md).

## Orçamentos

Após login, acesse:

- Orçamentos: `http://localhost:5000/orcamentos?ano_mes=2026-07`

Defina quanto planeja gastar por categoria e acompanhe o uso no mês. Veja detalhes em [Fase 6 — Orçamentos por categoria](docs/fase-6.md).

## Dashboard (API)

Após login, os endpoints JSON de agregação ficam em:

- Fluxo de caixa: `http://localhost:5000/dashboard/fluxo-caixa?ano_mes=2026-07`
- Compras recorrentes: `http://localhost:5000/dashboard/compras-recorrentes?ano_mes=2026-07`
- Categorias top: `http://localhost:5000/dashboard/categorias-top?ano_mes=2026-07`
- Patrimônio: `http://localhost:5000/dashboard/patrimonio`
- Orçamentos resumo: `http://localhost:5000/dashboard/orcamentos-resumo?ano_mes=2026-07`

Veja detalhes em [Fase 9 — Rotas de agregação para o dashboard](docs/fase-9.md).

## Autenticação

Após subir a aplicação, acesse:

- Cadastro: `http://localhost:5000/auth/cadastro`
- Login: `http://localhost:5000/auth/login`
- Perfil (protegido): `http://localhost:5000/perfil`

## Estrutura do projeto

```
app/
├── rotas/       # Blueprints Flask (endpoints)
├── servicos/    # Lógica de negócio e acesso ao banco
├── sql/         # Migrations SQL numeradas
└── templates/   # Templates Jinja2
tests/           # Testes automatizados
docs/            # Documentação por fase
```

## Documentação

- [Fase 0 — Setup do Projeto](docs/fase-0.md)
- [Fase 1 — Banco de dados mínimo](docs/fase-1.md)
- [Fase 2 — Autenticação simples](docs/fase-2.md)
- [Fase 3 — Cadastro manual de transação](docs/fase-3.md)
- [Fase 4 — Upload de planilha](docs/fase-4.md)
- [Fase 5 — Dados mensais (resumo_mensal)](docs/fase-5.md)
- [Fase 6 — Orçamentos por categoria](docs/fase-6.md)
- [Fase 7 — Filtros na listagem de transações](docs/fase-7.md)
- [Fase 8 — Perfis de importação multi-formato](docs/fase-8.md)
- [Fase 9 — Rotas de agregação para o dashboard](docs/fase-9.md)
