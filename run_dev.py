import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

os.environ.setdefault("ENV", os.getenv("FLASK_CONFIG") or "development")

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
