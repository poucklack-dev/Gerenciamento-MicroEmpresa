from werkzeug.security import check_password_hash

import pytest

from backend.core.auth import hash_senha, is_admin_role


def test_hash_senha_is_compatible_with_login():
    password_hash = hash_senha("senha-forte")

    assert password_hash != "senha-forte"
    assert check_password_hash(password_hash, "senha-forte")


def test_short_password_is_rejected():
    with pytest.raises(ValueError, match="8 caracteres"):
        hash_senha("curta")


@pytest.mark.parametrize("role", ["admin", "Gestor", "GERENTE DE TOPOGRAFIA"])
def test_admin_roles_are_normalized(role):
    assert is_admin_role(role) is True


def test_non_admin_role_is_rejected():
    assert is_admin_role("Financeiro") is False


def test_business_api_requires_authentication(client):
    response = client.get("/api/clientes/")

    assert response.status_code == 401
    assert response.get_json()["erro"] == "Autenticação necessária."


def test_debug_user_api_is_disabled_by_default(client):
    with client.session_transaction() as session:
        session["usuarios"] = {"id": 1, "cargo": "admin"}

    response = client.get("/api/usuarios/debug/usuario-atual")

    assert response.status_code == 404


def test_cross_origin_write_is_rejected(client):
    response = client.post(
        "/login",
        json={"usuario": "teste", "senha": "senha-forte"},
        headers={"Origin": "https://malicious.example"},
    )

    assert response.status_code == 403
