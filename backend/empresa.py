import re
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session
from flask_login import login_required
from core.auth import is_admin_role
from core.database import get_conn

empresa_bp = Blueprint("empresa", __name__)
FIELDS = ("nome_fantasia", "razao_social", "cpf_cnpj", "telefone", "email", "endereco", "cidade", "estado", "cep", "segmento", "responsavel", "cor_institucional")

def company_context():
    fallback = {"nome_fantasia": "Aurora Gestão", "cor_institucional": "#167052"}
    if current_app.config.get("TESTING"):
        return {"empresa": fallback}
    try:
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("SELECT nome_fantasia, cor_institucional FROM empresa WHERE id = 1")
            row = cur.fetchone()
            if row:
                return {"empresa": {"nome_fantasia": row[0], "cor_institucional": row[1] or "#167052"}}
        finally:
            cur.close()
    except Exception:
        pass
    return {"empresa": fallback}

@empresa_bp.get("/empresa")
def page():
    if "usuarios" not in session:
        return redirect("/login")
    return render_template("empresa.html")

@empresa_bp.get("/api/empresa")
@login_required
def get_empresa():
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"SELECT {', '.join(FIELDS)} FROM empresa WHERE id = 1")
        row = cur.fetchone()
        return jsonify(dict(zip(FIELDS, row)) if row else {})
    finally: cur.close(); conn.close()

@empresa_bp.put("/api/empresa")
@login_required
def update_empresa():
    if not is_admin_role((session.get("usuarios") or {}).get("cargo")):
        return jsonify({"error": "Apenas administradores podem alterar a empresa."}), 403
    data = request.get_json(silent=True) or {}
    values = [str(data.get(field, "")).strip() or None for field in FIELDS]
    if not values[0]: return jsonify({"error": "Nome fantasia é obrigatório."}), 400
    if values[7]: values[7] = values[7].upper()[:2]
    if values[11] and not re.fullmatch(r"#[0-9A-Fa-f]{6}", values[11]): return jsonify({"error": "Cor institucional inválida."}), 400
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"UPDATE empresa SET {', '.join(f'{field} = %s' for field in FIELDS)}, atualizado_em = NOW() WHERE id = 1", values)
        conn.commit()
        return jsonify({"success": True, "message": "Dados da empresa atualizados."})
    finally: cur.close(); conn.close()
