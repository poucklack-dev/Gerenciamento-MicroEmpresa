from werkzeug.security import check_password_hash

from core.auth import hash_senha


def test_hash_senha_is_compatible_with_login():
    password_hash = hash_senha("senha-forte")

    assert password_hash != "senha-forte"
    assert check_password_hash(password_hash, "senha-forte")


def test_business_api_requires_authentication(client):
    response = client.get("/api/clientes/")

    assert response.status_code == 401
    assert response.get_json()["erro"] == "Autenticação necessária."


def test_debug_user_api_is_disabled_by_default(client):
    with client.session_transaction() as session:
        session["usuarios"] = {"id": 1, "cargo": "admin"}

    response = client.get("/api/usuarios/debug/usuario-atual")

    assert response.status_code == 404
