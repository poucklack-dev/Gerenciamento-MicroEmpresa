from flask import Blueprint, request, jsonify
from core.database import get_conn
from psycopg2.extras import DictCursor
import re
from datetime import datetime
import logging
from functools import wraps
from flask_login import current_user

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp_colab = Blueprint("colaboradores", __name__, url_prefix="/api/colaboradores")

# ============================================================
# DECORADOR DE AUTENTICAÇÃO (PLACEHOLDER - AJUSTAR CONFORME SUA IMPLEMENTAÇÃO)
# ============================================================
def require_admin(f):
    """
    Decorator seguro para exigir permissões de admin/gestor.
    Protege rotas sensíveis contra acesso não autorizado.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"erro": "Acesso negado. Faça login."}), 401
        
        cargo = getattr(current_user, 'cargo', '')
        # Lista de cargos com permissão administrativa (sincronizada com usuario.py)
        cargos_permitidos = ['Gestor', 'admin', 'Gerente de Topografia', 'Coordenador de Topografia', 'Supervisor de Topografia']
        
        if str(cargo).strip() not in cargos_permitidos:
            return jsonify({"erro": "Acesso negado. Permissão insuficiente."}), 403
            
        return f(*args, **kwargs)
    return wrapper

# ============================================================
# VALIDADORES
# ============================================================

def validar_cpf(cpf):
    cpf = re.sub(r'[^0-9]', '', cpf or '')
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    s = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (s * 10 % 11) % 10
    if d1 != int(cpf[9]): return False
    s = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (s * 10 % 11) % 10
    return d2 == int(cpf[10])

def validar_email(email):
    if not email: return True
    return bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email))

def validar_telefone(tel):
    if not tel: return True
    return bool(re.fullmatch(r"\d{10,11}", tel))

def validar_rg(rg):
    return bool(re.fullmatch(r"\d{5,12}", rg or ""))

CARGOS = {
    'Auxiliar de Topografia','Ajudante de Campo','Topógrafo','Técnico em Topografia',
    'Técnico em Geomática','Operador de Estação Total','Operador GNSS',
    'Piloto de Drone (VANT/RPA)','Piloto ANAC (RPA)','Assistente de Campo',
    'Encarregado de Campo','Desenhista Técnico','Desenhista CAD','Projetista',
    'Analista de Geoprocessamento','Analista SIG (GIS)','Analista de Geodésia',
    'Técnico SIG','Encarregado de Topografia','Supervisor de Topografia',
    'Coordenador de Topografia','Gerente de Topografia',
    'Assistente Administrativo','Analista Administrativo',
    'Almoxarife','RH / DP','Financeiro', 'Gestor'
}

def validar_cargo(c): return c in CARGOS

def validar_data(data_str):
    if not data_str:
        return True
    try:
        datetime.strptime(data_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

# ============================================================
# UTILITÁRIOS PARA DETECTAR DEPENDÊNCIAS
# ============================================================

def detectar_dependencias_colaborador(colaborador_id):
    """
    Detecta todas as tabelas que possuem FK para colaboradores.id
    Retorna lista de dependências com contagem
    """
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Consulta para encontrar todas as FKs que apontam para colaboradores.id
        query = """
        SELECT 
            tc.table_name as tabela_filha,
            kcu.column_name as coluna_filha,
            c.conname as constraint_name,
            c.confupdtype as update_action,
            c.confdeltype as delete_action
        FROM 
            information_schema.table_constraints tc
        JOIN 
            information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN 
            information_schema.constraint_column_usage ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN 
            pg_constraint c 
            ON c.conname = tc.constraint_name
        WHERE 
            tc.constraint_type = 'FOREIGN KEY'
            AND ccu.table_name = 'colaboradores'
            AND ccu.column_name = 'id'
        ORDER BY 
            tc.table_name;
        """
        
        cur.execute(query)
        fks = cur.fetchall()
        
        dependencias = []
        
        for tabela, coluna, constraint, update_action, delete_action in fks:
            # Contar registros dependentes
            count_query = f"SELECT COUNT(*) FROM {tabela} WHERE {coluna} = %s"
            cur.execute(count_query, (colaborador_id,)) # Seguro, pois tabela/coluna vêm do information_schema
            count = cur.fetchone()[0]
            
            if count > 0:
                dependencias.append({
                    "tabela": tabela,
                    "coluna": coluna,
                    "constraint": constraint,
                    "count": count,
                    "update_action": update_action,
                    "delete_action": delete_action
                })
        
        return dependencias
        
    except Exception as e:
        logger.error(f"Erro ao detectar dependências: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def verificar_colaborador_existe(colaborador_id):
    """Verifica se colaborador existe e retorna seu status"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, nome, status FROM colaboradores WHERE id = %s", (colaborador_id,))
        result = cur.fetchone()
        return result
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# ============================================================
# SERIALIZADORES
# ============================================================

