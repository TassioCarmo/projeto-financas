from app.servicos.perfis_importacao.base import PerfilImportacao

PERFIL_EXTRATO = PerfilImportacao(
    id="extrato_bancario",
    nome="Extrato bancário",
    descricao=(
        "Colunas: Data Lançamento (ou Data), Histórico (ou Descrição), "
        "Valor (R$). Categoria ausente usa Outros."
    ),
    colunas_obrigatorias=frozenset({"data", "descricao", "valor"}),
    colunas_opcionais=frozenset(),
    aliases_colunas={
        "data": "data",
        "data lancamento": "data",
        "data lançamento": "data",
        "data transacao": "data",
        "data transação": "data",
        "descricao": "descricao",
        "descrição": "descricao",
        "historico": "descricao",
        "histórico": "descricao",
        "lancamento": "descricao",
        "lançamento": "descricao",
        "valor": "valor",
        "valor (r$)": "valor",
        "valor r$": "valor",
        "amount": "valor",
    },
    formatos_data=("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"),
    categoria_padrao="Outros",
    valor_absoluto=True,
)
