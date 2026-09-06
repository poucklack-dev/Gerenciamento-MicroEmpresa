"""Create or refresh the optional local portfolio administrator."""

import os

from dotenv import load_dotenv

from core.auth import hash_senha
from core.database import get_conn


def main() -> None:
    load_dotenv()
    if os.getenv("DEMO_SEED", "").strip().lower() not in {"1", "true", "yes"}:
        raise SystemExit("Defina DEMO_SEED=1 para criar a conta de demonstração.")

    password = os.getenv("DEMO_ADMIN_PASSWORD", "")
    username = os.getenv("DEMO_ADMIN_USER", "admin_demo").strip()
    if not username:
        raise SystemExit("DEMO_ADMIN_USER não pode ser vazio.")

    password_hash = hash_senha(password)
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nome, usuario, senha_hash, cargo, email, status)
            VALUES (%s, %s, %s, 'admin', %s, 'ativo')
            ON CONFLICT (usuario) DO UPDATE SET
                nome = EXCLUDED.nome,
                senha_hash = EXCLUDED.senha_hash,
                cargo = EXCLUDED.cargo,
                email = EXCLUDED.email,
                status = EXCLUDED.status,
                atualizado_em = NOW()
            """,
            ("Administrador Demo", username, password_hash, "admin.demo@example.test"),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    print(f"Conta de demonstração pronta: {username}")


if __name__ == "__main__":
    main()
