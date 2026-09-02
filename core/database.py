import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

_G_KEY = "_patagonia_db_conn"


def _connect():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        conn_kwargs = {}

        sslmode = os.getenv("DB_SSLMODE")
        if sslmode:
            conn_kwargs["sslmode"] = sslmode

        connect_timeout = os.getenv("DB_CONNECT_TIMEOUT")
        if connect_timeout:
            try:
                conn_kwargs["connect_timeout"] = int(connect_timeout)
            except ValueError:
                pass

        return psycopg2.connect(database_url, **conn_kwargs)

    conn_kwargs = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASS"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT", "5432"),
        "client_encoding": "UTF8",
    }

    sslmode = os.getenv("DB_SSLMODE")
    if sslmode:
        conn_kwargs["sslmode"] = sslmode

    connect_timeout = os.getenv("DB_CONNECT_TIMEOUT")
    if connect_timeout:
        try:
            conn_kwargs["connect_timeout"] = int(connect_timeout)
        except ValueError:
            # Ignore invalid timeout value
            pass

    return psycopg2.connect(**conn_kwargs)


def get_conn():
    """
    Return an independent PostgreSQL connection.

    The existing blueprints explicitly close their connections, including from
    nested helper functions. Sharing one connection through ``flask.g`` made a
    helper close the caller's active transaction (notably during collaborator
    deletion), so each call intentionally owns its connection.
    """
    return _connect()


def close_conn():
    """
    Close and remove the cached Flask-context connection (if any).
    Safe to call even when no Flask context exists.
    """
    try:
        from flask import g, has_app_context
    except Exception:
        return

    if not has_app_context():
        return

    conn = getattr(g, _G_KEY, None)
    if conn is None:
        return

    delattr(g, _G_KEY)

    try:
        conn.close()
    except Exception:
        pass



def get_cursor():
    conn = get_conn()
    conn.autocommit = True
    return conn.cursor()
