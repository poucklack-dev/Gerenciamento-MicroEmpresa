import os

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user

from core.database import get_conn
from core.user import User
from core.limiter import limiter  # Import the central limiter instance

# 🔥 AGORA SEM PREFIXO /auth
login_bp = Blueprint('login', __name__)

# ============================================================
#  ROTA PRINCIPAL DO LOGIN (USADA PELO /login E PELO /)
# ============================================================
@login_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("15 per minute", error_message="Muitas tentativas de login. Tente novamente em um minuto.")
def login():
    if request.method == 'POST':
        data = request.get_json()
        usuario = data.get('usuario')
        senha = data.get('senha')

        if not usuario or not senha:
            return jsonify({"error": "Usuário e senha são obrigatórios!"}), 400

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, usuario, senha_hash, cargo, nome, email, status, telefone, cpf
            FROM usuarios 
            WHERE usuario = %s AND status = 'ativo'
        """, (usuario,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_data and check_password_hash(user_data[2], senha):
            # 🔥 AGORA USAMOS O MÉTODO CORRETO PARA CRIAR O USER
            user = User.from_db_row(user_data)
            
            login_user(user)

            # Armazena na sessão também
            session['usuarios'] = {
                "id": user_data[0],
                "usuario": user_data[1],
                "cargo": user_data[3],
                "nome": user_data[4],
                "email": user_data[5],
                "status": user_data[6]
            }

            return jsonify({
                "success": True,
                "message": "Login realizado com sucesso!",
                "user": {
                    "id": user_data[0],
                    "nome": user_data[4],
                    "usuario": user_data[1],
                    "cargo": user_data[3],
                    "email": user_data[5],
                    "is_admin": user.is_admin  # 🔥 AGORA USA A PROPRIEDADE DO USER
                }
            })
        else:
            return jsonify({
                "success": False, 
                "error": "Usuário ou senha inválidos, ou usuário inativo."
            }), 401

    # GET request - renderiza a página de login
    return render_template('login.html')


# ============================================================
#  AGORA "/" TAMBÉM É LOGIN
# ============================================================
@login_bp.route("/", methods=["GET", "POST"])
def login_root():
    return login()


# ============================================================
# LOGOUT
# ============================================================
@login_bp.route('/logout')
def logout():
    session.pop('usuarios', None)
    logout_user()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login.login'))


# ============================================================
#  ROTA PARA VERIFICAR SESSÃO (usada pelo frontend)
# ============================================================
@login_bp.route('/check_session')
def check_session():
    """Verifica se o usuário está logado e retorna seus dados"""
    from flask_login import current_user

    user_session = session.get("usuarios") or {}
    if user_session.get("id"):
        return jsonify({
            "authenticated": True,
            "user": {
                "id": user_session.get("id"),
                "nome": user_session.get("nome", ""),
                "usuario": user_session.get("usuario", ""),
                "cargo": user_session.get("cargo", ""),
                "email": user_session.get("email", ""),
                "is_admin": "admin" in str(user_session.get("cargo", "")).lower(),
            }
        })

    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "nome": getattr(current_user, 'nome', ''),
            "usuario": getattr(current_user, 'usuario', ''),
            "cargo": getattr(current_user, 'cargo', ''),
            "email": getattr(current_user, 'email', ''),
            "is_admin": getattr(current_user, 'is_admin', False)
        }
    })


# ============================================================
#  ROTA PARA DEBUG - Mostrar dados do usuário atual
# ============================================================
@login_bp.route('/debug_user')
def debug_user():
    """Rota para debug - mostra todos os dados do usuário atual"""
    from flask_login import current_user

    debug_enabled = os.environ.get("ENABLE_DEBUG_ROUTES", "").strip().lower() in {"1", "true", "yes", "on"}
    if not debug_enabled:
        abort(404)

    if not getattr(current_user, "is_authenticated", False):
        abort(401)

    if not getattr(current_user, "is_admin", False):
        abort(403)
    
    user_attrs = {}
    for attr in dir(current_user):
        if not attr.startswith('_'):
            try:
                value = getattr(current_user, attr)
                # Não incluir métodos
                if not callable(value):
                    user_attrs[attr] = str(value)
            except:
                user_attrs[attr] = 'ERROR'
    
    return jsonify({
        "user_attributes": user_attrs,
        "is_admin": getattr(current_user, 'is_admin', False),
        "cargo": getattr(current_user, 'cargo', 'N/A')
    })
