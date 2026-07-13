from app.servicos.perfis_importacao.base import PerfilImportacao

PERFIL_CARTAO_FAMILIAR = PerfilImportacao(
    id="controle_cartao_familiar",
    nome="Controle Cartão Familiar",
    descricao=(
        "Planilha multi-aba com abas mensais (Janeiro–Dezembro). "
        "Colunas: Data, Descrição da Compra, Categoria, Pessoa, Valor (R$), "
        "Pago? (opcionais: Data Pagamento, Observações)."
    ),
    colunas_obrigatorias=frozenset({"descricao", "categoria", "valor"}),
    colunas_opcionais=frozenset(
        {"data", "pago", "pessoa", "observacoes", "data_pagamento"}
    ),
    aliases_colunas={
        "data": "data",
        "descricao da compra": "descricao",
        "descricao": "descricao",
        "descrição da compra": "descricao",
        "descrição": "descricao",
        "categoria": "categoria",
        "pessoa": "pessoa",
        "valor (r$)": "valor",
        "valor r$": "valor",
        "valor": "valor",
        "pago?": "pago",
        "pago": "pago",
        "data pagamento": "data_pagamento",
        "observacoes": "observacoes",
        "observações": "observacoes",
    },
    formatos_data=("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"),
    mapeamento_categorias={
        "tecnologia": "Compras",
        "financeiro": "Serviços",
        "higiene": "Saúde",
        "casa": "Moradia",
    },
)
