# backend/pages.py
from flask import Blueprint, render_template, redirect, session

pages_bp = Blueprint("pages", __name__)

def _gate():
    if "usuarios" not in session:
        return redirect("/login")
    return None

@pages_bp.get("/dashboard")
def dashboard_page():
    g = _gate()
    if g: return g
    return render_template("dashboard.html")

@pages_bp.get("/clientes")
def clientes_page():
    g = _gate()
    if g: return g
    return render_template("clientes.html")

@pages_bp.get("/colaboradores")
def colaboradores_page():
    g = _gate()
    if g: return g
    return render_template("colaboradores.html")

@pages_bp.get("/equipe_campo")
def equipe_campo_page():
    g = _gate()
    if g: return g
    return render_template("equipe_campo.html")

@pages_bp.get("/contas_pagar")
def contas_pagar_page():
    g = _gate()
    if g: return g
    return render_template("contas_pagar.html")

@pages_bp.get("/contas_receber")
def contas_receber_page():
    g = _gate()
    if g: return g
    return render_template("contas_receber.html")

@pages_bp.get("/quilometragem")
def quilometragem_page():
    g = _gate()
    if g: return g
    return render_template("quilometragem.html")

@pages_bp.get("/financeiro")
def financeiro_page():
    g = _gate()
    if g: return g
    return render_template("financeiro.html")

@pages_bp.get("/contratos")
def contratos_page():
    g = _gate()
    if g: return g
    return render_template("contratos.html")

@pages_bp.get("/documentos")
def documentos_page():
    g = _gate()
    if g: return g
    return render_template("documentos.html")

@pages_bp.get("/fornecedores")
def fornecedores_page():
    g = _gate()
    if g: return g
    return render_template("fornecedores.html")

@pages_bp.get("/perfil")
def perfil_page():
    g = _gate()
    if g: return g
    return render_template("perfil.html")

@pages_bp.get("/banco_de_horas")
def banco_de_horas_page():
    g = _gate()
    if g: return g
    return render_template("banco_de_horas.html")
