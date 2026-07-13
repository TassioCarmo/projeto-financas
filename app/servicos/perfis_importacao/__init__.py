import unicodedata

from app.servicos.perfis_importacao.base import FormatoPlanilhaError, PerfilImportacao
from app.servicos.perfis_importacao.controle_cartao_familiar import PERFIL_CARTAO_FAMILIAR
from app.servicos.perfis_importacao.extrato_bancario import PERFIL_EXTRATO
from app.servicos.perfis_importacao.padrao import PERFIL_PADRAO

PERFIS: dict[str, PerfilImportacao] = {
    PERFIL_PADRAO.id: PERFIL_PADRAO,
    PERFIL_EXTRATO.id: PERFIL_EXTRATO,
    PERFIL_CARTAO_FAMILIAR.id: PERFIL_CARTAO_FAMILIAR,
}


def normalizar_nome_coluna(nome: str) -> str:
    """Remove acentos e padroniza nome de coluna para comparar cabeçalhos."""
    texto = str(nome).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def mapear_colunas(colunas, perfil: PerfilImportacao) -> dict[str, str]:
    """
    Traduz nomes da planilha para nomes internos com base no perfil.

    Retorna um dicionário {nome_interno: nome_original_na_planilha}.
    Levanta FormatoPlanilhaError se faltar alguma coluna obrigatória.
    """
    mapeamento: dict[str, str] = {}
    for coluna in colunas:
        normalizada = normalizar_nome_coluna(coluna)
        canonica = perfil.aliases_colunas.get(normalizada)
        if canonica and canonica not in mapeamento:
            mapeamento[canonica] = coluna

    faltando = perfil.colunas_obrigatorias - set(mapeamento.keys())
    if faltando:
        nomes = ", ".join(sorted(faltando))
        raise FormatoPlanilhaError(f"Colunas obrigatórias ausentes: {nomes}.")

    return mapeamento


def listar_perfis() -> list[PerfilImportacao]:
    return list(PERFIS.values())


def obter_perfil(perfil_id: str) -> PerfilImportacao | None:
    return PERFIS.get(perfil_id)


def detectar_perfil(colunas) -> PerfilImportacao | None:
    """
    Identifica o perfil cujas colunas obrigatórias batem com o cabeçalho.

    Em empate, prefere o perfil com mais colunas opcionais mapeadas;
    se ainda empatar e houver coluna categoria, prefere o perfil padrão.
    """
    candidatos: list[tuple[PerfilImportacao, dict[str, str], int]] = []

    for perfil in PERFIS.values():
        try:
            mapeamento = mapear_colunas(colunas, perfil)
        except FormatoPlanilhaError:
            continue

        if perfil.id == "controle_cartao_familiar" and "pessoa" not in mapeamento:
            continue

        opcionais_mapeadas = sum(
            1 for coluna in perfil.colunas_opcionais if coluna in mapeamento
        )
        candidatos.append((perfil, mapeamento, opcionais_mapeadas))

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda item: (
            item[2],
            1 if item[0].id == "controle_cartao_familiar" else 0,
            1 if item[0].id == "padrao" and "categoria" in item[1] else 0,
        ),
        reverse=True,
    )
    return candidatos[0][0]


__all__ = [
    "FormatoPlanilhaError",
    "PerfilImportacao",
    "PERFIS",
    "detectar_perfil",
    "listar_perfis",
    "mapear_colunas",
    "normalizar_nome_coluna",
    "obter_perfil",
]
