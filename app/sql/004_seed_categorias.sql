INSERT INTO categorias (nome) VALUES
    ('Alimentação'),
    ('Transporte'),
    ('Moradia'),
    ('Saúde'),
    ('Educação'),
    ('Lazer'),
    ('Vestuário'),
    ('Compras'),
    ('Serviços'),
    ('Investimentos'),
    ('Outros')
ON CONFLICT (nome) DO NOTHING;
