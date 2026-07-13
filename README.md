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
pytest tests/test_health.py tests/test_auth.py

# Integração (exige docker compose up)
pytest -m integration
```

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