def serialize_colaborador(r):
    return {
        "id": r["id"], "nome": r["nome"], "cargo": r["cargo"], "funcao": r["funcao"], "status": r["status"],
        "email": r["email"], "telefone": r["telefone"], "cnh": r["cnh"], "validade_cnh": r["validade_cnh"],
        "endereco": r["endereco"], "salario": float(r["salario"]) if r["salario"] else None,
        "data_admissao": r["data_admissao"], "data_demissao": r["data_demissao"], "foto": r["foto"],
        "criado_em": r["criado_em"],

        "cpf": r["cpf"], "data_nascimento": r["data_nascimento"], "rg": r["rg"], "orgao_emissor": r["orgao_emissor"],
        "pis_pasep": r["pis_pasep"], "ctps_numero": r["ctps_numero"], "ctps_serie": r["ctps_serie"], "estado_civil": r["estado_civil"],
        "nome_mae": r["nome_mae"], "nome_pai": r["nome_pai"], "titulo_eleitor": r["titulo_eleitor"],

        "comprovante_residencia": r["comprovante_residencia"], "comprovante_escolaridade": r["comprovante_escolaridade"],
        "banco": r["banco"], "agencia": r["agencia"], "conta": r["conta"],

        "aso_admissional": r["aso_admissional"], "aso_periodico": r["aso_periodico"], "aso_mudanca_funcao": r["aso_mudanca_funcao"],
        "aso_retorno_trabalho": r["aso_retorno_trabalho"], "aso_demissional": r["aso_demissional"], "validade_aso": r["validade_aso"],
        "exames_complementares": r["exames_complementares"],

        "afastamento_tipo": r["afastamento_tipo"], "afastamento_inicio": r["afastamento_inicio"], "afastamento_fim": r["afastamento_fim"],
        "afastamento_laudo": r["afastamento_laudo"],

        "nr01_validade": r["nr01_validade"], "nr06_validade": r["nr06_validade"], "nr10_validade": r["nr10_validade"],
        "nr11_validade": r["nr11_validade"], "nr12_validade": r["nr12_validade"], "nr17_validade": r["nr17_validade"],
        "nr18_validade": r["nr18_validade"], "nr33_validade": r["nr33_validade"], "nr35_validade": r["nr35_validade"],

        "curso_topografia_validade": r["curso_topografia_validade"], "curso_estacao_total_validade": r["curso_estacao_total_validade"],
        "curso_gnss_validade": r["curso_gnss_validade"], "curso_drone_validade": r["curso_drone_validade"],
        "anac_rpa_validade": r["anac_rpa_validade"], "curso_iso9001_validade": r["curso_iso9001_validade"],
        "curso_iso14001_validade": r["curso_iso14001_validade"], "brigada_incendio_validade": r["brigada_incendio_validade"],
        "primeiros_socorros_validade": r["primeiros_socorros_validade"],

        "crea_numero": r["crea_numero"], "crea_validade": r["crea_validade"], "cria_profissao": r["cria_profissao"],
        "art_responsavel": r["art_responsavel"],

        "saldo_ferias": r["saldo_ferias"], "ferias_ultimo_periodo_inicio": r["ferias_ultimo_periodo_inicio"],
        "ferias_ultimo_periodo_fim": r["ferias_ultimo_periodo_fim"], "ferias_agendadas_inicio": r["ferias_agendadas_inicio"],
        "ferias_agendadas_fim": r["ferias_agendadas_fim"],

        "termo_responsabilidade_veiculo": r["termo_responsabilidade_veiculo"], "apto_dirigir": r["apto_dirigir"],

        "aso_admissional_status": r["aso_admissional_status"], "aso_admissional_data": r["aso_admissional_data"],
        "aso_periodico_status": r["aso_periodico_status"], "aso_periodico_data": r["aso_periodico_data"],
        "aso_mudanca_funcao_status": r["aso_mudanca_funcao_status"], "aso_mudanca_funcao_data": r["aso_mudanca_funcao_data"],
        "aso_retorno_trabalho_status": r["aso_retorno_trabalho_status"], "aso_retorno_trabalho_data": r["aso_retorno_trabalho_data"],
        "aso_demissional_status": r["aso_demissional_status"], "aso_demissional_data": r["aso_demissional_data"]
    }

def serialize_colaborador_simples(r):
    return {
        "id": r["id"],
        "nome": r["nome"],
        "status": r["status"]
    }

def serialize_epi(e): return {"id": e[0], "nome": e[1]}
def serialize_habilidade(h): return {"id": h[0], "nome": h[1]}
def serialize_nr(n): return {"id": n[0], "codigo": n[1], "nome": n[2], "descricao": n[3]}

# ============================================================
# ROTAS NRs (NORMAS REGULAMENTADORAS) - SISTEMA COMPLETO
# ============================================================

@bp_colab.post("/nrs")
@require_admin
def criar_nr():
    """Cria uma nova Norma Regulamentadora no catálogo"""
    try:
        data = request.json
        codigo = data.get("codigo")  # Ex: "NR-01", "NR-06", etc.
        nome = data.get("nome")      # Ex: "Disposições Gerais", "EPI", etc.
        descricao = data.get("descricao", "")

        if not codigo or not nome:
            return jsonify({"erro": "Código e nome são obrigatórios"}), 400

        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Verificar se código já existe
        cur.execute("SELECT id FROM nrs WHERE codigo = %s", (codigo,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"erro": f"NR com código {codigo} já existe"}), 409

        # Inserir nova NR
        cur.execute(
            "INSERT INTO nrs (codigo, nome, descricao) VALUES (%s, %s, %s) RETURNING id, codigo, nome, descricao",
            (codigo, nome, descricao)
        )
        
        resultado = cur.fetchone()
        nr_id = resultado[0]
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "mensagem": "NR criada com sucesso",
            "nr": {
                "id": nr_id,
                "codigo": resultado[1],
                "nome": resultado[2],
                "descricao": resultado[3]
            }
        }), 201
    except Exception as e:
        logger.error(f"Erro em criar_nr: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/nrs")
