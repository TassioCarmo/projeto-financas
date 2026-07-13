from app.servicos.perfis_importacao.base import PerfilImportacao

PERFIL_PADRAO = PerfilImportacao(
    id="padrao",
    nome="Padrão",
    descricao=(
        "Colunas: data, descricao, categoria, valor "
        "(opcionais: pago, pago_por_terceiro, nome_terceiro)."
    ),
    colunas_obrigatorias=frozenset({"data", "descricao", "categoria", "valor"}),
    colunas_opcionais=frozenset({"pago", "pago_por_terceiro", "nome_terceiro"}),
    aliases_colunas={
        "data": "data",
        "data_compra": "data",
        "data compra": "data",
        "descricao": "descricao",
        "descrição": "descricao",
        "desc": "descricao",
        "categoria": "categoria",
        "categoria_nome": "categoria",
        "valor": "valor",
        "amount": "valor",
        "pago": "pago",
        "pago?": "pago",
        "pago_por_terceiro": "pago_por_terceiro",
        "pago por terceiro": "pago_por_terceiro",
        "nome_terceiro": "nome_terceiro",
        "nome terceiro": "nome_terceiro",
    },
    formatos_data=("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"),
)
