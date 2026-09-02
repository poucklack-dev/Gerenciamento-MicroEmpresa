# core/auth.py
from functools import wraps
from flask import jsonify
from flask_login import current_user
from werkzeug.security import generate_password_hash


def hash_senha(password):
    """Create password hashes compatible with login and profile flows."""
    if not isinstance(password, str) or not password:
        raise ValueError("A senha não pode ser vazia.")
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
        if not getattr(current_user, 'is_admin', False):
            return jsonify({
                "success": False, 
                "erro": "Acesso negado. Este recurso requer permissões de administrador."
            }), 403
            
        return f(*args, **kwargs)
    return decorated_function
