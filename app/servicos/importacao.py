"""

Serviço de importação de planilhas (CSV / XLSX).



Fluxo principal:

    1. Ler o arquivo enviado pelo usuário

    2. Detectar ou aplicar o perfil de importação

    3. Mapear os nomes das colunas para um formato interno conhecido

    4. Validar cada linha (data, descrição, categoria, valor...)

    5. Salvar as linhas válidas no banco com origem='importacao'



Uma linha inválida gera um erro no resumo, mas NÃO impede

as demais linhas de serem importadas.

"""



from collections import defaultdict, deque
from datetime import date, datetime, timedelta

from decimal import Decimal, InvalidOperation

from io import BytesIO

from typing import BinaryIO



import pandas as pd



from app.servicos.categorias import mapa_nome_para_id

from app.servicos.perfis_importacao import (

    FormatoPlanilhaError,

    PerfilImportacao,

    detectar_perfil,

    mapear_colunas,

    normalizar_nome_coluna,

    obter_perfil,

)

from app.servicos.perfis_importacao.padrao import PERFIL_PADRAO

from app.servicos.planilha_cartao_familiar import (
    detectar_formato_cartao_familiar,
    ler_planilha_cartao_familiar,
)

from app.servicos.transacoes import (
    CategoriaInvalidaError,
    TransacaoNaoEncontradaError,
    atualizar_transacao,
    criar_transacao,
    listar_para_deduplicacao,
)



# Re-export para compatibilidade com testes existentes

COLUNAS_OBRIGATORIAS = PERFIL_PADRAO.colunas_obrigatorias

COLUNAS_OPCIONAIS = PERFIL_PADRAO.colunas_opcionais

ALIASES_COLUNAS = PERFIL_PADRAO.aliases_colunas

FORMATOS_DATA = PERFIL_PADRAO.formatos_data

_MESES_PARA_NUMERO = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}





def _normalizar_nome_coluna(nome: str) -> str:

    return normalizar_nome_coluna(nome)





def _mapear_colunas(colunas, perfil: PerfilImportacao | None = None) -> dict[str, str]:

    if perfil is None:

        perfil = PERFIL_PADRAO

    return mapear_colunas(colunas, perfil)





# --- Helpers para ler células ---





def _celula_vazia(valor) -> bool:

    """Verifica se uma célula está vazia (None, NaN ou texto em branco)."""

    if valor is None:

        return True

    if isinstance(valor, float) and pd.isna(valor):

        return True

    return str(valor).strip() == ""





def _linha_vazia(row: pd.Series) -> bool:

    """Retorna True se todas as células da linha estiverem vazias."""

    return all(_celula_vazia(valor) for valor in row)





def _valor_celula(row: pd.Series, coluna: str | None):

    """

    Lê o valor de uma célula pelo nome da coluna na planilha.



    Retorna None se a coluna não existir (colunas opcionais ausentes

    no cabeçalho são tratadas como vazias).

    """

    if coluna is None or coluna not in row.index:

        return None

    return row[coluna]





# --- Conversão de valores (data, valor, booleano) ---





def _parse_data(valor, perfil: PerfilImportacao) -> date | None:

    """Converte texto ou datetime da planilha em um objeto date."""

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

    for formato in perfil.formatos_data:

        try:

            return datetime.strptime(texto, formato).date()

        except ValueError:

            continue

    return None





def _limpar_texto_monetario(texto: str) -> str:

    """

    Remove símbolos e ajusta vírgula/ponto para formato numérico.



    Ex.: "R$ 1.234,56" vira "1234.56"

    """

    texto = texto.strip().upper().replace("R$", "").replace(" ", "")

    if not texto:

        return texto



    if "," in texto and "." in texto:

        # Formato BR (1.234,56): vírgula é decimal

        if texto.rfind(",") > texto.rfind("."):

            texto = texto.replace(".", "").replace(",", ".")

        else:

            # Formato US (1,234.56): ponto é decimal

            texto = texto.replace(",", "")

    elif "," in texto:

        texto = texto.replace(",", ".")



    return texto





def _parse_valor(valor, perfil: PerfilImportacao) -> Decimal | None:

    """Converte texto como 'R$ 1.234,56' ou '45.90' em número Decimal."""

    if _celula_vazia(valor):

        return None

    if isinstance(valor, (int, float)) and not (isinstance(valor, float) and pd.isna(valor)):

        try:

            resultado = Decimal(str(valor))

            if perfil.valor_absoluto:

                resultado = abs(resultado)

            return resultado if resultado > 0 else None

        except InvalidOperation:

            return None



    texto = _limpar_texto_monetario(str(valor))

    if not texto:

        return None



    try:

        resultado = Decimal(texto)

    except InvalidOperation:

        return None



    if perfil.valor_absoluto:

        resultado = abs(resultado)

    return resultado if resultado > 0 else None





