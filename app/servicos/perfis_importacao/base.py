from dataclasses import dataclass


class FormatoPlanilhaError(Exception):
    """Erro no formato do arquivo (colunas faltando, extensão inválida, etc.)."""


@dataclass(frozen=True)
class PerfilImportacao:
    id: str
    nome: str
    descricao: str
    colunas_obrigatorias: frozenset[str]
    colunas_opcionais: frozenset[str]
    aliases_colunas: dict[str, str]
    formatos_data: tuple[str, ...]
    categoria_padrao: str | None = None
    valor_absoluto: bool = False
