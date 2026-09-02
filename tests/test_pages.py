import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/clientes",
        "/colaboradores",
        "/equipe_campo",
        "/contas_pagar",
        "/contas_receber",
        "/quilometragem",
        "/financeiro",
        "/contratos",
        "/documentos",
        "/fornecedores",
        "/perfil",
        "/banco_de_horas",
    ],
)
def test_administrative_pages_render_for_session_user(client, path):
    with client.session_transaction() as session:
        session["usuarios"] = {"id": 1, "cargo": "admin", "nome": "Teste"}

    response = client.get(path)

    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data
