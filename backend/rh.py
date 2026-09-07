"""Indicadores de RH usados pelo painel gerencial."""
from calendar import monthrange
from datetime import date, datetime

from flask import Blueprint, jsonify, request

from core.auth import admin_required
from core.database import get_conn


rh_bp = Blueprint("rh", __name__, url_prefix="/api/rh")


def parse_competencia(value):
    if not value:
        today = date.today()
        return today.replace(day=1)
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValueError("Competência inválida. Use AAAA-MM.") from exc


def build_payroll(rows, competencia):
    colaboradores = []
    setores = {}
    total = 0.0
    sem_salario = 0
    for employee_id, nome, cargo, setor, salario in rows:
        amount = float(salario or 0)
        total += amount
        if not salario:
            sem_salario += 1
        sector_name = setor or "Sem setor"
        bucket = setores.setdefault(sector_name, {"setor": sector_name, "colaboradores": 0, "salarios": 0.0})
        bucket["colaboradores"] += 1
        bucket["salarios"] += amount
        colaboradores.append({"id": employee_id, "nome": nome, "cargo": cargo or "Não informado", "setor": sector_name, "salario": amount})
    count = len(colaboradores)
    return {
        "competencia": competencia.strftime("%Y-%m"),
        "total_salarios": round(total, 2),
        "colaboradores_ativos": count,
        "salario_medio": round(total / count, 2) if count else 0.0,
        "sem_salario_informado": sem_salario,
        "setores": sorted(setores.values(), key=lambda item: item["salarios"], reverse=True),
        "colaboradores": colaboradores,
        "observacao": "Estimativa baseada no salário cadastral; não inclui encargos, benefícios ou descontos.",
    }


@rh_bp.get("/folha-pagamento")
@admin_required
def folha_pagamento():
    try:
        competencia = parse_competencia(request.args.get("competencia"))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    ultimo_dia = competencia.replace(day=monthrange(competencia.year, competencia.month)[1])
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, nome, cargo, setor, salario
            FROM colaboradores
            WHERE LOWER(COALESCE(status, 'ativo')) = 'ativo'
              AND (data_admissao IS NULL OR data_admissao <= %s)
              AND (data_demissao IS NULL OR data_demissao >= %s)
            ORDER BY nome
            """,
            (ultimo_dia, competencia),
        )
        return jsonify(build_payroll(cur.fetchall(), competencia))
    finally:
        cur.close()
        conn.close()