def _data_primeiro_dia_mes(nome_mes: str, ano: int | None = None) -> date | None:
    mes = _MESES_PARA_NUMERO.get(_normalizar_nome_coluna(nome_mes))
    if mes is None:
        return None
    return date(ano or 2026, mes, 1)


def _resolver_categoria(
    categoria_raw,
    mapa_categorias: dict[str, int],
    perfil: PerfilImportacao,
) -> tuple[int | None, str | None]:
    categoria_chave = _normalizar_nome_coluna(str(categoria_raw))
    if perfil.mapeamento_categorias:
        categoria_mapeada = perfil.mapeamento_categorias.get(categoria_chave)
        if categoria_mapeada:
            categoria_chave = _normalizar_nome_coluna(categoria_mapeada)
    categoria_id = mapa_categorias.get(categoria_chave)
    if categoria_id is None:
        return None, f"Categoria '{categoria_raw}' não encontrada."
    return categoria_id, None


def _resolver_pessoa(
    row: pd.Series,
    mapeamento: dict[str, str],
) -> tuple[bool, str | None]:
    pessoa_raw = _valor_celula(row, mapeamento.get("pessoa"))
    if _celula_vazia(pessoa_raw):
        pago_por_terceiro = _parse_bool(
            _valor_celula(row, mapeamento.get("pago_por_terceiro"))
        )
        nome_terceiro_raw = _valor_celula(row, mapeamento.get("nome_terceiro"))
        nome_terceiro = (
            None
            if _celula_vazia(nome_terceiro_raw)
            else str(nome_terceiro_raw).strip()
        )
        return pago_por_terceiro, nome_terceiro

    pessoa_norm = _normalizar_nome_coluna(str(pessoa_raw))
    if pessoa_norm == "eu":
        return False, None
    return True, str(pessoa_raw).strip()


def _parse_bool(valor) -> bool:

    """Converte 'sim', 'true', '1' etc. em True; qualquer outro valor vazio vira False."""

    if isinstance(valor, bool):

        return valor

    if _celula_vazia(valor):

        return False

    texto = str(valor).strip().lower()

    return texto in ("true", "1", "on", "yes", "sim", "s")





# --- Validação de linha e importação principal ---





def _validar_linha(

    row: pd.Series,

    numero_linha: int,

    mapeamento: dict[str, str],

    mapa_categorias: dict[str, int],

    perfil: PerfilImportacao,

    data_resolvida: date | None = None,

) -> tuple[dict | None, str | None]:

    """

    Valida uma linha da planilha e monta o dict para criar_transacao().



    Retorna (dados, None) se válida, ou (None, mensagem_erro) se inválida.

    """

    data = _parse_data(_valor_celula(row, mapeamento.get("data")), perfil)

    if data is None:

        data = data_resolvida

    if data is None:

        return None, "Data inválida ou ausente."



    descricao_raw = _valor_celula(row, mapeamento.get("descricao"))

    if _celula_vazia(descricao_raw):

        return None, "Descrição é obrigatória."

    descricao = str(descricao_raw).strip()

    observacoes_raw = _valor_celula(row, mapeamento.get("observacoes"))

    if not _celula_vazia(observacoes_raw):

        descricao = f"{descricao} (obs: {str(observacoes_raw).strip()})"



    coluna_categoria = mapeamento.get("categoria")

    if coluna_categoria:

        categoria_raw = _valor_celula(row, coluna_categoria)

        if _celula_vazia(categoria_raw):

            return None, "Categoria é obrigatória."

        categoria_id, erro_categoria = _resolver_categoria(

            categoria_raw, mapa_categorias, perfil

        )

        if erro_categoria:

            return None, erro_categoria

    elif perfil.categoria_padrao:

        categoria_id, erro_categoria = _resolver_categoria(

            perfil.categoria_padrao, mapa_categorias, perfil

        )

        if erro_categoria:

            return None, f"Categoria padrão '{perfil.categoria_padrao}' não encontrada."

    else:

        return None, "Categoria é obrigatória."



    valor = _parse_valor(_valor_celula(row, mapeamento.get("valor")), perfil)

    if valor is None:

        return None, "Valor inválido ou ausente."



    pago = _parse_bool(_valor_celula(row, mapeamento.get("pago")))

    pago_por_terceiro, nome_terceiro = _resolver_pessoa(row, mapeamento)



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





# --- Leitura do arquivo (CSV / XLSX) ---





