# Documentação — Fase 4: Upload de planilha

Esta fase adicionou a segunda forma de entrada de dados: importação de planilhas CSV ou Excel com formato fixo, com limpeza básica linha a linha e resumo do resultado na tela.

---

## Objetivo da fase

Entregar upload de planilha para usuários autenticados:

1. Tela HTML com input de arquivo (`.xlsx`/`.csv`) e botão **Importar**
2. `POST /transacoes/importar` processando um único formato conhecido
3. Serviço de limpeza em `app/servicos/importacao.py`
4. Resumo pós-upload: linhas importadas, linhas com erro, transações visíveis na listagem

**Critério de aceite:** usuário sobe uma planilha real, vê o resultado do import, e as transações aparecem na lista junto com as cadastradas manualmente.

---

## Estrutura criada/alterada

```
financas-platform/
├── app/
│   ├── rotas/
│   │   └── transacoes.py         # + POST /transacoes/importar
│   ├── servicos/
│   │   ├── importacao.py         # leitura, normalização, importação
│   │   ├── categorias.py         # + mapa_nome_para_id()
│   │   └── transacoes.py         # criar_transacao(origem=...)
│   └── templates/
│       └── transacoes/
│           └── listar.html       # + seção de upload e resumo
├── tests/
│   ├── fixtures/
│   │   └── planilha_exemplo.csv
│   ├── test_importacao.py
│   └── test_importacao_integration.py
└── docs/
    └── fase-4.md                 # Este arquivo
```

---

## Formato da planilha

Primeira linha = cabeçalho. Colunas canônicas (aliases aceitos após normalização):

| Coluna | Obrigatória | Aliases | Exemplo |
|--------|-------------|---------|---------|
| `data` | sim | data_compra, data compra | `2026-07-13` ou `13/07/2026` |
| `descricao` | sim | descrição, desc | `Supermercado` |
| `categoria` | sim | categoria_nome | `Alimentação` |
| `valor` | sim | valor, amount | `45,90` ou `45.90` |
| `pago` | não | pago, pago? | `sim`, `true`, `1` |
| `pago_por_terceiro` | não | pago por terceiro | `não` |
| `nome_terceiro` | condicional | nome terceiro | `Maria` |

Categorias são resolvidas **por nome** contra as categorias ativas do seed (match case-insensitive, sem acento).

---

## Fluxo

```mermaid
flowchart TD
    upload["POST /transacoes/importar\nmultipart arquivo"] --> parse["importacao.py\nler + normalizar colunas"]
    parse --> rowLoop["Para cada linha"]
    rowLoop -->|valida| insert["criar_transacao\norigem=importacao"]
    rowLoop -->|inválida| errList["acumula erro\nsem parar"]
    insert --> listar["GET /transacoes\nmesma listagem Fase 3"]
    errList --> listar
```

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/transacoes/importar` | Upload de `.csv` ou `.xlsx` (protegida) |

**Request:** `multipart/form-data` com campo `arquivo`.

**Comportamento:**
- Linhas válidas → inseridas com `origem='importacao'`
- Linhas inválidas → registradas em `erros[]`, importação continua
- Resultado armazenado na sessão e exibido na próxima visita a `/transacoes`

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
2. Cadastrar um gasto manual na seção **Novo gasto**
3. Na seção **Importar planilha**, selecionar `tests/fixtures/planilha_exemplo.csv`
4. Clicar **Importar**
5. Ver resumo: 2 importadas, 1 com erro (linha sem descrição)
6. Confirmar que Supermercado, Uber e o gasto manual aparecem na tabela

### Exemplo com curl

```powershell
curl -X POST http://localhost:5000/transacoes/importar `
  -b cookies.txt -c cookies.txt `
  -F "arquivo=@tests/fixtures/planilha_exemplo.csv" `
  -L
```

---

## Testes

```powershell
# Unitários (não exigem Postgres)
pytest tests/test_health.py tests/test_auth.py tests/test_transacoes.py tests/test_importacao.py

# Integração (exige docker compose up)
pytest -m integration
```

O teste de integração verifica:

- Cadastro manual + upload de planilha
- 2 transações importadas, 1 linha com erro
- `origem='importacao'` no Postgres

---

## O que ficou de fora (propositalmente)

- Perfis de importação (Fase 8)
- Mapeamento configurável de colunas
- Preview antes de confirmar
- Deduplicação

---

## Commit sugerido

```
feat: importação de planilha CSV/XLSX com formato fixo
```

---

## Próximo passo

A **Parte 2** pode incluir filtros na listagem, dashboard ou perfis de importação, dependendo do feedback do MVP.
