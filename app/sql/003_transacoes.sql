-- Regra de ouro: toda query em transacoes deve filtrar por usuario_id.

CREATE TABLE transacoes (
    id BIGSERIAL PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_compra DATE NOT NULL,
    descricao TEXT NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE RESTRICT,
    valor NUMERIC(12, 2) NOT NULL,
    pago BOOLEAN NOT NULL DEFAULT FALSE,
    pago_por_terceiro BOOLEAN NOT NULL DEFAULT FALSE,
    nome_terceiro TEXT,
    origem TEXT NOT NULL CHECK (origem IN ('manual', 'importacao')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transacoes_usuario_id ON transacoes (usuario_id);
CREATE INDEX idx_transacoes_usuario_data ON transacoes (usuario_id, data_compra DESC);