def ler_planilha(arquivo: BinaryIO, nome_arquivo: str) -> pd.DataFrame:

    """

    Lê um arquivo CSV ou XLSX e retorna um DataFrame do pandas.



    Levanta FormatoPlanilhaError se a extensão não for suportada.

    """

    nome = nome_arquivo.lower()

    if nome.endswith(".csv"):

        conteudo = arquivo.read()

        # Tenta encodings comuns — planilhas BR costumam vir em utf-8 ou latin-1

        for encoding in ("utf-8-sig", "utf-8", "latin-1"):

            try:

                return pd.read_csv(BytesIO(conteudo), encoding=encoding)

            except UnicodeDecodeError:

                continue

        raise FormatoPlanilhaError("Não foi possível ler o arquivo CSV.")

    if nome.endswith(".xlsx"):

        conteudo = arquivo.read()

        arquivo.seek(0)

        if detectar_formato_cartao_familiar(BytesIO(conteudo)):

            return ler_planilha_cartao_familiar(BytesIO(conteudo))

        return pd.read_excel(BytesIO(conteudo), engine="openpyxl")

    raise FormatoPlanilhaError("Formato não suportado. Use .csv ou .xlsx.")





def gerar_chave_deduplicacao(dados: dict) -> tuple:
    """
    Chave estável para identificar a mesma compra entre importações.

    Usa data + descrição + categoria + valor + pessoa (nome_terceiro).
    O campo pago fica de fora — pode mudar entre exportações mensais.
    """
    nome = dados.get("nome_terceiro")
    return (
        dados["data_compra"],
        dados["descricao"].strip(),
        dados["categoria_id"],
        dados["valor"].quantize(Decimal("0.01")),
        nome.strip() if nome else None,
    )


def _montar_indice_deduplicacao(
    registros: list[dict],
) -> dict[tuple, deque[dict]]:
    """Agrupa transações existentes por chave; fila suporta compras repetidas."""
    indice: dict[tuple, deque[dict]] = defaultdict(deque)
    for registro in registros:
        indice[gerar_chave_deduplicacao(registro)].append(registro)
    return indice


def _resolver_data_linha(
    row: pd.Series,
    mapeamento: dict[str, str],
    perfil: PerfilImportacao,
    ultima_data_por_aba: dict[str, date],
) -> date | None:
    aba_mes = row["_aba_mes"] if "_aba_mes" in row.index else None
    aba_ano = row["_aba_ano"] if "_aba_ano" in row.index else None
    data_celula = _parse_data(_valor_celula(row, mapeamento.get("data")), perfil)

    if data_celula:
        if aba_mes is not None and not _celula_vazia(aba_mes):
            ultima_data_por_aba[str(aba_mes)] = data_celula
        return data_celula

    if aba_mes is not None and not _celula_vazia(aba_mes):
        chave_aba = str(aba_mes)
        if chave_aba in ultima_data_por_aba:
            return ultima_data_por_aba[chave_aba]
        ano = None
        if aba_ano is not None and not _celula_vazia(aba_ano):
            ano = int(aba_ano)
        return _data_primeiro_dia_mes(chave_aba, ano)

    return None


def _coletar_linhas_validas(
    df: pd.DataFrame,
    mapeamento: dict[str, str],
    mapa_categorias: dict[str, int],
    perfil: PerfilImportacao,
) -> tuple[list[tuple[int, dict]], list[dict]]:
    linhas_validas: list[tuple[int, dict]] = []
    erros: list[dict] = []
    ultima_data_por_aba: dict[str, date] = {}

    for indice, row in df.iterrows():
        numero_linha = int(indice) + 2
        if _linha_vazia(row):
            continue

        data_resolvida = _resolver_data_linha(
            row, mapeamento, perfil, ultima_data_por_aba
        )
        dados, erro = _validar_linha(
            row,
            numero_linha,
            mapeamento,
            mapa_categorias,
            perfil,
            data_resolvida=data_resolvida,
        )
        if erro:
            erros.append({"linha": numero_linha, "mensagem": erro})
            continue
        linhas_validas.append((numero_linha, dados))

    return linhas_validas, erros


