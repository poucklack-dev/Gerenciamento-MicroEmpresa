from flask import Blueprint, request, jsonify, session
from core.database import get_conn
from core.auth import hash_senha
from flask_login import current_user

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

# ========================================================
#  CARGOS QUE SÃO CONSIDERADOS ADMINISTRADORES
# ========================================================
CARGOS_ADMIN = [
    'Gestor', 
    'admin',
    'Gerente de Topografia',
    'Coordenador de Topografia', 
    'Supervisor de Topografia'
]

# ========================================================
#  VERIFICAR SE USUÁRIO É ADMIN (PELO CARGO) - CORRIGIDO
# ========================================================
def verificar_admin():
    """Verifica se o usuário atual é administrador pelo cargo."""
    try:
        # Primeiro tenta pelo Flask-Login
        if current_user.is_authenticated:
            cargo = getattr(current_user, 'cargo', '')
            if cargo and str(cargo).strip() in CARGOS_ADMIN:
                return True
        
        # Se não funcionou, tenta pela sessão (fallback)
        if session and 'usuarios' in session:
            cargo_sessao = session['usuarios'].get('cargo', '')
            if cargo_sessao and str(cargo_sessao).strip() in CARGOS_ADMIN:
                return True
        
        return False
        
    except Exception as e:
        print(f"Erro ao verificar admin: {e}")
        return False

# ========================================================
#  DEBUG: VERIFICAR DADOS DO USUÁRIO ATUAL - CORRIGIDO
# ========================================================
@usuarios_bp.get("/debug/usuario-atual")
def debug_usuario_atual():
    """Endpoint para debug - mostra dados do usuário atual."""
    from flask import session
    
    user_data = {}
    
    if current_user.is_authenticated:
        user_data["flask_user"] = {
            "id": getattr(current_user, 'id', None),
            "nome": getattr(current_user, 'nome', None),
            "usuario": getattr(current_user, 'usuario', None),
            "cargo": getattr(current_user, 'cargo', None),
            "email": getattr(current_user, 'email', None),
            "status": getattr(current_user, 'status', None),
            "is_authenticated": current_user.is_authenticated,
            "is_active": getattr(current_user, 'is_active', True),
            "is_anonymous": current_user.is_anonymous,
        }
    
    if session and 'usuarios' in session:
        user_data["sessao"] = session['usuarios']
    
    # Verificar se é admin
    is_admin = verificar_admin()
    
    return jsonify({
        "usuario": user_data,
        "verificacao_admin": {
            "eh_admin": is_admin,
            "cargo_atual": session.get('usuarios', {}).get('cargo', '') if session else '',
            "cargos_admin": CARGOS_ADMIN,
            "verificacao": "cargo exato na lista CARGOS_ADMIN"
        }
    })

# ========================================================
#  DEBUG COMPLETO DO SISTEMA DE AUTENTICAÇÃO
# ========================================================
@usuarios_bp.get("/debug/completo")
def debug_completo():
    """Debug completo do sistema de autenticação."""
    from flask import session
    import inspect
    
    debug_info = {
        "session_id": session.get('_id', 'N/A'),
        "session_keys": list(session.keys()) if session else [],
        "session_usuarios": session.get('usuarios', {}) if session else {},
        "current_user": {
            "id": getattr(current_user, 'id', None),
            "nome": getattr(current_user, 'nome', None),
            "usuario": getattr(current_user, 'usuario', None),
            "cargo": getattr(current_user, 'cargo', None),
            "is_authenticated": current_user.is_authenticated,
            "is_anonymous": current_user.is_anonymous,
        },
        "verificacao_admin_result": verificar_admin(),
        "cargos_admin": CARGOS_ADMIN,
        "request_headers": dict(request.headers),
    }
    
    return jsonify(debug_info)

