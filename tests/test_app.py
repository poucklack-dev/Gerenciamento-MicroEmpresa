import os

def test_app_creation(client):
    """Test that the app is created and TESTING config is set."""
    assert client.application.testing is True

def test_app_paths(client):
    """Test that template_folder and static_folder are correctly set."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    assert client.application.template_folder == os.path.join(base_dir, 'templates')
    assert client.application.static_folder == os.path.join(base_dir, 'static')


def test_health_endpoint_does_not_expose_internal_details(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
