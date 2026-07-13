-- Regra de ouro: toda query em orcamentos deve filtrar por usuario_id.
--
-- Esta tabela guarda quanto o usuário planeja gastar por categoria em cada mês.
-- O formato de ano_mes é "AAAA-MM" (ex: "2026-07" = julho de 2026).
-- Cada usuário pode ter no máximo UM orçamento por categoria + mês (UNIQUE abaixo).

CREATE TABLE orcamentos (
    id BIGSERIAL PRIMARY KEY,

    -- Dono do registro — sempre vem da sessão, nunca do formulário
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,

    -- Categoria do plano de gastos (ex: Alimentação, Transporte)
    categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE RESTRICT,

    -- Mês de referência no formato "2026-07"
    ano_mes TEXT NOT NULL CHECK (ano_mes ~ '^\d{4}-\d{2}$'),

    -- Quanto o usuário planeja gastar nesta categoria no mês
    valor_planejado NUMERIC(12, 2) NOT NULL CHECK (valor_planejado >= 0),

    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Garante um único orçamento por usuário + categoria + mês (permite upsert)
    UNIQUE (usuario_id, categoria_id, ano_mes)
);

-- Índice para buscar rapidamente os orçamentos de um usuário em um mês
CREATE INDEX idx_orcamentos_usuario_mes ON orcamentos (usuario_id, ano_mes);
