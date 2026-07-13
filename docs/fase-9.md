# Documentação — Fase 9: Rotas de agregação para o dashboard

Esta fase adicionou endpoints JSON autenticados que agregam dados de transações, resumo mensal e orçamentos para alimentar um dashboard futuro.

---

## Objetivo da fase

Entregar rotas de agregação para usuários autenticados:

1. Fluxo de caixa (entrou vs. saiu) — mês e total geral
2. Compras recorrentes — mês e total geral
3. Categorias com maior gasto — mês e total geral
4. Evolução do patrimônio mês a mês
5. Resumo consolidado de orçamentos

**Critério de aceite:** rotas retornando dados corretos, usando `GROUP BY` no SQL.

---

## Estrutura criada

```
financas-platform/
├── app/
│   ├── rotas/
│   │   └── dashboard.py              # 5 endpoints GET JSON
│   ├── servicos/
│   │   └── dashboard.py              # agregações SQL
│   └── __init__.py                   # + dashboard_bp
├── tests/
│   ├── test_dashboard.py
│   └── test_dashboard_integration.py
└── docs/
    └── fase-9.md                     # Este arquivo
```

---

## Definições de domínio

| Conceito | Fonte | Regra |
|----------|-------|-------|
| **Entrou** | `resumo_mensal` | `renda + rendimentos` |
| **Saiu** | `transacoes` | `SUM(valor)` por mês ou histórico |
| **Patrimônio efetivo** | `resumo_mensal` | `COALESCE(patrimonio, patrimonio_sugerido)` |
| **Compra recorrente** | `transacoes.descricao` | Mesma descrição normalizada com `COUNT(*) >= 2` |

Todas as queries filtram `WHERE usuario_id = %s`.

---

## Endpoints

| Método | Rota | Query param |
|--------|------|-------------|
| GET | `/dashboard/fluxo-caixa` | `ano_mes` (default: mês atual) |
| GET | `/dashboard/compras-recorrentes` | `ano_mes` |
| GET | `/dashboard/categorias-top` | `ano_mes` |
| GET | `/dashboard/patrimonio` | — |
| GET | `/dashboard/orcamentos-resumo` | `ano_mes` |

Resposta sempre JSON. Requer sessão ativa (`401` se não autenticado). `ano_mes` inválido retorna `400`.

### Exemplo: fluxo de caixa

```json
{
  "ano_mes": "2026-07",
  "mes": { "entrou": 5120.0, "saiu": 1100.0, "saldo": 4020.0 },
  "total_geral": { "entrou": 9920.0, "saiu": 1400.0, "saldo": 8520.0 }
}
```

### Exemplo: compras recorrentes

```json
{
  "ano_mes": "2026-07",
  "mes": [
    {
      "descricao": "Netflix",
      "categoria_id": 1,
      "categoria_nome": "Alimentação",
      "ocorrencias": 2,
      "total": 100.0,
      "media": 50.0
    }
  ],
  "total_geral": [ ... ]
}
```

### Exemplo: categorias top

```json
{
  "ano_mes": "2026-07",
  "mes": [
    {
      "categoria_id": 1,
      "categoria_nome": "Alimentação",
      "total": 950.0,
      "qtd": 3,
      "percentual": 86.36
    }
  ],
  "total_geral": [ ... ]
}
```

### Exemplo: patrimônio

```json
{
  "serie": [
    {
      "ano_mes": "2026-06",
      "renda": 4800.0,
      "investimento": 400.0,
      "rendimentos": 100.0,
      "patrimonio": null,
      "patrimonio_sugerido": 500.0,
      "patrimonio_efetivo": 500.0
    }
  ]
}
```

### Exemplo: orçamentos resumo

```json
{
  "ano_mes": "2026-07",
  "totais": {
    "valor_planejado": 1300.0,
    "valor_gasto": 1100.0,
    "saldo_restante": 200.0,
    "percentual_usado": 84.62
  },
  "por_categoria": [ ... ]
}
```

---

## Queries SQL principais

### Fluxo de caixa (saiu)

```sql
SELECT COALESCE(SUM(valor), 0)
FROM transacoes
WHERE usuario_id = %s
  AND TO_CHAR(data_compra, 'YYYY-MM') = %s;
```

### Compras recorrentes

```sql
SELECT LOWER(TRIM(descricao)), categoria_id,
       COUNT(*) AS ocorrencias, SUM(valor) AS total
FROM transacoes
WHERE usuario_id = %s
GROUP BY LOWER(TRIM(descricao)), categoria_id
HAVING COUNT(*) >= 2
ORDER BY total DESC;
```

### Categorias top

```sql
SELECT t.categoria_id, c.nome, SUM(t.valor) AS total, COUNT(*) AS qtd
FROM transacoes t
JOIN categorias c ON c.id = t.categoria_id
WHERE t.usuario_id = %s
GROUP BY t.categoria_id, c.nome
ORDER BY total DESC;
```

---

## Como rodar

```powershell
cd C:\Users\tcarmo\Documents\projeto\financas-platform

docker compose up -d
python migrate.py
python run.py
```

### Validar com curl

```powershell
# Login
curl -X POST http://localhost:5000/auth/login `
  -d "email=joao@example.com&senha=senha123" `
  -c cookies.txt -b cookies.txt -L

# Fluxo de caixa
curl "http://localhost:5000/dashboard/fluxo-caixa?ano_mes=2026-07" -b cookies.txt

# Patrimônio
curl "http://localhost:5000/dashboard/patrimonio" -b cookies.txt
```

---

## Testes

```powershell
# Unitários (não exigem Postgres)
pytest tests/test_dashboard.py

# Integração (exige docker compose up)
pytest -m integration tests/test_dashboard_integration.py
```

---

## O que ficou de fora (propositalmente)

- Template HTML do dashboard
- Coluna `recorrente` em transações
- Transações de receita (entrou vem só de `resumo_mensal`)
- Categorias com gasto mas sem orçamento em `orcamentos-resumo`

---

## Commit sugerido

```
feat: rotas de agregação JSON para dashboard (Fase 9)
```

---

## Próximo passo

Fase futura pode incluir tela HTML do dashboard consumindo estes endpoints.
