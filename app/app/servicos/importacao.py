import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from app.servicos.categorias import mapa_nome_para_id
from app.servicos.transacoes import CategoriaInvalidaError, criar_transacao

COLUNAS_OBRIGATORIAS = {"data", "descricao", "categoria", "valor"}
COLUNAS_OPCIONAIS = {"pago", "pago_por_terceiro", "nome_terceiro"}

ALIASES_COLUNAS = {
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
}

FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


class FormatoPlanilhaError(Exception):
    pass


def _normalizar_nome_coluna(nome: str) -> str:
    texto = str(nome).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def _mapear_colunas(colunas) -> dict[str, str]:
    mapeamento: dict[str, str] = {}
    for coluna in colunas:
        normalizada = _normalizar_nome_coluna(coluna)
        canonica = ALIASES_COLUNAS.get(normalizada)
        if canonica and canonica not in mapeamento:
            mapeamento[canonica] = coluna

    faltando = COLUNAS_OBRIGATORIAS - set(mapeamento.keys())
    if faltando:
        nomes = ", ".join(sorted(faltando))
        raise FormatoPlanilhaError(f"Colunas obrigatórias ausentes: {nomes}.")

    return mapeamento


def _celula_vazia(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and pd.isna(valor):
        return True
    return str(valor).strip() == ""


def _linha_vazia(row: pd.Series) -> bool:
    return all(_celula_vazia(valor) for valor in row)


def _parse_data(valor) -> date | None:
    if _celula_vazia(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if hasattr(valor, "date") and callable(valor.date):
        try:
            return valor.date()
        except (ValueError, TypeError):
            pass

    texto = str(valor).strip()
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _parse_valor(valor) -> Decimal | None:
    if _celula_vazia(valor):
        return None
    if isinstance(valor, (int, float)) and not (isinstance(valor, float) and pd.isna(valor)):
        try:
            resultado = Decimal(str(valor))
            return resultado if resultado > 0 else None
        except InvalidOperation:
            return None

    texto = str(valor).strip().upper().replace("R$", "").replace(" ", "")
    if not texto:
        return None

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        resultado = Decimal(texto)
    except InvalidOperation:
        return None
    return resultado if resultado > 0 else None


def _parse_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if _celula_vazia(valor):
        return False
    texto = str(valor).strip().lower()
    return texto in ("true", "1", "on", "yes", "sim", "s")


def _valor_celula(row: pd.Series, coluna: str | None):
    if coluna is None or coluna not in row.index:
        return None
    return row[coluna]


def _validar_linha(
    row: pd.Series,
    numero_linha: int,
    mapeamento: dict[str, str],
    mapa_categorias: dict[str, int],
) -> tuple[dict | None, str | None]:
    data = _parse_data(_valor_celula(row, mapeamento.get("data")))
    if data is None:
        return None, "Data inválida ou ausente."

    descricao_raw = _valor_celula(row, mapeamento.get("descricao"))
    if _celula_vazia(descricao_raw):
        return None, "Descrição é obrigatória."
    descricao = str(descricao_raw).strip()

    categoria_raw = _valor_celula(row, mapeamento.get("categoria"))
    if _celula_vazia(categoria_raw):
        return None, "Categoria é obrigatória."
    categoria_chave = _normalizar_nome_coluna(str(categoria_raw))
    categoria_id = mapa_categorias.get(categoria_chave)
    if categoria_id is None:
        return None, f"Categoria '{categoria_raw}' não encontrada."

    valor = _parse_valor(_valor_celula(row, mapeamento.get("valor")))
    if valor is None:
        return None, "Valor inválido ou ausente."

    pago = _parse_bool(_valor_celula(row, mapeamento.get("pago")))
    pago_por_terceiro = _parse_bool(
        _valor_celula(row, mapeamento.get("pago_por_terceiro"))
    )

    nome_terceiro_raw = _valor_celula(row, mapeamento.get("nome_terceiro"))
    nome_terceiro = (
        None if _celula_vazia(nome_terceiro_raw) else str(nome_terceiro_raw).strip()
    )

    if pago_por_terceiro and not nome_terceiro:
        return None, "Nome do terceiro é obrigatório quando pago por terceiro."

    if not pago_por_terceiro:
        nome_terceiro = None

    return {
        "data_compra": data,
        "descricao": descricao,
        "categoria_id": categoria_id,
        "valor": valor,
        "pago": pago,
        "pago_por_terceiro": pago_por_terceiro,
        "nome_terceiro": nome_terceiro,
    }, None


def ler_planilha(arquivo: BinaryIO, nome_arquivo: str) -> pd.DataFrame:
    nome = nome_arquivo.lower()
    if nome.endswith(".csv"):
        conteudo = arquivo.read()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return pd.read_csv(BytesIO(conteudo), encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise FormatoPlanilhaError("Não foi possível ler o arquivo CSV.")
    if nome.endswith(".xlsx"):
        return pd.read_excel(arquivo, engine="openpyxl")
    raise FormatoPlanilhaError("Formato não suportado. Use .csv ou .xlsx.")


def importar_transacoes(
    usuario_id: str, arquivo: BinaryIO, nome_arquivo: str
) -> dict:
    erros: list[dict] = []
    importadas = 0

    try:
        df = ler_planilha(arquivo, nome_arquivo)
    except FormatoPlanilhaError as exc:
        return {"importadas": 0, "erros": [{"linha": 0, "mensagem": str(exc)}]}

    if df.empty:
        return {
            "importadas": 0,
            "erros": [{"linha": 0, "mensagem": "Planilha vazia."}],
        }

    try:
        mapeamento = _mapear_colunas(df.columns)
    except FormatoPlanilhaError as exc:
        return {"importadas": 0, "erros": [{"linha": 0, "mensagem": str(exc)}]}

    mapa_categorias = mapa_nome_para_id()

    for indice, row in df.iterrows():
        numero_linha = int(indice) + 2
        if _linha_vazia(row):
            continue

        dados, erro = _validar_linha(row, numero_linha, mapeamento, mapa_categorias)
        if erro:
            erros.append({"linha": numero_linha, "mensagem": erro})
            continue

        try:
            criar_transacao(usuario_id, origem="importacao", **dados)
            importadas += 1
        except CategoriaInvalidaError:
            erros.append({"linha": numero_linha, "mensagem": "Categoria inválida."})

    return {"importadas": importadas, "erros": erros}