# ========================================================
#  LISTAR TODOS OS USUÁRIOS (PARA ADMINS) - CORRIGIDO
# ========================================================
@usuarios_bp.get("/listar")
def listar_usuarios():
    """Lista todos os usuários do sistema."""
    # Verificar se o usuário é admin pelo cargo
    if not verificar_admin():
        print(f"USUÁRIO NÃO É ADMIN! Cargo atual: {getattr(current_user, 'cargo', '')}")
        if session and 'usuarios' in session:
            print(f"Cargo na sessão: {session['usuarios'].get('cargo')}")
        return jsonify({"error": "Acesso negado. Somente administradores."}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                id,
                nome,
                usuario,
                cargo,
                email,
                telefone,
                cpf,
                status,
                criado_em,
                atualizado_em
            FROM usuarios
            ORDER BY nome
        """)
        
        usuarios = []
        for row in cur.fetchall():
            usuarios.append({
                "id": row[0],
                "nome": row[1],
                "usuario": row[2],
                "cargo": row[3],
                "email": row[4],
                "telefone": row[5],
                "cpf": row[6],
                "status": row[7],
                "criado_em": row[8].isoformat() if row[8] else None,
                "atualizado_em": row[9].isoformat() if row[9] else None
            })
        
        return jsonify(usuarios)
        
    except Exception as e:
        return jsonify({"error": f"Erro ao listar usuários: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ========================================================
#  CRIAR NOVO USUÁRIO (PARA ADMINS) - CORRIGIDO
# ========================================================
@usuarios_bp.post("/criar")
def criar_usuario():
    """Cria um novo usuário no sistema."""
    # Verificar se o usuário é admin pelo cargo
    if not verificar_admin():
        print(f"USUÁRIO NÃO É ADMIN! Tentativa de criar usuário por cargo: {getattr(current_user, 'cargo', '')}")
        return jsonify({"error": "Acesso negado. Somente administradores."}), 403
    
    data = request.get_json()
    
    # Validação dos campos obrigatórios
    campos_obrigatorios = ['nome', 'usuario', 'senha', 'cargo']
    for campo in campos_obrigatorios:
        if campo not in data or not str(data[campo]).strip():
            return jsonify({"error": f"Campo '{campo}' é obrigatório."}), 400
    
    # Verificar se as senhas coincidem (se houver confirmação)
    if 'confirmar_senha' in data and data['senha'] != data['confirmar_senha']:
        return jsonify({"error": "As senhas não coincidem."}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Verificar se o usuário já existe
        cur.execute("SELECT id FROM usuarios WHERE usuario = %s", (data['usuario'],))
        if cur.fetchone():
            return jsonify({"error": "Nome de usuário já existe."}), 400
        
        # Criptografar senha
        senha_hash = hash_senha(data['senha'])
        
        # Inserir novo usuário
        cur.execute("""
            INSERT INTO usuarios (
                nome, usuario, senha_hash, cargo, email, telefone, cpf, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['nome'].strip(),
            data['usuario'].strip(),
            senha_hash,
            data['cargo'].strip(),
            data.get('email', '').strip(),
            data.get('telefone', '').strip(),
            data.get('cpf', '').strip(),
            data.get('status', 'ativo')
        ))
        
        novo_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "message": "Usuário criado com sucesso!",
            "id": novo_id
        }), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Erro ao criar usuário: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ========================================================
