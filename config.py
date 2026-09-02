import os


def get_env_name():
    return (os.environ.get("ENV") or os.environ.get("FLASK_ENV") or "development").strip().lower()


class BaseConfig:
    DEBUG = False
    TESTING = False

    # Can be overridden per environment; production enforces presence at startup.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Security / session cookie settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Flask-Login remember cookie settings (if used)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Prefer https when generating external URLs (override in dev/test)
    PREFERRED_URL_SCHEME = "https"

    # Global maximum request size (50 MB by default)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))

    # Redis (optional) for server-side sessions. If not set, app will fall back to cookie sessions.
    REDIS_URL = os.environ.get("REDIS_URL")

    # Session options (used when Redis is configured)
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-me"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    PREFERRED_URL_SCHEME = "http"


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "test-secret-key"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    PREFERRED_URL_SCHEME = "http"


class ProductionConfig(BaseConfig):
    # SECRET_KEY must be provided via environment in production. No default allowed.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


def get_config_class():
    env = get_env_name()
    if env in {"prod", "production"}:
        return ProductionConfig
    if env in {"test", "testing"}:
        return TestingConfig
    return DevelopmentConfig
