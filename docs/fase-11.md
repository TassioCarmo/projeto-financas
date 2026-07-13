# Documentação — Fase 11: Dashboard visual completo

Esta fase adicionou telas HTML com Chart.js consumindo as APIs JSON da Fase 9.

---

## Objetivo da fase

Entregar dashboard navegável para usuários autenticados:

1. Visão geral (fluxo de caixa + patrimônio)
2. Detalhamento por categoria
3. Ranking de recorrências
4. Status de orçamentos
5. Integração com consultas personalizadas (Fase 10)

**Critério de aceite:** dashboard navegável com todos os dados reais do usuário logado.

---

## Estrutura criada

```
financas-platform/
├── app/
│   ├── rotas/
│   │   └── dashboard.py              # + rotas HTML
│   └── templates/
│       ├── _nav_app.html             # Nav global compartilhada
│       └── dashboard/
│           ├── layout.html
│           ├── _subnav.html
│           ├── _scripts_common.html
│           ├── visao_geral.html
│           ├── categorias.html
│           ├── recorrencias.html
│           └── orcamentos.html
├── tests/
│   ├── test_dashboard_views.py
│   └── test_dashboard_views_integration.py
└── docs/
    └── fase-11.md                    # Este arquivo
```

---

## Rotas HTML

| Rota | Tela | APIs consumidas |
|------|------|-----------------|
| `GET /dashboard` | Visão geral | `fluxo-caixa`, `patrimonio` |
| `GET /dashboard/categorias` | Categorias | `categorias-top` |
| `GET /dashboard/recorrencias` | Recorrências | `compras-recorrentes` |
| `GET /dashboard/orcamentos` | Orçamentos | `orcamentos-resumo` |
| `GET /consultas` | Consultas (Fase 10) | — |

Query param `ano_mes` (formato `AAAA-MM`) nas telas com escopo mensal. Default: mês atual.

As rotas JSON da Fase 9 permanecem inalteradas.

---

## Gráficos por tela

| Tela | Chart.js | Dados |
|------|----------|-------|
| Visão geral | Barras (entrou/saiu/saldo) + Linha (patrimônio) | `fluxo-caixa.mes`, `patrimonio.serie` |
| Categorias | Doughnut + tabela | `categorias-top` (toggle mês/total) |
| Recorrências | Barras horizontais + tabela | `compras-recorrentes` (toggle mês/total) |
| Orçamentos | Barras agrupadas + progresso | `orcamentos-resumo` |

Chart.js carregado via CDN: `https://cdn.jsdelivr.net/npm/chart.js`

---

## Navegação

**Nav global** (todas as telas autenticadas):

`Transações | Resumo mensal | Orçamentos | Dashboard | Consultas | Perfil | Sair`

**Sub-nav do dashboard:**

`Visão geral | Categorias | Recorrências | Orçamentos | Consultas`

---

## Como rodar

```powershell
cd C:\Users\tcarmo\Documents\projeto\financas-platform

docker compose up -d
python migrate.py
python run.py
```

### Validar manualmente no browser

1. Login em `http://localhost:5000/auth/login`
2. Cadastre transações, resumo mensal e orçamentos
3. Acesse `http://localhost:5000/dashboard`
4. Navegue pelas abas do dashboard
5. Troque o mês de referência e verifique atualização dos gráficos
6. Acesse **Consultas** pela sub-nav

---

## Testes

```powershell
# Unitários (não exigem Postgres)
pytest tests/test_dashboard_views.py

# Integração (exige docker compose up)
pytest -m integration tests/test_dashboard_views_integration.py
```

---

## O que ficou de fora (propositalmente)

- Redirect pós-login para `/dashboard` (permanece `/transacoes`)
- Exportação de gráficos
- WebSocket / atualização em tempo real
- Novas agregações SQL

---

## Commit sugerido

```
feat: dashboard visual com Chart.js (Fase 11)
```

---

## Próximo passo

Fases futuras podem incluir exportação, temas visuais ou redirect pós-login para o dashboard.