def listar_nrs():
    """Lista todas as NRs cadastradas"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, codigo, nome, descricao FROM nrs ORDER BY codigo")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([
            {
                "id": r["id"],
                "codigo": r["codigo"],
                "nome": r["nome"],
                "descricao": r["descricao"]
            } for r in rows
        ]), 200
    except Exception as e:
        logger.error(f"Erro em listar_nrs: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/nrs/<int:id>")
@require_admin
def excluir_nr(id):
    """Exclui uma NR do catálogo"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # Verificar se a NR existe
        cur.execute("SELECT codigo, nome FROM nrs WHERE id = %s", (id,))
        nr = cur.fetchone()
        
        if not nr:
            return jsonify({"erro": "NR não encontrada"}), 404
        
        # Verificar se há associações com colaboradores
        cur.execute("SELECT COUNT(*) FROM nrs_colaboradores WHERE nr_id = %s", (id,))
        count = cur.fetchone()[0]
        
        if count > 0:
            return jsonify({
                "erro": f"Não é possível excluir a {nr['codigo']} - {nr['nome']} pois está associada a {count} colaborador(es)",
                "sugestao": "Remova as associações primeiro ou use a opção de exclusão forçada"
            }), 400
        
        # Excluir a NR
        cur.execute("DELETE FROM nrs WHERE id = %s", (id,))
        conn.commit()

        return jsonify({
            "mensagem": f"NR {nr[0]} - {nr[1]} excluída com sucesso"
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir NR: {e}")
        return jsonify({"erro": f"Erro ao excluir NR: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

@bp_colab.post("/<int:colab_id>/nrs")
@require_admin
def adicionar_nr_colaborador(colab_id):
    """Associa uma NR a um colaborador com data de validade"""
    try:
        data = request.json
        nr_id = data.get("nr_id")
        data_validade = data.get("data_validade")
        
        if not nr_id or not data_validade:
            return jsonify({"erro": "NR e data de validade são obrigatórios"}), 400
        
        # Validar formato da data
        try:
            datetime.strptime(data_validade, '%Y-%m-%d')
        except ValueError:
            return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400
        
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Verificar se colaborador existe
        cur.execute("SELECT id FROM colaboradores WHERE id = %s", (colab_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # Verificar se NR existe
        cur.execute("SELECT codigo, nome FROM nrs WHERE id = %s", (nr_id,))
        nr = cur.fetchone()
        if not nr:
            cur.close()
            conn.close()
            return jsonify({"erro": "NR não encontrada"}), 404
        
        # Verificar se já existe associação
        cur.execute(
            "SELECT id FROM nrs_colaboradores WHERE colaborador_id = %s AND nr_id = %s",
            (colab_id, nr_id)
        )
        if cur.fetchone():
            # Atualizar existente
            cur.execute(
                "UPDATE nrs_colaboradores SET data_validade = %s WHERE colaborador_id = %s AND nr_id = %s",
                (data_validade, colab_id, nr_id)
            )
            mensagem = "Data de validade atualizada"
        else:
            # Criar nova associação
            cur.execute(
                """INSERT INTO nrs_colaboradores 
                   (colaborador_id, nr_id, data_validade) 
                   VALUES (%s, %s, %s)""",
                (colab_id, nr_id, data_validade)
            )
            mensagem = "NR associada ao colaborador"
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "mensagem": mensagem,
            "nr": {
                "codigo": nr[0],
                "nome": nr[1]
            },
            "data_validade": data_validade
        }), 201
        
    except Exception as e:
        logger.error(f"Erro em adicionar_nr_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/<int:colab_id>/nrs")
@require_admin
def listar_nrs_colaborador(colab_id):
    """Lista todas as NRs associadas a um colaborador"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute("""
            SELECT nc.id, n.codigo, n.nome, n.descricao, nc.data_validade,
                   CASE 
                       WHEN nc.data_validade < CURRENT_DATE THEN 'vencida'
                       WHEN nc.data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN 'prestes_a_vencer'
                       ELSE 'valida'
                   END as status_validade
            FROM nrs_colaboradores nc
            JOIN nrs n ON n.id = nc.nr_id
            WHERE nc.colaborador_id = %s
            ORDER BY n.codigo
        """, (colab_id,))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([
            {
                "id": r["id"],
                "codigo": r["codigo"],
                "nome": r["nome"],
                "descricao": r["descricao"],
                "data_validade": r["data_validade"],
                "status_validade": r["status_validade"]
            } for r in rows
        ]), 200
        
    except Exception as e:
        logger.error(f"Erro em listar_nrs_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/nrs_colaboradores/<int:id_associacao>")
@require_admin
def remover_nr_colaborador(id_associacao):
    """Remove uma associação entre NR e colaborador"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Obter informações da associação antes de excluir
        cur.execute("""
            SELECT n.codigo, n.nome, c.nome as colaborador
            FROM nrs_colaboradores nc
            JOIN nrs n ON n.id = nc.nr_id
            JOIN colaboradores c ON c.id = nc.colaborador_id
            WHERE nc.id = %s
        """, (id_associacao,))
        
        associacao = cur.fetchone()
        
        if not associacao:
            cur.close()
            conn.close()
            return jsonify({"erro": "Associação não encontrada"}), 404
        
        # Excluir a associação
        cur.execute("DELETE FROM nrs_colaboradores WHERE id = %s", (id_associacao,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "mensagem": f"Associação da {associacao['codigo']} - {associacao['nome']} com {associacao['colaborador']} removida com sucesso"
        }), 200
        
    except Exception as e:
        logger.error(f"Erro em remover_nr_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/nrs/proximas_vencimentos")
@require_admin
def listar_nrs_proximas_vencimentos():
    """Lista NRs que estão prestes a vencer (30 dias)"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute("""
            SELECT 
                c.id as colaborador_id,
                c.nome as colaborador_nome,
                n.codigo as nr_codigo,
                n.nome as nr_nome,
                nc.data_validade,
                DATE_PART('day', nc.data_validade - CURRENT_DATE)::integer as dias_para_vencer
            FROM nrs_colaboradores nc
            JOIN colaboradores c ON c.id = nc.colaborador_id
            JOIN nrs n ON n.id = nc.nr_id
            WHERE c.status = 'ativo'
                AND nc.data_validade BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            ORDER BY nc.data_validade ASC, c.nome
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([
            {
                "colaborador_id": r["colaborador_id"],
                "colaborador_nome": r["colaborador_nome"],
                "nr_codigo": r["nr_codigo"],
                "nr_nome": r["nr_nome"],
                "data_validade": r["data_validade"],
                "dias_para_vencer": r["dias_para_vencer"]
            } for r in rows
        ]), 200
        
    except Exception as e:
        logger.error(f"Erro em listar_nrs_proximas_vencimentos: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

# ============================================================
# ROTAS COLABORADORES - NOVAS FUNCIONALIDADES
# ============================================================

@bp_colab.get("/ativos")
def listar_colaboradores_ativos():
    """Lista apenas colaboradores ativos"""
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, nome, status FROM colaboradores WHERE status = 'ativo' ORDER BY nome")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([serialize_colaborador_simples(r) for r in rows]), 200
    except Exception as e:
        logger.error(f"Erro em listar_colaboradores_ativos: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/<int:id>/dependencias")
@require_admin
def listar_dependencias_colaborador(id):
    """Endpoint para listar dependências de um colaborador"""
    try:
        # Verificar se colaborador existe
        colaborador = verificar_colaborador_existe(id)
        if not colaborador:
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # Detectar dependências
        dependencias = detectar_dependencias_colaborador(id)
        
        return jsonify({
            "colaborador_id": id,
            "colaborador_nome": colaborador["nome"],
            "colaborador_status": colaborador["status"],
            "dependencias": dependencias,
            "total_dependencias": len(dependencias)
        }), 200
        
    except Exception as e:
        logger.error(f"Erro em listar_dependencias_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

# ============================================================
# SOFT DELETE (DESATIVAÇÃO) - MELHORADO
# ============================================================

@bp_colab.delete("/<int:id>")
@require_admin
def excluir_colaborador(id):
    """Soft delete - marca como inativo"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # 1. Verificar se colaborador existe
        cur.execute("SELECT id, nome, status FROM colaboradores WHERE id = %s", (id,))
        colaborador = cur.fetchone()
        
        if not colaborador:
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # 2. Executar soft delete
        # Determinar tipo da coluna data_demissao para usar valor correto
        cur.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'colaboradores' 
            AND column_name = 'data_demissao'
        """)
        tipo_data = cur.fetchone()
        
        valor_data = "NOW()"  # timestamp por padrão
        if tipo_data and tipo_data[0] == 'date':
            valor_data = "CURRENT_DATE"
        
        query = f"""
            UPDATE colaboradores 
            SET status = 'inativo', data_demissao = {valor_data}
            WHERE id = %s
            RETURNING id, nome, status, data_demissao
        """
        
        cur.execute(query, (id,))
        resultado = cur.fetchone()
        
        if not resultado:
            return jsonify({"erro": "Nenhuma linha afetada - possível erro de concorrência"}), 400
        
        conn.commit()
        
        return jsonify({
            "mensagem": "Colaborador desativado com sucesso",
            "id": resultado["id"],
            "nome": resultado["nome"],
            "status": resultado["status"],
            "data_demissao": str(resultado["data_demissao"])
        }), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erro em excluir_colaborador (soft delete): {e}")
        return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# ============================================================
# HARD DELETE (EXCLUSÃO PERMANENTE) COM 3 MODOS
# ============================================================

@bp_colab.delete("/<int:id>/permanent")
@require_admin
def excluir_colaborador_permanentemente(id):
    """Hard delete com 3 modos: default (seguro), force, transfer"""
    conn = None
    cur = None
    
    try:
        # Obter parâmetros da query string
        force_mode = request.args.get('force', '').lower() == 'true'
        transfer_to = request.args.get('transfer_to')
        mode = request.args.get('mode', 'default')  # default, force, transfer
        
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # 1. Verificar se colaborador existe e está inativo
        cur.execute("SELECT id, nome, status FROM colaboradores WHERE id = %s", (id,))
        colaborador = cur.fetchone()
        
        if not colaborador:
            return jsonify({"erro": "Colaborador não encontrado"}), 404

        if colaborador["status"] != 'inativo':
            return jsonify({
                "erro": "Colaborador não está inativo",
                "status_atual": colaborador["status"],
                "sugestao": f"Use DELETE /api/colaboradores/{id} para desativar antes da exclusão permanente",
                "modo_sugerido": "soft_delete"
            }), 400
        
        colaborador_nome = colaborador[1]
        
        # 2. Detectar dependências
        dependencias = detectar_dependencias_colaborador(id)
        
        # 3. MODO DEFAULT: verificar e bloquear se houver dependências
        if mode == 'default' and dependencias and not force_mode and not transfer_to:
            return jsonify({
                "erro": "Não é possível excluir permanentemente por dependências",
                "colaborador_id": id,
                "colaborador_nome": colaborador["nome"],
                "dependencias": dependencias,
                "total_registros_dependentes": sum(d['count'] for d in dependencias),
                "opcoes": [
                    "Adicione ?force=true à URL para apagar registros dependentes",
                    "Adicione ?transfer_to=<novo_id> para transferir histórico (quando aplicável)",
                    "Use GET /api/colaboradores/{id}/dependencias para detalhes"
                ],
                "modo_atual": "default"
            }), 409
        
        # 4. MODO FORCE: apagar registros dependentes primeiro
        if force_mode:
            try:
                # Ordenar dependências por tipo de ação (cascata primeiro)
                for dep in dependencias:
                    tabela = dep['tabela']
                    coluna = dep['coluna']
                    
                    # Verificar se a FK tem CASCADE ou RESTRICT
                    if dep['delete_action'] == 'c':
                        # CASCADE - será apagado automaticamente
                        continue
                    
                    # Apagar manualmente
                    delete_query = f"DELETE FROM {tabela} WHERE {coluna} = %s"
                    cur.execute(delete_query, (id,))
                    logger.info(f"Force mode: apagados {cur.rowcount} registros de {tabela}")
                
                # Apagar colaborador
                cur.execute("DELETE FROM colaboradores WHERE id = %s", (id,))
                
                if cur.rowcount == 0:
                    raise Exception("Nenhuma linha do colaborador foi apagada")
                
                conn.commit()
                
                return jsonify({
                    "mensagem": "Colaborador excluído permanentemente com remoção de dependências",
                    "colaborador_id": id,
                    "colaborador_nome": colaborador_nome,
                    "deleted": True,
                    "dependencias_apagadas": dependencias,
                    "modo_utilizado": "force"
                }), 200
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro no modo force: {e}")
                return jsonify({
                    "erro": "Falha ao apagar dependências",
                    "mensagem": str(e),
                    "dependencias": dependencias,
                    "modo": "force"
                }), 500
        
        # 5. MODO TRANSFER: transferir dependências para outro colaborador
        elif transfer_to:
            try:
                transfer_to_id = int(transfer_to)
                
                # Verificar se o colaborador de destino existe e é diferente
                if transfer_to_id == id:
                    return jsonify({
                        "erro": "Não é possível transferir para o mesmo colaborador"
                    }), 400
                
                cur.execute("SELECT id, nome, status FROM colaboradores WHERE id = %s", (transfer_to_id,))
                destino = cur.fetchone()
                
                if not destino:
                    return jsonify({"erro": "Colaborador de destino não encontrado"}), 404
                
                # Verificar se destino está ativo
                if destino[2] != 'ativo':
                    return jsonify({
                        "erro": "Colaborador de destino não está ativo",
                        "sugestao": "Selecione um colaborador ativo para transferência"
                    }), 400

                # Transferir dependências
                tabelas_atualizadas = []
                tabelas_com_problema = []
                
                for dep in dependencias:
                    tabela = dep['tabela']
                    coluna = dep['coluna']
                    
                    # Verificar se é uma tabela onde transferência faz sentido
                    # (excluir tabelas de histórico sensível que não devem ser transferidas)
                    tabelas_nao_transferiveis = [
                        'logs_sensíveis',  # Exemplo - ajustar conforme seu esquema
                        'auditoria'        # Exemplo - ajustar conforme seu esquema
                    ]
                    
                    if tabela in tabelas_nao_transferiveis:
                        tabelas_com_problema.append({
                            "tabela": tabela,
                            "motivo": "Tabela de histórico sensível não transferível"
                        })
                        continue
                    
                    try:
                        # Verificar se a coluna existe na tabela
                        cur.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = %s 
                            AND column_name = %s
                        """, (tabela, coluna))
                        
                        if not cur.fetchone():
                            # Tentar encontrar coluna com nome similar
                            cur.execute(f"""
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = %s 
                                AND column_name LIKE '%%colaborador%%'
                            """, (tabela,))
                            coluna_alternativa = cur.fetchone()
                            
                            if coluna_alternativa:
                                coluna = coluna_alternativa[0]
                            else:
                                tabelas_com_problema.append({
                                    "tabela": tabela,
                                    "motivo": f"Coluna {coluna} não encontrada"
                                })
                                continue
                        
                        # Executar transferência
                        update_query = f"UPDATE {tabela} SET {coluna} = %s WHERE {coluna} = %s"
                        cur.execute(update_query, (transfer_to_id, id))
                        registros_transferidos = cur.rowcount
                        
                        if registros_transferidos > 0:
                            tabelas_atualizadas.append({
                                "tabela": tabela,
                                "coluna": coluna,
                                "registros_transferidos": registros_transferidos
                            })
                            
                    except Exception as update_error:
                        tabelas_com_problema.append({
                            "tabela": tabela,
                            "motivo": str(update_error)
                        })
                
                # Se houver tabelas com problemas, verificar se podemos continuar
                if tabelas_com_problema and len(tabelas_atualizadas) == 0:
                    return jsonify({
                        "erro": "Não foi possível transferir nenhum registro",
                        "tabelas_com_problema": tabelas_com_problema,
                        "sugestao": "Use o modo force=true ou contate o administrador"
                    }), 409
                
                # Apagar colaborador original
                cur.execute("DELETE FROM colaboradores WHERE id = %s", (id,))
                
                conn.commit()
                
                return jsonify({
                    "mensagem": "Colaborador excluído com transferência de histórico",
                    "colaborador_origem": {
                        "id": id,
                        "nome": colaborador_nome
                    },
                    "colaborador_destino": {
                        "id": transfer_to_id,
                        "nome": destino["nome"]
                    },
                    "transferido_para": transfer_to_id,
                    "tabelas_atualizadas": tabelas_atualizadas,
                    "tabelas_com_problema": tabelas_com_problema if tabelas_com_problema else None,
                    "modo_utilizado": "transfer"
                }), 200
                
            except ValueError:
                return jsonify({"erro": "ID de transferência inválido"}), 400
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro no modo transfer: {e}")
                return jsonify({
                    "erro": "Falha na transferência de dependências",
                    "mensagem": str(e)
                }), 500
        
        # 6. MODO DEFAULT SEM DEPENDÊNCIAS: apagar diretamente
        else:
            try:
                # Apagar registros em tabelas filhas primeiro (se houver CASCADE, isso é opcional)
                for dep in dependencias:
                    if dep['delete_action'] != 'c':  # Se não for CASCADE
                        tabela = dep['tabela']
                        coluna = dep['coluna']
                        delete_query = f"DELETE FROM {tabela} WHERE {coluna} = %s"
                        cur.execute(delete_query, (id,))
                
                # Apagar colaborador
                cur.execute("DELETE FROM colaboradores WHERE id = %s", (id,))
                
                if cur.rowcount == 0:
                    return jsonify({"erro": "Nenhuma linha afetada - possível erro de concorrência"}), 400
                
                conn.commit()
                
                return jsonify({
                    "mensagem": "Colaborador excluído permanentemente",
                    "colaborador_id": id,
                    "colaborador_nome": colaborador["nome"],
                    "deleted": True,
                    "dependencias_removidas": dependencias if dependencias else None,
                    "modo_utilizado": "default_sem_dependencias"
                }), 200
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro no hard delete: {e}")
                
                # Verificar se é erro de FK
                if "foreign key constraint" in str(e).lower():
                    # Recalcular dependências
                    try:
                        dependencias_recalc = detectar_dependencias_colaborador(id)
                        return jsonify({
                            "erro": "Violação de chave estrangeira detectada",
                            "dependencias": dependencias_recalc,
                            "sugestao": "Use force=true ou transfer_to para resolver dependências"
                        }), 409
                    except:
                        pass
                
                return jsonify({
                    "erro": "Erro interno ao excluir colaborador",
                    "mensagem": str(e)
                }), 500
    
    except Exception as e:
        logger.error(f"Erro em excluir_colaborador_permanentemente: {e}")
        return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# ============================================================
# ROTAS EXISTENTES (MANTIDAS PARA COMPATIBILIDADE)
# ============================================================

@bp_colab.get("/")
@require_admin
def listar_colaboradores():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM colaboradores ORDER BY nome") # SELECT * é ok aqui pois serialize_colaborador usa nomes
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([serialize_colaborador(r) for r in rows]), 200
    except Exception as e:
        logger.error(f"Erro em listar_colaboradores: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/<int:id>")
@require_admin
def obter_colaborador(id):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM colaboradores WHERE id=%s", (id,)) # SELECT * é ok aqui pois serialize_colaborador usa nomes
        r = cur.fetchone()
        cur.close()
        conn.close()
        if not r: return jsonify({"erro": "não encontrado"}), 404
        return jsonify(serialize_colaborador(r)), 200
    except Exception as e:
        logger.error(f"Erro em obter_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.post("/")
@require_admin
def criar_colaborador():
    try:
        data = request.json

        if not validar_cpf(data.get("cpf")):
            return jsonify({"erro": "CPF inválido"}), 400

        if not validar_email(data.get("email")):
            return jsonify({"erro": "email inválido"}), 400

        if not validar_telefone(data.get("telefone")):
            return jsonify({"erro": "telefone inválido"}), 400

        if not validar_cargo(data.get("cargo")):
            return jsonify({"erro": "cargo inválido"}), 400

        campos = [
            "nome","cargo","funcao","status","email","telefone","cnh","validade_cnh","endereco","salario",
            "data_admissao","data_demissao","foto","cpf","data_nascimento","rg","orgao_emissor","pis_pasep",
            "ctps_numero","ctps_serie","estado_civil","nome_mae","nome_pai","titulo_eleitor",
            "comprovante_residencia","comprovante_escolaridade","banco","agencia","conta",
            "aso_admissional","aso_periodico","aso_mudanca_funcao","aso_retorno_trabalho","aso_demissional",
            "validade_aso","exames_complementares",
            "afastamento_tipo","afastamento_inicio","afastamento_fim","afastamento_laudo",
            "nr01_validade","nr06_validade","nr10_validade","nr11_validade","nr12_validade",
            "nr17_validade","nr18_validade","nr33_validade","nr35_validade",
            "curso_topografia_validade","curso_estacao_total_validade","curso_gnss_validade",
            "curso_drone_validade","anac_rpa_validade","curso_iso9001_validade","curso_iso14001_validade",
            "brigada_incendio_validade","primeiros_socorros_validade",
            "crea_numero","crea_validade","cria_profissao","art_responsavel",
            "saldo_ferias","ferias_ultimo_periodo_inicio","ferias_ultimo_periodo_fim",
            "ferias_agendadas_inicio","ferias_agendadas_fim",
            "termo_responsabilidade_veiculo","apto_dirigir",
            "aso_admissional_status","aso_admissional_data",
            "aso_periodico_status","aso_periodico_data",
            "aso_mudanca_funcao_status","aso_mudanca_funcao_data",
            "aso_retorno_trabalho_status","aso_retorno_trabalho_data",
            "aso_demissional_status","aso_demissional_data"
        ]

        valores = [data.get(c) for c in campos]

        query = f"INSERT INTO colaboradores ({','.join(campos)}) VALUES ({','.join(['%s']*len(campos))}) RETURNING id"

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, tuple(valores))
        novo_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Criado", "id": novo_id}), 201
    except Exception as e:
        logger.error(f"Erro em criar_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.put("/<int:id>")
@require_admin
def editar_colaborador(id):
    try:
        data = request.json

        # Whitelist de campos que podem ser atualizados para evitar Mass Assignment
        campos_permitidos = {
            "nome", "cargo", "funcao", "status", "email", "telefone", "cnh", "validade_cnh", "endereco", "salario",
            "data_admissao", "data_demissao", "foto", "cpf", "data_nascimento", "rg", "orgao_emissor", "pis_pasep",
            "ctps_numero", "ctps_serie", "estado_civil", "nome_mae", "nome_pai", "titulo_eleitor",
            "comprovante_residencia", "comprovante_escolaridade", "banco", "agencia", "conta",
            "aso_admissional", "aso_periodico", "aso_mudanca_funcao", "aso_retorno_trabalho", "aso_demissional",
            "validade_aso", "exames_complementares",
            "afastamento_tipo", "afastamento_inicio", "afastamento_fim", "afastamento_laudo",
            "nr01_validade", "nr06_validade", "nr10_validade", "nr11_validade", "nr12_validade",
            "nr17_validade", "nr18_validade", "nr33_validade", "nr35_validade",
            "curso_topografia_validade", "curso_estacao_total_validade", "curso_gnss_validade",
            "curso_drone_validade", "anac_rpa_validade", "curso_iso9001_validade", "curso_iso14001_validade",
            "brigada_incendio_validade", "primeiros_socorros_validade",
            "crea_numero", "crea_validade", "cria_profissao", "art_responsavel",
            "saldo_ferias", "ferias_ultimo_periodo_inicio", "ferias_ultimo_periodo_fim",
            "ferias_agendadas_inicio", "ferias_agendadas_fim",
            "termo_responsabilidade_veiculo", "apto_dirigir",
            "aso_admissional_status", "aso_admissional_data", "aso_periodico_status", "aso_periodico_data",
            "aso_mudanca_funcao_status", "aso_mudanca_funcao_data", "aso_retorno_trabalho_status",
            "aso_retorno_trabalho_data", "aso_demissional_status", "aso_demissional_data"
        }

        sets = []
        vals = []

        mapeamento_campos = {
            'aso_admissional_status': 'aso_admissional_status',
            'aso_admissional_data': 'aso_admissional_data', 
            'aso_periodico_status': 'aso_periodico_status',
            'aso_periodico_data': 'aso_periodico_data',
            'aso_mudanca_funcao_status': 'aso_mudanca_funcao_status',
            'aso_mudanca_funcao_data': 'aso_mudanca_funcao_data',
            'aso_retorno_trabalho_status': 'aso_retorno_trabalho_status',
            'aso_retorno_trabalho_data': 'aso_retorno_trabalho_data',
            'aso_demissional_status': 'aso_demissional_status',
            'aso_demissional_data': 'aso_demissional_data'
        }

        for k, v in data.items():
            # Ignorar campos não permitidos
            if k not in campos_permitidos:
                logger.warning(f"Tentativa de editar campo não permitido: {k}")
                continue

            campo_banco = mapeamento_campos.get(k, k)
            
            if k.endswith('_data') and v:
                if not validar_data(v):
                    print(f"Data inválida ignorada: {k} = {v}")
                    continue
            
            sets.append(f"{campo_banco}=%s")
            vals.append(v)

        if not sets:
            return jsonify({"erro": "nada para atualizar"}), 400

        vals.append(id)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"UPDATE colaboradores SET {','.join(sets)} WHERE id=%s", tuple(vals))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Atualizado"}), 200
    except Exception as e:
        logger.error(f"Erro em editar_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

# ============================================================
# ROTAS EPIs (MANTIDAS)
# ============================================================

@bp_colab.post("/epis")
@require_admin
def criar_epi():
    try:
        nome = request.json.get("nome")
        if not nome:
            return jsonify({"erro": "nome obrigatório"}), 400

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO epis (nome) VALUES (%s) RETURNING id", (nome,))
        eid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "EPI criado", "id": eid}), 201
    except Exception as e:
        logger.error(f"Erro em criar_epi: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/epis")
def listar_epis():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM epis ORDER BY nome")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([serialize_epi(r) for r in rows]), 200
    except Exception as e:
        logger.error(f"Erro em listar_epis: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.post("/<int:colab_id>/epis")
@require_admin
def entregar_epi(colab_id):
    try:
        data = request.json
        epi_id = data.get("epi_id")
        data_entrega = data.get("data_entrega")
        assinatura = data.get("assinatura", False)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO epis_colaboradores (colaborador_id, epi_id, data_entrega, assinatura) VALUES (%s,%s,%s,%s)",
            (colab_id, epi_id, data_entrega, assinatura)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "EPI entregue"}), 201
    except Exception as e:
        logger.error(f"Erro em entregar_epi: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/<int:colab_id>/epis")
@require_admin
def listar_epis_colaborador(colab_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT ec.id, e.nome, ec.data_entrega, ec.assinatura
            FROM epis_colaboradores ec
            JOIN epis e ON e.id = ec.epi_id
            WHERE ec.colaborador_id=%s
        """, (colab_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([
            {"id": r[0], "nome": r[1], "data_entrega": r[2], "assinatura": r[3]}
            for r in rows
        ]), 200
    except Exception as e:
        logger.error(f"Erro em listar_epis_colaborador: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/epis_entregues/<int:id_registro>")
@require_admin
def excluir_epi_entregue(id_registro):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM epis_colaboradores WHERE id=%s", (id_registro,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensagem": "EPI removido"}), 200
    except Exception as e:
        logger.error(f"Erro em excluir_epi_entregue: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/epis/<int:id>")
@require_admin
def excluir_epi_principal(id):
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Verifica se o EPI existe
        cur.execute("SELECT id FROM epis WHERE id=%s", (id,))
        if not cur.fetchone():
            return jsonify({"erro": "EPI não encontrado"}), 404
        
        # Verifica se há entregas deste EPI
        cur.execute("SELECT COUNT(*) FROM epis_colaboradores WHERE epi_id=%s", (id,))
        count = cur.fetchone()[0]
        
        if count > 0:
            return jsonify({"erro": "Não é possível excluir este EPI pois já foi entregue a colaboradores"}), 400
        
        # Exclui o EPI
        cur.execute("DELETE FROM epis WHERE id=%s", (id,))
        conn.commit()
        
        return jsonify({"mensagem": "EPI excluído com sucesso"}), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir EPI: {e}")
        return jsonify({"erro": f"Erro ao excluir EPI: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

# ============================================================
# ROTAS HABILIDADES (MANTIDAS)
# ============================================================

@bp_colab.post("/habilidades")
@require_admin
def criar_habilidade():
    try:
        nome = request.json.get("nome")
        if not nome:
            return jsonify({"erro": "nome obrigatório"}), 400

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO habilidades (nome) VALUES (%s) RETURNING id", (nome,))
        hid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Habilidade criada", "id": hid}), 201
    except Exception as e:
        logger.error(f"Erro em criar_habilidade: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/habilidades")
def listar_habilidades():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM habilidades ORDER BY nome")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([serialize_habilidade(r) for r in rows]), 200
    except Exception as e:
        logger.error(f"Erro em listar_habilidades: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.post("/<int:colab_id>/habilidades")
@require_admin
def adicionar_habilidade(colab_id):
    try:
        data = request.json
        habilidade_id = data.get("habilidade_id")
        nivel = data.get("nivel", "básico")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO habilidades_colaboradores (colaborador_id, habilidade_id, nivel) VALUES (%s,%s,%s)",
            (colab_id, habilidade_id, nivel)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Habilidade adicionada"}), 201
    except Exception as e:
        logger.error(f"Erro em adicionar_habilidade: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.get("/<int:colab_id>/habilidades")
@require_admin
def listar_habilidades_colab(colab_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT hc.id, h.nome, hc.nivel
            FROM habilidades_colaboradores hc
            JOIN habilidades h ON h.id = hc.habilidade_id
            WHERE hc.colaborador_id=%s
        """, (colab_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([
            {"id": r[0], "nome": r[1], "nivel": r[2]}
            for r in rows
        ]), 200
    except Exception as e:
        logger.error(f"Erro em listar_habilidades_colab: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.put("/habilidades_colab/<int:id_registro>")
@require_admin
def editar_habilidade(id_registro):
    try:
        nivel = request.json.get("nivel")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE habilidades_colaboradores SET nivel=%s WHERE id=%s",
            (nivel, id_registro)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Atualizado"}), 200
    except Exception as e:
        logger.error(f"Erro em editar_habilidade: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/habilidades_colab/<int:id_registro>")
@require_admin
def excluir_habilidade(id_registro):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM habilidades_colaboradores WHERE id=%s", (id_registro,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mensagem": "Habilidade removida"}), 200
    except Exception as e:
        logger.error(f"Erro em excluir_habilidade: {e}")
        return jsonify({"erro": "Erro interno do servidor"}), 500

@bp_colab.delete("/habilidades/<int:id>")
@require_admin
def excluir_habilidade_principal(id):
    conn = get_conn()
    cur = conn.cursor()

    try:
        # 1) Verifica se existe
        cur.execute("SELECT nome FROM habilidades WHERE id=%s", (id,))
        habilidade = cur.fetchone()

        if not habilidade:
            return jsonify({"erro": "Habilidade não encontrada"}), 404

        nome_habilidade = habilidade[0]

        # 2) Apaga todas as associações (independente de quem usa)
        cur.execute("""
            DELETE FROM habilidades_colaboradores
            WHERE habilidade_id = %s
        """, (id,))

        # 3) Exclui a habilidade principal
        cur.execute("DELETE FROM habilidades WHERE id=%s", (id,))
        conn.commit()

        return jsonify({
            "mensagem": "Habilidade excluída com sucesso, incluindo todos os vínculos.",
            "habilidade": nome_habilidade
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir habilidade: {e}")
        return jsonify({"erro": f"Erro ao excluir habilidade: {str(e)}"}), 500

    finally:
        cur.close()
        conn.close()