#  EDITAR USUÁRIO (PARA ADMINS) - CORRIGIDO
# ========================================================
@usuarios_bp.put("/editar/<int:user_id>")
def editar_usuario(user_id):
    """Edita um usuário existente."""
    # Verificar se o usuário é admin pelo cargo
    if not verificar_admin():
        print(f"USUÁRIO NÃO É ADMIN! Tentativa de editar usuário por cargo: {getattr(current_user, 'cargo', '')}")
        return jsonify({"error": "Acesso negado. Somente administradores."}), 403
    
    data = request.get_json()
    
    # Validação dos campos obrigatórios
    campos_obrigatorios = ['nome', 'usuario', 'cargo']
    for campo in campos_obrigatorios:
        if campo not in data or not str(data[campo]).strip():
            return jsonify({"error": f"Campo '{campo}' é obrigatório."}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Verificar se o usuário existe
        cur.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado."}), 404
        
        # Verificar se o novo nome de usuário já existe (exceto para o próprio usuário)
        cur.execute("SELECT id FROM usuarios WHERE usuario = %s AND id != %s", 
                   (data['usuario'], user_id))
        if cur.fetchone():
            return jsonify({"error": "Nome de usuário já está em uso."}), 400
        
        # Preparar campos para atualização
        campos_update = []
        valores = []
        
        campos_base = ['nome', 'usuario', 'cargo', 'email', 'telefone', 'cpf', 'status']
        
        for campo in campos_base:
            if campo in data:
                campos_update.append(f"{campo} = %s")
                valores.append(data[campo].strip() if data[campo] else None)
        
        # Se houver nova senha, adicionar à atualização
        if 'senha' in data and data['senha']:
            senha_hash = hash_senha(data['senha'])
            campos_update.append("senha_hash = %s")
            valores.append(senha_hash)
        
        # Adicionar data de atualização
        campos_update.append("atualizado_em = NOW()")
        
        # Executar atualização
        query = f"UPDATE usuarios SET {', '.join(campos_update)} WHERE id = %s"
        valores.append(user_id)
        
        cur.execute(query, tuple(valores))
        conn.commit()
        
        # Buscar usuário atualizado
        cur.execute("""
            SELECT id, nome, usuario, cargo, email, telefone, cpf, status
            FROM usuarios WHERE id = %s
        """, (user_id,))
        
        usuario_atualizado = cur.fetchone()
        
        return jsonify({
            "message": "Usuário atualizado com sucesso!",
            "usuario": {
                "id": usuario_atualizado[0],
                "nome": usuario_atualizado[1],
                "usuario": usuario_atualizado[2],
                "cargo": usuario_atualizado[3],
                "email": usuario_atualizado[4],
                "telefone": usuario_atualizado[5],
                "cpf": usuario_atualizado[6],
                "status": usuario_atualizado[7]
            }
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Erro ao atualizar usuário: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ========================================================
#  ALTERAR STATUS DO USUÁRIO (PARA ADMINS) - CORRIGIDO
# ========================================================
@usuarios_bp.put("/status/<int:user_id>")
def alterar_status(user_id):
    """Altera o status de um usuário (ativo/inativo)."""
    # Verificar se o usuário é admin pelo cargo
    if not verificar_admin():
        print(f"USUÁRIO NÃO É ADMIN! Tentativa de alterar status por cargo: {getattr(current_user, 'cargo', '')}")
        return jsonify({"error": "Acesso negado. Somente administradores."}), 403
    
    data = request.get_json()
    novo_status = data.get("status")
    
    if novo_status not in ["ativo", "inativo"]:
        return jsonify({"error": "Status inválido. Use 'ativo' ou 'inativo'."}), 400
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Verificar se o usuário existe
        cur.execute("SELECT id FROM usuarios WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado."}), 404
        
        # Não permitir desativar a si mesmo
        if user_id == getattr(current_user, 'id', None):
            return jsonify({"error": "Não é possível alterar seu próprio status."}), 400
        
        cur.execute("""
            UPDATE usuarios 
            SET status = %s, atualizado_em = NOW() 
            WHERE id = %s
        """, (novo_status, user_id))
        
        conn.commit()
        
        return jsonify({
            "message": f"Status do usuário alterado para '{novo_status}' com sucesso!"
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Erro ao alterar status: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ========================================================
#  VERIFICAR PERMISSÕES DO USUÁRIO ATUAL - CORRIGIDO
# ========================================================
@usuarios_bp.get("/permissao")
def verificar_permissao():
    """Verifica se o usuário atual é admin pelo cargo."""
    try:
        # Coletar dados de várias fontes
        user_id_flask = getattr(current_user, 'id', None)
        cargo_flask = getattr(current_user, 'cargo', '')
        
        user_id_sessao = None
        cargo_sessao = ''
        nome_sessao = ''
        usuario_sessao = ''
        
        if session and 'usuarios' in session:
            user_id_sessao = session['usuarios'].get('id')
            cargo_sessao = session['usuarios'].get('cargo', '')
            nome_sessao = session['usuarios'].get('nome', '')
            usuario_sessao = session['usuarios'].get('usuario', '')
        
        # Verificar se é admin usando ambas as fontes
        is_admin_flask = cargo_flask and str(cargo_flask).strip() in CARGOS_ADMIN
        is_admin_sessao = cargo_sessao and str(cargo_sessao).strip() in CARGOS_ADMIN
        
        is_admin = is_admin_flask or is_admin_sessao
        
        # Usar o cargo da sessão se disponível
        cargo_final = cargo_sessao or cargo_flask or ''
        
        return jsonify({
            "is_admin": is_admin,
            "user_id": user_id_sessao or user_id_flask,
            "nome": nome_sessao or getattr(current_user, 'nome', ''),
            "usuario": usuario_sessao or getattr(current_user, 'usuario', ''),
            "cargo": cargo_final,
            "cargos_admin": CARGOS_ADMIN,
            "debug": {
                "cargo_flask": cargo_flask,
                "cargo_sessao": cargo_sessao,
                "is_admin_flask": is_admin_flask,
                "is_admin_sessao": is_admin_sessao
            }
        })
    except Exception as e:
        return jsonify({"error": f"Erro ao verificar permissão: {str(e)}"}), 500

# ========================================================
#  BUSCAR USUÁRIO POR ID (PARA ADMINS) - CORRIGIDO
# ========================================================
@usuarios_bp.get("/buscar/<int:user_id>")
def buscar_usuario(user_id):
    """Busca um usuário específico."""
    # Verificar se o usuário é admin pelo cargo
    if not verificar_admin():
        print(f"USUÁRIO NÃO É ADMIN! Tentativa de buscar usuário por cargo: {getattr(current_user, 'cargo', '')}")
        return jsonify({"error": "Acesso negado. Somente administradores."}), 403
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                id,
                nome,
                usuario,
                cargo,
                email,
                telefone,
                cpf,
                status,
                criado_em,
                atualizado_em
            FROM usuarios
            WHERE id = %s
        """, (user_id,))
        
        usuario = cur.fetchone()
        
        if not usuario:
            return jsonify({"error": "Usuário não encontrado."}), 404
        
        return jsonify({
            "id": usuario[0],
            "nome": usuario[1],
            "usuario": usuario[2],
            "cargo": usuario[3],
            "email": usuario[4],
            "telefone": usuario[5],
            "cpf": usuario[6],
            "status": usuario[7],
            "criado_em": usuario[8].isoformat() if usuario[8] else None,
            "atualizado_em": usuario[9].isoformat() if usuario[9] else None
        })
        
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar usuário: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ========================================================
#  LISTAR TODOS OS CARGOS DISPONÍVEIS
# ========================================================
@usuarios_bp.get("/cargos")
def listar_cargos():
    """Lista todos os cargos disponíveis no sistema."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Usuário não autenticado"}), 401
    
    # Definir todos os cargos possíveis
    TODOS_CARGOS = [
        'Auxiliar de Topografia', 'Ajudante de Campo', 'Topógrafo', 
        'Técnico em Topografia', 'Técnico em Geomática', 'Operador de Estação Total', 
        'Operador GNSS', 'Piloto de Drone (VANT/RPA)', 'Piloto ANAC (RPA)', 
        'Assistente de Campo', 'Encarregado de Campo', 'Desenhista Técnico', 
        'Desenhista CAD', 'Projetista', 'Analista de Geoprocessamento', 
        'Analista SIG (GIS)', 'Analista de Geodésia', 'Técnico SIG', 
        'Encarregado de Topografia', 'Supervisor de Topografia', 
        'Coordenador de Topografia', 'Gerente de Topografia',
        'Assistente Administrativo', 'Analista Administrativo',
        'Almoxarife', 'RH / DP', 'Financeiro', 'Gestor', 'admin'
    ]
    
    return jsonify({
        "cargos": TODOS_CARGOS,
        "cargos_admin": CARGOS_ADMIN
    })