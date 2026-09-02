from flask_login import UserMixin
from core.database import get_conn

class User(UserMixin):
    def __init__(self, user_id):
        """Construtor padrão - usado pelo Flask-Login user_loader"""
        self.id = user_id
        self._load_user()
    
    @classmethod
    def from_db_row(cls, db_row):
        """
        Método especial para criar um User a partir de uma linha do banco
        Usado no login onde já temos todos os dados
        """
        user = cls(db_row[0])  # Cria o User normalmente (vai carregar do banco)
        
        # MAS... sobrescrevemos com os dados que já temos (mais rápido)
        user.id = db_row[0]
        user.usuario = db_row[1]
        user.senha_hash = db_row[2]
        user.cargo = db_row[3]
        user.nome = db_row[4]
        user.email = db_row[5]
        
        # Dados opcionais (verifica se existem na linha)
        if len(db_row) > 6:
            user.status = db_row[6]
        if len(db_row) > 7:
            user.telefone = db_row[7]
        if len(db_row) > 8:
            user.cpf = db_row[8]
        
        # Calcula se é admin
        user.is_admin = 'admin' in str(user.cargo).lower() if user.cargo else False
        
        return user
    
    def _load_user(self):
        """Carrega os dados do usuário do banco de dados"""
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, usuario, nome, email, telefone, foto, cargo, status, senha_hash 
            FROM usuarios 
            WHERE id = %s
        """, (self.id,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()

        if user_data:
            self.id = user_data[0]
            self.usuario = user_data[1]
            self.nome = user_data[2]
            self.email = user_data[3]
            self.telefone = user_data[4]
            self.foto = user_data[5]
            self.cargo = user_data[6]
            self.status = user_data[7]
            self.senha_hash = user_data[8]
            
            # Calcula se é admin baseado no cargo
            self.is_admin = 'admin' in str(self.cargo).lower() if self.cargo else False
        else:
            # Se não encontrar, define valores padrão
            self.usuario = None
            self.cargo = None
            self.nome = None
            self.email = None
            self.is_admin = False

    def get_id(self):
        """Retorna o ID como string (requerido pelo Flask-Login)"""
        return str(self.id)
    
    def __repr__(self):
        """Representação do objeto para debug"""
        return f"<User(id={self.id}, nome='{self.nome}', cargo='{self.cargo}', is_admin={self.is_admin})>"
    
    def to_dict(self):
        """Converte o User para dicionário (útil para templates)"""
        return {
            'id': self.id,
            'nome': self.nome,
            'usuario': self.usuario,
            'cargo': self.cargo,
            'email': self.email,
            'status': getattr(self, 'status', None),
            'telefone': getattr(self, 'telefone', None),
            'is_admin': self.is_admin
        }