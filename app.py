# app.py
import os
from flask import Flask, jsonify, request, session
from flask_login import LoginManager, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_talisman import Talisman

from core.database import get_conn, close_conn
from core.user import User
from core.limiter import limiter  # Import central limiter instance
from config import get_config_class, get_env_name

# Server-side session imports are done conditionally below (only if REDIS_URL present)

# ============================================================
#  APP Initialization
# ============================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config.from_object(get_config_class())
app.url_map.strict_slashes = False

# Apply ProxyFix (trust single proxy as Cloud Run sits behind a proxy)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# ============================================================
#  RATE LIMITING (FLASK-LIMITER)
# ============================================================
# Initialize rate limiter. Uses Redis if REDIS_URL is set, otherwise memory.
# This is placed after ProxyFix so that it can correctly get the remote address.
redis_url = app.config.get('REDIS_URL') or os.environ.get('REDIS_URL')
app.config.setdefault("RATELIMIT_STORAGE_URI", redis_url if redis_url else "memory://")
app.config.setdefault("RATELIMIT_STRATEGY", "fixed-window")
app.config.setdefault("RATELIMIT_DEFAULT", os.environ.get("RATELIMIT_DEFAULT", "200 per day; 50 per hour"))

limiter.init_app(app)


# ============================================================
#  SECURITY HEADERS (FLASK-TALISMAN)
# ============================================================
# Define a robust Content Security Policy
csp = {
    'default-src': '\'self\'',
    'base-uri': '\'self\'',
    'object-src': '\'none\'',
    'frame-ancestors': '\'none\'',
    'img-src': [
        '\'self\'',
        'data:',
        'blob:'
    ],
    'style-src': [
        '\'self\'',
        '\'unsafe-inline\'',  # Required by some libraries, review if possible
        'https://fonts.googleapis.com',
        'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net'
    ],
    'font-src': [
        '\'self\'',
        'data:',
        'https://fonts.gstatic.com',
        'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net'
    ],
    'script-src': [
        '\'self\'',
        '\'unsafe-inline\'',  # Required by some libraries, review if possible
        'https://code.jquery.com',
        'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net'
    ],
    'connect-src': [
        '\'self\'',
        'https://viacep.com.br',
        'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net'
    ],
    'form-action': '\'self\'',
}

# Initialize Talisman to enforce security headers
Talisman(
    app,
    content_security_policy=csp,
    force_https_permanent=True, # Use HSTS
    frame_options='DENY',
    frame_options_allow_from=None,
    strict_transport_security_include_subdomains=True,
    content_security_policy_report_only=False,
    referrer_policy='no-referrer-when-downgrade'
)


env_name = get_env_name()

# Ensure SECRET_KEY is present in production — fail fast with clear error
if env_name in {"prod", "production"} and not app.config.get("SECRET_KEY"):
    raise RuntimeError(
        "SECRET_KEY environment variable is required in production and is not set. Application will not start."
    )

# ----------------------
# Server-side session (optional Redis)
# If REDIS_URL is provided in environment/config, initialize Flask-Session
# ----------------------
if redis_url:
    try:
        import redis as redis_lib
        from flask_session import Session as FlaskSession

        # Create Redis client and attach to Flask-Session
        redis_client = redis_lib.from_url(redis_url)
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis_client
        app.config.setdefault('SESSION_PERMANENT', app.config.get('SESSION_PERMANENT', False))
        app.config.setdefault('SESSION_USE_SIGNER', app.config.get('SESSION_USE_SIGNER', True))

        sess = FlaskSession()
        sess.init_app(app)
        app.logger.info('Server-side sessions enabled (Redis)')
    except Exception as e:
        # Fail fast in production if Redis is explicitly required
        if env_name in {"prod", "production"}:
            raise RuntimeError(f'Failed to initialize Redis session store: {e}')
        else:
            app.logger.warning(f'Could not initialize Redis session store, falling back to cookie sessions: {e}')


# ============================================================
#  LOGIN MANAGER
# ============================================================
login_manager = LoginManager()
login_manager.init_app(app)
# Relax session protection to reduce spurious logouts behind Cloud Run (IP may change)
# Setting to None avoids aggressive logout; monitor this for security needs.
login_manager.session_protection = None
login_manager.login_view = 'login.login'


