from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from app.servicos.importacao import (
    FormatoPlanilhaError,
    _mapear_colunas,
    _normalizar_nome_coluna,
    _parse_bool,
    _parse_data,
    _parse_valor,
    _validar_linha,
    importar_transacoes,
    ler_planilha,
)


def test_normalizar_nome_coluna():
    assert _normalizar_nome_coluna(" Descrição ") == "descricao"
    assert _normalizar_nome_coluna("Data Compra") == "data compra"
    assert _normalizar_nome_coluna("Pago?") == "pago?"


def test_mapear_colunas_com_aliases():
    colunas = ["Data", "Descrição", "Categoria", "Valor", "Pago"]
    mapeamento = _mapear_colunas(colunas)
    assert set(mapeamento.keys()) == {"data", "descricao", "categoria", "valor", "pago"}


def test_mapear_colunas_faltando_obrigatoria():
    with pytest.raises(FormatoPlanilhaError, match="Colunas obrigatórias"):
        _mapear_colunas(["data", "descricao"])


def test_parse_data_formatos():
    assert _parse_data("2026-07-13") == date(2026, 7, 13)
    assert _parse_data("13/07/2026") == date(2026, 7, 13)
    assert _parse_data("13-07-2026") == date(2026, 7, 13)
    assert _parse_data("invalido") is None
    assert _parse_data(None) is None


def test_parse_valor_formatos():
    assert _parse_valor("45,90") == Decimal("45.90")
    assert _parse_valor("1.234,56") == Decimal("1234.56")
    assert _parse_valor("R$ 10,00") == Decimal("10.00")
    assert _parse_valor("45.90") == Decimal("45.90")
    assert _parse_valor("0") is None
    assert _parse_valor("-5") is None
    assert _parse_valor("abc") is None


def test_parse_bool():
    assert _parse_bool("sim") is True
    assert _parse_bool("Sim") is True
    assert _parse_bool("nao") is False
    assert _parse_bool("não") is False
    assert _parse_bool("true") is True
    assert _parse_bool("") is False
    assert _parse_bool(None) is False


def _linha_series(dados: dict) -> pd.Series:
    return pd.Series(dados)


def test_validar_linha_valida():
    row = _linha_series(
        {
            "data": "2026-07-13",
            "descricao": "Almoço",
            "categoria": "Alimentação",
            "valor": "45,90",
            "pago": "sim",
        }
    )
    mapeamento = {
        "data": "data",
        "descricao": "descricao",
        "categoria": "categoria",
        "valor": "valor",
        "pago": "pago",
        "pago_por_terceiro": "pago_por_terceiro",
        "nome_terceiro": "nome_terceiro",
    }
    mapa = {"alimentacao": 1}
    dados, erro = _validar_linha(row, 2, mapeamento, mapa)
    assert erro is None
    assert dados["descricao"] == "Almoço"
    assert dados["categoria_id"] == 1
    assert dados["valor"] == Decimal("45.90")
    assert dados["pago"] is True


def test_validar_linha_categoria_inexistente():
    row = _linha_series(
        {
            "data": "2026-07-13",
            "descricao": "Teste",
            "categoria": "Inexistente",
            "valor": "10.00",
        }
    )
    mapeamento = {
        "data": "data",
        "descricao": "descricao",
        "categoria": "categoria",
        "valor": "valor",
    }
    _, erro = _validar_linha(row, 2, mapeamento, {"alimentacao": 1})
    assert "não encontrada" in erro


def test_validar_linha_terceiro_sem_nome():
    row = _linha_series(
        {
            "data": "2026-07-13",
            "descricao": "Teste",
            "categoria": "Alimentação",
            "valor": "10.00",
            "pago_por_terceiro": "sim",
        }
    )
    mapeamento = {
        "data": "data",
        "descricao": "descricao",
        "categoria": "categoria",
        "valor": "valor",
        "pago_por_terceiro": "pago_por_terceiro",
        "nome_terceiro": "nome_terceiro",
    }
    _, erro = _validar_linha(row, 2, mapeamento, {"alimentacao": 1})
    assert "terceiro" in erro.lower()


def test_ler_planilha_csv():
    conteudo = b"data,descricao,categoria,valor\n2026-07-13,Teste,Alimentacao,10.00\n"
    df = ler_planilha(BytesIO(conteudo), "teste.csv")
    assert len(df) == 1
    assert df.iloc[0]["descricao"] == "Teste"


def test_ler_planilha_extensao_invalida():
    with pytest.raises(FormatoPlanilhaError, match="Formato não suportado"):
        ler_planilha(BytesIO(b""), "teste.txt")


@patch("app.servicos.importacao.criar_transacao")
@patch("app.servicos.importacao.mapa_nome_para_id", return_value={"alimentacao": 1, "transporte": 2})
def test_importar_transacoes_parcial(mock_mapa, mock_criar):
    csv = (
        "data,descricao,categoria,valor\n"
        "2026-07-10,Supermercado,Alimentação,125.50\n"
        "2026-07-11,,Transporte,32.00\n"
        "2026-07-12,Invalida,Inexistente,10.00\n"
    )
    resultado = importar_transacoes("user-id", BytesIO(csv.encode()), "planilha.csv")
    assert resultado["importadas"] == 1
    assert len(resultado["erros"]) == 2
    mock_criar.assert_called_once()
    assert mock_criar.call_args.kwargs["origem"] == "importacao"


def test_importar_planilha_vazia():
    csv = "data,descricao,categoria,valor\n"
    resultado = importar_transacoes("user-id", BytesIO(csv.encode()), "vazia.csv")
    assert resultado["importadas"] == 0
    assert resultado["erros"][0]["mensagem"] == "Planilha vazia."
