# core/limiter.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==============================================================================
#  FLASK-LIMITER INSTANCE
# ==============================================================================
#
# Central instance for the rate limiter.
# Initialized here without an app, which allows it to be imported into
# blueprints without causing circular dependencies.
#
# The app will be associated later using `limiter.init_app(app)`.
#
# The key_func uses `get_remote_address`, which will correctly use the
# IP address from the `X-Forwarded-For` header once ProxyFix is configured
# on the main app.
#
# ==============================================================================

limiter = Limiter(
    key_func=get_remote_address,
    # The strategy and storage are configured in app.py via app.config
)