@app.before_request
def protect_administrative_api():
    """Require an authenticated session for business APIs.

    The time-clock endpoints under ``/ponto`` intentionally remain public so
    field employees can register attendance using CPF/facial validation.
    """
    if not request.path.startswith("/api/"):
        return None

    if request.path.startswith("/api/diag/"):
        return None  # The diagnostic blueprint performs its own admin check.

    session_user = session.get("usuarios") or {}
    if session_user.get("id") or getattr(current_user, "is_authenticated", False):
        if request.path.startswith("/api/usuarios/debug/"):
            debug_enabled = os.environ.get("ENABLE_DEBUG_ROUTES", "").strip().lower() in {"1", "true", "yes", "on"}
            if not debug_enabled:
                return jsonify({"success": False, "erro": "Recurso não encontrado."}), 404
            cargo = session_user.get("cargo") or getattr(current_user, "cargo", "")
            if "admin" not in str(cargo).lower() and str(cargo).strip() not in {
                "Gestor", "Gerente de Topografia", "Coordenador de Topografia", "Supervisor de Topografia"
            }:
                return jsonify({"success": False, "erro": "Acesso negado."}), 403
        return None

    return jsonify({"success": False, "erro": "Autenticação necessária."}), 401

@login_manager.user_loader
def load_user(user_id):
    if app.config.get("TESTING"):
        from flask_login import UserMixin

        class TestUser(UserMixin):
            def __init__(self, uid):
                self.id = uid

        return TestUser(user_id)

    try:
        return User(user_id)
    except Exception:
        app.logger.exception("Failed to load user from database")
        return None


# Ensure authenticated pages are not cached by intermediaries or WebViews
@app.after_request
def set_auth_cache_headers(response):
    # This function now ONLY handles caching for authenticated users.
    # All other security headers are managed by Flask-Talisman.
    try:
        from flask_login import current_user
        # Do not modify static files or other assets
        if request.path.startswith('/static'):
            return response

        is_authenticated = "usuarios" in session
        if not is_authenticated:
            is_authenticated = getattr(current_user, 'is_authenticated', False)

        if is_authenticated:
            # Prevent proxies and browsers from caching authenticated pages
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
    except Exception:
        # Silently pass on errors in this hook
        pass
    return response


@app.teardown_appcontext
def close_db_connection(_exc=None):
    close_conn()

# ============================================================
#  BLUEPRINTS
# ============================================================
from backend.login import login_bp
from backend.cliente import clientes_pages_bp, clientes_bp
from backend.colaboradores import bp_colab
from backend.contas_a_receber import bp_receber
from backend.contas_a_pagar import bp_pagar
from backend.contratos import bp_contratos
from backend.dashboard import bp_home, bp_dashboard
from backend.documentos import bp_documentos
from backend.equipe_campo import equipe_campo_bp
from backend.facial import bp_faces
from backend.financeiro import financeiro360_bp
from backend.fornecedores import fornecedores_bp
from backend.perfil import perfil_bp
from backend.ponto import bp_ponto
from backend.quilometragem import custos_bp
from backend.usuario import usuarios_bp
from backend.banco_de_horas import banco_horas_bp
from backend.pages import pages_bp
from backend.diag import diag_bp
from backend.media import media_bp

app.register_blueprint(pages_bp)
app.register_blueprint(login_bp)
app.register_blueprint(clientes_pages_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(bp_colab)
app.register_blueprint(bp_receber)
app.register_blueprint(bp_pagar)
app.register_blueprint(bp_contratos)
app.register_blueprint(bp_home)
app.register_blueprint(bp_dashboard)
app.register_blueprint(bp_documentos)
app.register_blueprint(equipe_campo_bp)
app.register_blueprint(bp_faces)
app.register_blueprint(financeiro360_bp)
app.register_blueprint(fornecedores_bp)
app.register_blueprint(perfil_bp)
app.register_blueprint(bp_ponto)
app.register_blueprint(custos_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(banco_horas_bp)
app.register_blueprint(diag_bp)
app.register_blueprint(media_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


# Handle large uploads gracefully and return JSON
from werkzeug.exceptions import RequestEntityTooLarge


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return (jsonify({
        "success": False,
        "erro": f"Arquivo muito grande. Tamanho máximo: {app.config.get('MAX_CONTENT_LENGTH')/(1024*1024)}MB"
    }), 413)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True}), 200


@app.get("/readyz")
def readyz():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"ok": True}), 200
    except Exception:
        return jsonify({"ok": False}), 503
