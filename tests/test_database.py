from unittest.mock import patch

# Import the function to be tested
from core.database import get_conn

@patch('core.database.psycopg2.connect')
@patch('core.database.os.getenv')
def test_get_conn_uses_env_vars_for_cloud_sql(mock_getenv, mock_psycopg2_connect):
    """
    GIVEN a set of environment variables for a Cloud SQL connection
    WHEN get_conn() is called
    THEN it should call psycopg2.connect with the correct parameters for a Unix socket.
    """
    # Define the mock return values for os.getenv for a Cloud SQL scenario
    mock_env_vars = {
        "DB_NAME": "test_db",
        "DB_USER": "test_user",
        "DB_PASS": "test_pass",
        "DB_HOST": "/cloudsql/test-project:us-central1:test-instance",
        "DB_PORT": "5432"
    }
    # The side_effect allows mock_getenv to return different values for different keys
    mock_getenv.side_effect = lambda key, default=None: mock_env_vars.get(key, default)

    # Call the function
    get_conn()

    # Assert that psycopg2.connect was called exactly once
    mock_psycopg2_connect.assert_called_once()

    # Assert that it was called with the correct arguments
    mock_psycopg2_connect.assert_called_with(
        dbname="test_db",
        user="test_user",
        password="test_pass",
        host="/cloudsql/test-project:us-central1:test-instance",
        port="5432",
        client_encoding="UTF8"
    )

@patch('core.database.psycopg2.connect')
@patch('core.database.os.getenv')
def test_get_conn_uses_default_port_when_not_provided(mock_getenv, mock_psycopg2_connect):
    """
    GIVEN environment variables for a local connection without a DB_PORT
    WHEN get_conn() is called
    THEN it should call psycopg2.connect with the default port '5432'.
    """
    mock_env_vars = {
        "DB_NAME": "local_db",
        "DB_USER": "local_user",
        "DB_PASS": "local_pass",
        "DB_HOST": "localhost",
    }
    # When DB_PORT is requested, os.getenv will return None, so the default should be used.
    mock_getenv.side_effect = lambda key, default=None: mock_env_vars.get(key, default)
    
    get_conn()

    mock_psycopg2_connect.assert_called_with(
        dbname="local_db",
        user="local_user",
        password="local_pass",
        host="localhost",
        port="5432", # The default value specified in get_conn
        client_encoding="UTF8"
    )
