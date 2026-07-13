-- Regra de ouro: toda query em resumo_mensal deve filtrar por usuario_id.
--
-- Esta tabela guarda um "resumo financeiro" por mês para cada usuário.
-- O formato de ano_mes é "AAAA-MM" (ex: "2026-07" = julho de 2026).
-- Cada usuário pode ter no máximo UM registro por mês (UNIQUE abaixo).

CREATE TABLE resumo_mensal (
    id BIGSERIAL PRIMARY KEY,

    -- Dono do registro — sempre vem da sessão, nunca do formulário
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,

    -- Mês de referência no formato "2026-07"
    ano_mes TEXT NOT NULL CHECK (ano_mes ~ '^\d{4}-\d{2}$'),

    -- Quanto o usuário ganhou no mês (informação para histórico)
    renda NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Quanto foi investido/aportado no mês
    investimento NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Rendimentos (juros, dividendos etc.) recebidos no mês
    rendimentos NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Patrimônio informado manualmente pelo usuário (opcional)
    -- Se NULL, o usuário não informou — usamos só o patrimonio_sugerido
    patrimonio NUMERIC(12, 2),

    -- Patrimônio calculado automaticamente pela aplicação
    -- Fórmula: base do mês anterior + investimento + rendimentos
    patrimonio_sugerido NUMERIC(12, 2),

    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Garante um único registro por usuário + mês (permite upsert)
    UNIQUE (usuario_id, ano_mes)
);

-- Índice para buscar rapidamente os meses de um usuário
CREATE INDEX idx_resumo_mensal_usuario_ano ON resumo_mensal (usuario_id, ano_mes);
