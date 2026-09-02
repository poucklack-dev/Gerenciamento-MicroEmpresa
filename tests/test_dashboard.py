def test_dashboard_redirects_for_anonymous(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/dashboard' page is requested (GET) by an anonymous user
    THEN check that the user is redirected to the login page.
    """
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_dashboard_accessible_for_logged_in_user(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/dashboard' page is requested (GET) by a logged-in user
    THEN check that the page is returned successfully.
    """
    # To simulate a logged-in user, set the session key used by the pages gate.
    with client.session_transaction() as session:
        session['usuarios'] = {
            "id": 1,
            "usuario": "test",
            "cargo": "admin",
            "nome": "Usuário Teste",
            "email": "teste@example.com",
            "status": "ativo",
        }

    response = client.get('/dashboard')
    assert response.status_code == 200
    # Check for a piece of content that is unique to the dashboard page
    assert "Dashboard de Gestão".encode("utf-8") in response.data
