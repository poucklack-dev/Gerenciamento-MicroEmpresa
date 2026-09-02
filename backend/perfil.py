# perfil.py — PATAGONIA • Backend Premium de Perfil de Usuário
# ==============================================================

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash
from core.database import get_conn
from core.storage import get_storage

perfil_bp = Blueprint("perfil", __name__, url_prefix="/perfil")

def get_usuario_completo(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nome, usuario, email, telefone, cargo, status, foto, criado_em
        FROM usuarios
        WHERE id = %s
    """, (user_id,))
    u = cur.fetchone()

    if not u:
        cur.close()
        conn.close()
        return None

    usuario = {
        "id": u[0],
        "nome": u[1],
        "usuario": u[2],
        "email": u[3],
        "telefone": u[4],
        "cargo": u[5],
        "status": u[6],
        "foto": u[7],
        "criado_em": u[8],
    }

    # Dados vinculados ao colaborador (não mexe em fotos)
    cur.execute("""
        SELECT id, nome, funcao, status, cnh, validade_cnh, endereco, salario, data_admissao, foto
        FROM colaboradores
        WHERE email = %s
        LIMIT 1
    """, (usuario["email"],))
    c = cur.fetchone()

    if c:
        usuario["colaborador"] = {
            "id": c[0],
            "nome": c[1],
            "funcao": c[2],
            "status": c[3],
            "cnh": c[4],
            "validade_cnh": c[5],
            "endereco": c[6],
            "salario": float(c[7]) if c[7] else None,
            "data_admissao": c[8],
            "foto": c[9],  # Foto do colaborador (se existir)
        }
    else:
        usuario["colaborador"] = None

    # Logs
    try:
        cur.execute("""
            SELECT acao, detalhes, criado_em
            FROM logs_sistema
            WHERE usuario_id = %s
            ORDER BY criado_em DESC
            LIMIT 30
        """, (user_id,))
        logs = cur.fetchall()
        usuario["logs"] = [
            {"acao": l[0], "detalhes": l[1], "criado_em": l[2]} for l in logs
        ]
    except:
        usuario["logs"] = []

    cur.close()
    conn.close()
    return usuario


@perfil_bp.get("/dados")
def dados_perfil():
    return jsonify(get_usuario_completo(current_user.id))


@perfil_bp.get("/")
def pagina_perfil():
    return render_template("perfil.html")


@perfil_bp.post("/atualizar")
def atualizar_perfil():
    nome = request.form.get("nome")
    email = request.form.get("email")
    telefone = request.form.get("telefone")

    try:
        storage = get_storage()
        foto_path = current_user.foto

        # Upload de foto EXCLUSIVO para perfil de usuário
        if "foto" in request.files:
            file = request.files["foto"]
            if file.filename:
                foto_path = storage.save(file, subdir="faces")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE usuarios
            SET nome = %s, email = %s, telefone = %s, foto = %s
            WHERE id = %s
        """, (nome, email, telefone, foto_path, current_user.id))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True, 
            "message": "Perfil atualizado com sucesso!", 
            "foto_url": storage.get_url(foto_path) if foto_path else None
        })

    except Exception as e:
        current_app.logger.exception("Erro ao atualizar perfil")
        return jsonify({"success": False, "message": str(e)}), 500


@perfil_bp.post("/alterar-senha")
def alterar_senha():
    dados = request.get_json()
    senha_atual = dados.get("senha_atual")
    nova_senha = dados.get("nova_senha")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT senha_hash FROM usuarios WHERE id = %s", (current_user.id,))
    senha_hash = cur.fetchone()[0]

    if not check_password_hash(senha_hash, senha_atual):
        return jsonify({"success": False, "message": "Senha atual incorreta."}), 400

    novo_hash = generate_password_hash(nova_senha, method="pbkdf2:sha256")

    cur.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s", (novo_hash, current_user.id))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"success": True, "message": "Senha alterada com sucesso!"})
