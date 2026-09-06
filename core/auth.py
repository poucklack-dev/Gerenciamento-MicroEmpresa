# core/auth.py
from functools import wraps
from flask import jsonify
from flask_login import current_user
from werkzeug.security import generate_password_hash

ADMIN_ROLES = frozenset({
    "admin",
    "gestor",
    "gerente de topografia",
    "coordenador de topografia",
    "supervisor de topografia",
})


def is_admin_role(role: object) -> bool:
    """Return whether a stored job role grants administrative access."""
    return str(role or "").strip().casefold() in ADMIN_ROLES


def hash_senha(password: str) -> str:
    """Create password hashes compatible with login and profile flows."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    return generate_password_hash(password, method="pbkdf2:sha256")

def admin_required(f):
    """
    Decorator that ensures the current user is authenticated and is an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First, check if user is authenticated
        if not current_user.is_authenticated:
            return jsonify({
                "success": False, 
                "erro": "Autenticação necessária para acessar este recurso."
            }), 401
        
        # Then, check if the authenticated user is an admin
        if not is_admin_role(getattr(current_user, "cargo", "")):
            return jsonify({
                "success": False, 
                "erro": "Acesso negado. Este recurso requer permissões de administrador."
            }), 403
            
        return f(*args, **kwargs)
    return decorated_function
