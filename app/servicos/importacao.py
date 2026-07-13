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



from datetime import date, datetime

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

from app.servicos.transacoes import CategoriaInvalidaError, criar_transacao



# Re-export para compatibilidade com testes existentes

COLUNAS_OBRIGATORIAS = PERFIL_PADRAO.colunas_obrigatorias

COLUNAS_OPCIONAIS = PERFIL_PADRAO.colunas_opcionais

ALIASES_COLUNAS = PERFIL_PADRAO.aliases_colunas

FORMATOS_DATA = PERFIL_PADRAO.formatos_data





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

) -> tuple[dict | None, str | None]:

    """

    Valida uma linha da planilha e monta o dict para criar_transacao().



    Retorna (dados, None) se válida, ou (None, mensagem_erro) se inválida.

    """

    data = _parse_data(_valor_celula(row, mapeamento.get("data")), perfil)

    if data is None:

        return None, "Data inválida ou ausente."



    descricao_raw = _valor_celula(row, mapeamento.get("descricao"))

    if _celula_vazia(descricao_raw):

        return None, "Descrição é obrigatória."

    descricao = str(descricao_raw).strip()



    coluna_categoria = mapeamento.get("categoria")

    if coluna_categoria:

        categoria_raw = _valor_celula(row, coluna_categoria)

        if _celula_vazia(categoria_raw):

            return None, "Categoria é obrigatória."

        categoria_chave = _normalizar_nome_coluna(str(categoria_raw))

        categoria_id = mapa_categorias.get(categoria_chave)

        if categoria_id is None:

            return None, f"Categoria '{categoria_raw}' não encontrada."

    elif perfil.categoria_padrao:

        categoria_chave = _normalizar_nome_coluna(perfil.categoria_padrao)

        categoria_id = mapa_categorias.get(categoria_chave)

        if categoria_id is None:

            return None, f"Categoria padrão '{perfil.categoria_padrao}' não encontrada."

    else:

        return None, "Categoria é obrigatória."



    valor = _parse_valor(_valor_celula(row, mapeamento.get("valor")), perfil)

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

        return pd.read_excel(arquivo, engine="openpyxl")

    raise FormatoPlanilhaError("Formato não suportado. Use .csv ou .xlsx.")





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

            "erros": [{"linha": int, "mensagem": str}, ...],

            "perfil_usado": str | None,

        }

    """

    erros: list[dict] = []

    importadas = 0



    # 1. Ler o arquivo

    try:

        df = ler_planilha(arquivo, nome_arquivo)

    except FormatoPlanilhaError as exc:

        return {"importadas": 0, "erros": [{"linha": 0, "mensagem": str(exc)}], "perfil_usado": None}



    if df.empty:

        return {

            "importadas": 0,

            "erros": [{"linha": 0, "mensagem": "Planilha vazia."}],

            "perfil_usado": None,

        }



    # 2. Resolver perfil (auto-detect ou seleção manual)

    perfil, erro_perfil = _resolver_perfil(df.columns, perfil_id)

    if erro_perfil:

        return {

            "importadas": 0,

            "erros": [{"linha": 0, "mensagem": erro_perfil}],

            "perfil_usado": None,

        }



    # 3. Mapear colunas do cabeçalho

    try:

        mapeamento = _mapear_colunas(df.columns, perfil)

    except FormatoPlanilhaError as exc:

        return {

            "importadas": 0,

            "erros": [{"linha": 0, "mensagem": str(exc)}],

            "perfil_usado": perfil.id,

        }



    # 4. Carregar categorias do banco uma vez (evita consulta por linha)

    mapa_categorias = mapa_nome_para_id()



    # 5. Processar linha a linha

    for indice, row in df.iterrows():

        # +2 porque: linha 1 é o cabeçalho, e o índice do pandas começa em 0

        numero_linha = int(indice) + 2

        if _linha_vazia(row):

            continue



        dados, erro = _validar_linha(

            row, numero_linha, mapeamento, mapa_categorias, perfil

        )

        if erro:

            erros.append({"linha": numero_linha, "mensagem": erro})

            continue



        try:

            criar_transacao(usuario_id, origem="importacao", **dados)

            importadas += 1

        except CategoriaInvalidaError:

            erros.append({"linha": numero_linha, "mensagem": "Categoria inválida."})



    return {"importadas": importadas, "erros": erros, "perfil_usado": perfil.id, "perfil_nome": perfil.nome}


