from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash
from datetime import timedelta
from database import get_conn
import uuid
import traceback


# ===========================================================
# LOGIN BLUEPRINT (com DEBUG TOTAL)
# ===========================================================

log_bp = Blueprint("log_bp", __name__, url_prefix="/log")


@log_bp.post("/login")
def login():
    req_id = str(uuid.uuid4())[:8]   # id curto para rastrear requisição
    print(f"\n🔵 [LOGIN {req_id}] Nova requisição recebida")

    # ---------------------------------------------------------
    # 1. Ler JSON da requisição
    # ---------------------------------------------------------
    data = request.get_json(silent=True)
    print(f"🟣 [LOGIN {req_id}] JSON recebido:", data)

    if not data:
        print(f"🔴 [LOGIN {req_id}] JSON inválido (None)")
        return jsonify({"erro": "JSON inválido"}), 400

    email = data.get("email")
    senha = data.get("senha")

    print(f"🟣 [LOGIN {req_id}] Email recebido: {email}")
    print(f"🟣 [LOGIN {req_id}] Senha recebida: {'<oculta>' if senha else None}")

    if not email or not senha:
        print(f"🔴 [LOGIN {req_id}] Email ou senha vazios")
        return jsonify({"erro": "Preencha email e senha."}), 400

    # ---------------------------------------------------------
    # 2. Conectar ao Banco
    # ---------------------------------------------------------
    try:
        print(f"🟡 [LOGIN {req_id}] Tentando conectar ao banco...")
        conn = get_conn()

        if conn is None:
            print(f"🔴 [LOGIN {req_id}] get_conn() retornou None")
            return jsonify({"erro": "Falha ao conectar ao banco"}), 500

        cur = conn.cursor()
        print(f"🟡 [LOGIN {req_id}] Conexão e cursor OK.")

        # -----------------------------------------------------
        # 3. Buscar o usuário
        # -----------------------------------------------------
        print(f"🟡 [LOGIN {req_id}] Executando SELECT do usuário {email}")
        cur.execute("""
            SELECT id, nome, role, senha_hash
            FROM usuarios
            WHERE email = %s AND ativo = TRUE
        """, (email,))

        row = cur.fetchone()
        print(f"🟡 [LOGIN {req_id}] Resultado no banco:", row)

        cur.close()
        conn.close()
        print(f"🟢 [LOGIN {req_id}] Conexão com banco fechada.")

    except Exception as e:
        print(f"🔴 [LOGIN {req_id}] ERRO NO BANCO:", e)
        traceback.print_exc()
        return jsonify({"erro": f"Erro no banco: {e}"}), 500

    # ---------------------------------------------------------
    # 4. Validar usuário encontrado
    # ---------------------------------------------------------
    if not row:
        print(f"🔴 [LOGIN {req_id}] Usuário não encontrado ou inativo")
        return jsonify({"erro": "Usuário não encontrado"}), 401

    user_id, nome, role, senha_hash_db = row

    print(f"🟢 [LOGIN {req_id}] Usuário encontrado: {nome} (ID={user_id}, Role={role})")
    print(f"🟡 [LOGIN {req_id}] Hash no banco: {senha_hash_db}")

    # ---------------------------------------------------------
    # 5. Validar senha
    # ---------------------------------------------------------
    print(f"🟡 [LOGIN {req_id}] Validando senha...")
    if not check_password_hash(senha_hash_db, senha):
        print(f"🔴 [LOGIN {req_id}] Senha incorreta para {email}")
        return jsonify({"erro": "Senha incorreta"}), 401

    print(f"🟢 [LOGIN {req_id}] Senha válida.")

    # ---------------------------------------------------------
    # 6. Criar token JWT
    # ---------------------------------------------------------
    try:
        print(f"🟡 [LOGIN {req_id}] Gerando JWT...")
        token = create_access_token(
            identity=user_id,
            expires_delta=timedelta(hours=12)
        )
        print(f"🟢 [LOGIN {req_id}] JWT gerado com sucesso.")
    except Exception as e:
        print(f"🔴 [LOGIN {req_id}] ERRO GERANDO JWT:", e)
        traceback.print_exc()
        return jsonify({"erro": "Falha ao gerar token"}), 500

    # ---------------------------------------------------------
    # 7. Resposta final
    # ---------------------------------------------------------
    print(f"🟢 [LOGIN {req_id}] LOGIN FINALIZADO COM SUCESSO PARA {email}")

    return jsonify({
        "token": token,
        "usuario": {
            "id": user_id,
            "nome": nome,
            "papel": role
        }
    }), 200
