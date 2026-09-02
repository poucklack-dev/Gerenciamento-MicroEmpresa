import psycopg2
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def create_user(username, password, nome, cargo, email):
    """Cria um novo usuário no banco de dados com uma senha hasheada."""
    
    # Gerar o hash da senha
    senha_hash = generate_password_hash(password, method='pbkdf2:sha256')
    print(f"Gerando hash para a senha: {senha_hash}")

    try:
        # Conectar ao banco de dados
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()

        # Inserir o novo usuário
        cur.execute(
            """
            INSERT INTO usuarios (usuario, senha_hash, nome, cargo, email)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (username, senha_hash, nome, cargo, email)
        )
        user_id = cur.fetchone()[0]
        conn.commit()

        
        print(f"\nUsuário '{username}' criado com sucesso! ID: {user_id}")

    except Exception as e:
        print(f"\nOcorreu um erro: {e}")

    finally:
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    novo_usuario = input("Digite o nome do novo usuário (login): ")
    nova_senha = input("Digite a senha para o novo usuário: ")
    nome_completo = input("Digite o nome completo: ")
    cargo_usuario = input("Digite o cargo (ex: admin, user): ")
    email_usuario = input("Digite o email: ")
    
    if novo_usuario and nova_senha:
        create_user(novo_usuario, nova_senha, nome_completo, cargo_usuario, email_usuario)
    else:
        print("Usuário e senha não podem ser vazios.")
