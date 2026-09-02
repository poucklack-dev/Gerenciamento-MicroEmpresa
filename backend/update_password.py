import psycopg2
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def update_password(username, email, telefone, new_password):
    """Atualiza a senha apenas após confirmar e-mail e telefone."""

    # Criar hash da nova senha
    senha_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    print(f"Gerando novo hash para a senha: {senha_hash}")

    try:
        # Conectar ao banco
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()

        # Verificar se usuário existe e confirmar email + telefone
        cur.execute("""
            SELECT id FROM usuarios
            WHERE usuario = %s AND email = %s AND telefone = %s
        """, (username, email, telefone))

        usuario = cur.fetchone()

        if not usuario:
            print("\n❌ Erro: Usuário, e-mail ou telefone não conferem.")
            return

        # Atualizar a senha
        cur.execute("""
            UPDATE usuarios SET senha_hash = %s
            WHERE usuario = %s
        """, (senha_hash, username))

        conn.commit()

        print(f"\n✔ Senha do usuário '{username}' atualizada com sucesso!")

    except Exception as e:
        print(f"\n❌ Ocorreu um erro: {e}")

    finally:
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()


# ===============================
# Execução direta
# ===============================
if __name__ == "__main__":
    usuario_existente = input("Usuário: ")
    email_confirmacao = input("E-mail cadastrado: ")
    telefone_confirmacao = input("Telefone cadastrado: ")
    nova_senha = input("Nova senha: ")

    if usuario_existente and email_confirmacao and telefone_confirmacao and nova_senha:
        update_password(usuario_existente, email_confirmacao, telefone_confirmacao, nova_senha)
    else:
        print("❌ Todos os campos são obrigatórios.")
