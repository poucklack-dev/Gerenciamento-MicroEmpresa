from datetime import date
from decimal import Decimal

import pytest

from backend.rh import build_payroll, parse_competencia


def test_folha_consolida_salarios_e_setores():
    rows = [
        (1, "Ana", "Analista", "Financeiro", Decimal("3500.00")),
        (2, "Bruno", "Assistente", "Financeiro", Decimal("2500.00")),
        (3, "Clara", "Vendas", "Comercial", Decimal("4000.00")),
    ]
    folha = build_payroll(rows, date(2026, 9, 1))

    assert folha["total_salarios"] == 10_000
    assert folha["colaboradores_ativos"] == 3
    assert folha["salario_medio"] == 3333.33
    assert folha["setores"][0] == {"setor": "Financeiro", "colaboradores": 2, "salarios": 6000.0}


def test_folha_identifica_cadastro_sem_salario():
    folha = build_payroll([(1, "Ana", None, None, None)], date(2026, 9, 1))

    assert folha["sem_salario_informado"] == 1
    assert folha["colaboradores"][0]["setor"] == "Sem setor"


def test_competencia_invalida_e_rejeitada():
    with pytest.raises(ValueError):
        parse_competencia("09/2026")