def _persistir_com_deduplicacao(
    usuario_id: str,
    linhas_validas: list[tuple[int, dict]],
    indice: dict[tuple, deque[dict]],
) -> tuple[int, int, int, list[dict]]:
    """
    Insere, atualiza ou ignora cada linha com base no índice de duplicatas.

    Duplicata com pago=true → ignora; pago=false → atualiza; sem match → insere.
    """
    importadas = 0
    atualizadas = 0
    ignoradas = 0
    erros: list[dict] = []

    for numero_linha, dados in linhas_validas:
        chave = gerar_chave_deduplicacao(dados)
        fila = indice.get(chave)

        try:
            if fila:
                existente = fila.popleft()
                if existente["pago"]:
                    ignoradas += 1
                else:
                    atualizar_transacao(
                        usuario_id,
                        existente["id"],
                        data_compra=dados["data_compra"],
                        descricao=dados["descricao"],
                        categoria_id=dados["categoria_id"],
                        valor=dados["valor"],
                        pago=dados["pago"],
                        pago_por_terceiro=dados["pago_por_terceiro"],
                        nome_terceiro=dados["nome_terceiro"],
                    )
                    atualizadas += 1
            else:
                criar_transacao(usuario_id, origem="importacao", **dados)
                importadas += 1
        except CategoriaInvalidaError:
            erros.append({"linha": numero_linha, "mensagem": "Categoria inválida."})
        except TransacaoNaoEncontradaError:
            erros.append({"linha": numero_linha, "mensagem": "Transação não encontrada."})

    return importadas, atualizadas, ignoradas, erros


def _resultado_importacao_vazio(
    erros: list[dict] | None = None,
    perfil: PerfilImportacao | None = None,
) -> dict:
    return {
        "importadas": 0,
        "atualizadas": 0,
        "ignoradas": 0,
        "erros": erros or [],
        "perfil_usado": perfil.id if perfil else None,
        "perfil_nome": perfil.nome if perfil else None,
    }


def _resolver_perfil(colunas, perfil_id: str) -> tuple[PerfilImportacao | None, str | None]:

    if perfil_id == "auto":

        perfil = detectar_perfil(colunas)

        if perfil is None:

            return None, "Não foi possível detectar o perfil. Escolha manualmente."

        return perfil, None



    perfil = obter_perfil(perfil_id)

    if perfil is None:

        return None, f"Perfil de importação inválido: {perfil_id}."

    return perfil, None





def importar_transacoes(

    usuario_id: str,

    arquivo: BinaryIO,

    nome_arquivo: str,

    perfil_id: str = "auto",

) -> dict:

    """

    Função principal: importa transações de uma planilha.



    Retorna:

        {

            "importadas": int,

            "atualizadas": int,

            "ignoradas": int,

            "erros": [{"linha": int, "mensagem": str}, ...],

            "perfil_usado": str | None,

        }

    """

    # 1. Ler o arquivo

    try:

        df = ler_planilha(arquivo, nome_arquivo)

    except FormatoPlanilhaError as exc:

        return _resultado_importacao_vazio(

            erros=[{"linha": 0, "mensagem": str(exc)}],

        )



    if df.empty:

        return _resultado_importacao_vazio(

            erros=[{"linha": 0, "mensagem": "Planilha vazia."}],

        )



    # 2. Resolver perfil (auto-detect ou seleção manual)

    perfil, erro_perfil = _resolver_perfil(df.columns, perfil_id)

    if erro_perfil:

        return _resultado_importacao_vazio(

            erros=[{"linha": 0, "mensagem": erro_perfil}],

        )



    # 3. Mapear colunas do cabeçalho

    try:

        mapeamento = _mapear_colunas(df.columns, perfil)

    except FormatoPlanilhaError as exc:

        return _resultado_importacao_vazio(

            erros=[{"linha": 0, "mensagem": str(exc)}],

            perfil=perfil,

        )



    # 4. Validar linhas e carregar categorias

    mapa_categorias = mapa_nome_para_id()

    linhas_validas, erros = _coletar_linhas_validas(

        df, mapeamento, mapa_categorias, perfil

    )



    if not linhas_validas:

        return _resultado_importacao_vazio(erros=erros, perfil=perfil)



    # 5. Carregar transações existentes em lote (margem de 31 dias)

    datas = [dados["data_compra"] for _, dados in linhas_validas]

    data_min = min(datas) - timedelta(days=31)

    data_max = max(datas) + timedelta(days=31)

    existentes = listar_para_deduplicacao(usuario_id, data_min, data_max)

    indice = _montar_indice_deduplicacao(existentes)



    # 6. Inserir, atualizar ou ignorar com deduplicação

    importadas, atualizadas, ignoradas, erros_persistencia = _persistir_com_deduplicacao(

        usuario_id, linhas_validas, indice

    )

    erros.extend(erros_persistencia)



    return {

        "importadas": importadas,

        "atualizadas": atualizadas,

        "ignoradas": ignoradas,

        "erros": erros,

        "perfil_usado": perfil.id,

        "perfil_nome": perfil.nome,

    }


