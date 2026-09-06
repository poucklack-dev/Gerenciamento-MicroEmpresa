from datetime import datetime

import pytest

from backend.banco_de_horas import (
    calculate_balance,
    calculate_expected,
    calculate_record_minutes,
    competence,
    format_minutes,
    official_worked,
    parse_minutes,
)


def test_saldo_zerado_quando_realizado_igual_previsto():
    assert calculate_balance(10_320, 10_320)["saldo_minutos"] == 0


def test_saldo_positivo_em_minutos():
    result = calculate_balance(10_320, 10_710)
    assert result["saldo_minutos"] == 390
    assert result["extras_minutos"] == 390


def test_saldo_negativo_em_minutos():
    result = calculate_balance(10_320, 10_080)
    assert result["saldo_minutos"] == -240
    assert result["negativas_minutos"] == 240


def test_carga_calculada_com_ajuste_assinado():
    assert calculate_expected(480, 22, [-240]) == 10_320


def test_carga_direta_aceita_mais_de_24_horas():
    assert calculate_expected(direct_minutes=parse_minutes("172:00")) == 10_320


def test_total_manual_e_fonte_oficial():
    assert official_worked("manual", 600, 480) == 480


def test_registros_detalhados_descontam_intervalo():
    start = datetime(2026, 9, 1, 8)
    end = datetime(2026, 9, 1, 17, 30)
    assert calculate_record_minutes(start, end, 60) == 510


def test_manual_e_registros_nunca_sao_somados():
    assert official_worked("registros", 600, 480) == 600
    assert official_worked("manual", 600, 480) != 1_080


def test_anulado_fica_fora_dos_totais():
    result = calculate_balance(480, 600, excluded=True)
    assert result["considerar_nos_totais"] is False
    assert result["extras_minutos"] == 0


def test_restaurado_volta_aos_totais():
    assert calculate_balance(480, 600, excluded=False)["considerar_nos_totais"] is True


def test_formatacao_acima_de_24_horas():
    assert format_minutes(10_320) == "172h00"


def test_agregacao_preserva_saldo_negativo():
    saldos = [calculate_balance(600, 540)["saldo_minutos"], calculate_balance(600, 570)["saldo_minutos"]]
    assert sum(saldos) == -90
    assert format_minutes(sum(saldos), True) == "-1h30"


def test_periodo_mensal_normalizado():
    assert competence("2026-09").isoformat() == "2026-09-01"


def test_entrada_invalida_e_rejeitada():
    with pytest.raises(ValueError):
        parse_minutes("8:75")


def test_turno_que_cruza_meia_noite():
    start = datetime(2026, 9, 1, 22)
    end = datetime(2026, 9, 1, 6)
    assert calculate_record_minutes(start, end, 60) == 420
