# ========================================================================
#   SISTEMA DE GESTÃO DE CUSTOS VEICULARES - BACKEND COMPLETO CORRIGIDO
#   Versão compatível com o banco de dados real da Patagonia Topografia
# ========================================================================

from flask import Blueprint, request, jsonify, send_file, current_app
from datetime import datetime
from functools import wraps
from flask_login import current_user
import os
import traceback
import io

# ============================================================
#   IMPORTAÇÃO REAL DO BANCO
# ============================================================
from core.database import get_cursor, get_conn
from core.storage import get_storage

# Criar Blueprint
custos_bp = Blueprint("custos", __name__, url_prefix="/api/custos")

# ========================================================================
#   DECORADOR DE AUTENTICAÇÃO
# ========================================================================
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

# ========================================================================
#   FUNÇÕES AUXILIARES
# ========================================================================

def save_uploaded_file(file):
    """Salva arquivo enviado com o serviço de storage e retorna a chave."""
    if not file or not file.filename:
        return None
    try:
        storage = get_storage()
        key = storage.save(file, subdir='custos')
        return key
    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"Erro ao salvar arquivo via storage: {e}")
        return None


def format_float(v):
    """Converte valor para float com segurança"""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def log_error(local, erro):
    """Log de erros detalhado"""
    if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
        print(f"[ERRO - {local}] {erro}")
        traceback.print_exc()


def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False):
    """Executa query no banco com tratamento de erro"""
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(query, params or ())

        if commit:
            conn.commit()
            return True

        if fetchone:
            return cur.fetchone()

        if fetchall:
            return cur.fetchall()

        return True

    except Exception as e:
        conn.rollback()
        log_error("execute_query", e)
        raise e

    finally:
        cur.close()
        conn.close()

# ========================================================================
#   ENDPOINTS DE VEÍCULOS - CORRIGIDO
# ========================================================================

@custos_bp.route("/veiculos", methods=["GET"])
@require_admin
def listar_veiculos():
    """Lista todos os veículos ativos"""
    try:
        # CORREÇÃO: Usar 'ano' em vez de 'ano_fabricacao'
        query = """
            SELECT id, placa, modelo, marca, ano, km_atual, status
            FROM veiculos
            WHERE status = 'ativo'
            ORDER BY placa
        """

        result = execute_query(query, fetchall=True)
        
        veiculos = []
        for r in result:
            veiculos.append({
                "id": r[0],
                "placa": r[1],
                "modelo": r[2],
                "marca": r[3],
                "ano": r[4],  # CORRIGIDO: era ano_fabricacao
                "km_atual": float(r[5]) if r[5] else 0,
                "status": r[6]
            })
        
        return jsonify(veiculos)
        
    except Exception as e:
        log_error("listar_veiculos", e)
        return jsonify({"error": "Erro ao listar veículos"}), 500

# ========================================================================
#   ENDPOINTS DE CONTRATOS - CORRIGIDO
# ========================================================================

@custos_bp.route("/contratos", methods=["GET"])
@require_admin
def listar_contratos():
    """Lista todos os contratos ativos"""
    try:
        # CORREÇÃO: Usar 'valor_orcado' em vez de 'valor_total'
        query = """
            SELECT id, codigo_contrato, nome_empresa, valor_orcado, data_inicio, data_fim
            FROM contratos
            WHERE status = 'ativo'
            ORDER BY nome_empresa
        """

        result = execute_query(query, fetchall=True)
        
        contratos = []
        for r in result:
            contratos.append({
                "id": r[0],
                "codigo_contrato": r[1],
                "nome_empresa": r[2],
                "valor_orcado": float(r[3]) if r[3] else 0,  # CORRIGIDO: era valor_total
                "data_inicio": r[4].isoformat() if r[4] else None,
                "data_fim": r[5].isoformat() if r[5] else None
            })
        
        return jsonify(contratos)
        
    except Exception as e:
        log_error("listar_contratos", e)
        return jsonify({"error": "Erro ao listar contratos"}), 500

# ========================================================================
#   LISTAR CUSTOS - CORRIGIDO
# ========================================================================

@custos_bp.route("/", methods=["GET"])
@require_admin
def listar_custos():
    """Lista custos com filtros"""
    try:
        # Obter parâmetros
        veiculo_id = request.args.get("veiculo_id")
        contrato_id = request.args.get("contrato_id")
        tipo_custo = request.args.get("tipo_custo")
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        limite = int(request.args.get("limite", 100))

        query = """
            SELECT c.*, v.placa, v.modelo, v.marca,
                   co.codigo_contrato, co.nome_empresa
            FROM custos_veiculos c
            LEFT JOIN veiculos v ON c.veiculo_id = v.id
            LEFT JOIN contratos co ON c.contrato_id = co.id
            WHERE 1=1
        """

        params = []

        # Adicionar filtros
        if veiculo_id:
            query += " AND c.veiculo_id = %s"
            params.append(veiculo_id)

        if contrato_id:
            query += " AND c.contrato_id = %s"
            params.append(contrato_id)

        if tipo_custo:
            query += " AND c.tipo_custo = %s"
            params.append(tipo_custo)

        if data_inicio:
            query += " AND c.data >= %s"
            params.append(data_inicio)

        if data_fim:
            query += " AND c.data <= %s"
            params.append(data_fim)

        query += " ORDER BY c.data DESC, c.id DESC LIMIT %s"
        params.append(limite)

        result = execute_query(query, params, fetchall=True)

        custos = []
        storage = get_storage()
        for r in result:
            custo = {
                'id': r[0],
                'veiculo_id': r[1],
                'contrato_id': r[2],
                'tipo_custo': r[3],
                'descricao': r[4],
                'data': r[5].isoformat() if r[5] else None,
                'valor': float(r[6]) if r[6] else 0,
                'litros': float(r[7]) if r[7] else None,
                'preco_litro': float(r[8]) if r[8] else None,
                'km_atual': float(r[9]) if r[9] else None,
                'local': r[10],
                'fornecedor': r[11],
                'observacao': r[12],
                'comprovante': r[13],
                'comprovante_url': storage.get_url(r[13]) if r[13] else None,
                'criado_em': r[14].isoformat() if r[14] else None,
                'placa': r[15],
                'modelo': r[16],
                'marca': r[17],
                'codigo_contrato': r[18],
                'nome_empresa': r[19]
            }
            custos.append(custo)

        return jsonify(custos)

    except Exception as e:
        log_error("listar_custos", e)
        return jsonify({"error": "Erro ao listar custos"}), 500

# ========================================================================
#   CRIAR CUSTO
# ========================================================================

@custos_bp.route("/", methods=["POST"])
@require_admin
def criar_custo():
    """Cria um novo registro de custo"""
    try:
        # Verificar tipo de conteúdo
        if request.content_type and 'multipart/form-data' in request.content_type:
            dados = request.form.to_dict()
            arquivo = request.files.get("comprovante")
        else:
            dados = request.get_json() or {}
            arquivo = None

        # Validações obrigatórias
        if not dados.get("veiculo_id"):
            return jsonify({"error": "Veículo é obrigatório"}), 400

        if not dados.get("tipo_custo"):
            return jsonify({"error": "Tipo de custo é obrigatório"}), 400

        if not dados.get("data"):
            return jsonify({"error": "Data é obrigatória"}), 400

        valor = format_float(dados.get("valor"))
        if not valor or valor <= 0:
            return jsonify({"error": "Valor inválido ou não informado"}), 400

        # Validações específicas para abastecimento
        if dados.get("tipo_custo") == 'abastecimento':
            litros = format_float(dados.get("litros"))
            preco_litro = format_float(dados.get("preco_litro"))
            km_atual = format_float(dados.get("km_atual"))
            
            if not litros or litros <= 0:
                return jsonify({"error": "Litros é obrigatório para abastecimento"}), 400
            if not preco_litro or preco_litro <= 0:
                return jsonify({"error": "Preço por litro é obrigatório para abastecimento"}), 400
            if not km_atual or km_atual <= 0:
                return jsonify({"error": "KM atual é obrigatório para abastecimento"}), 400

        # Processar comprovante
        comprovante_url = None
        if arquivo:
            comprovante_url = save_uploaded_file(arquivo)

        query = """
            INSERT INTO custos_veiculos (
                veiculo_id, contrato_id, tipo_custo, descricao, data,
                valor, litros, preco_litro, km_atual, local,
                fornecedor, observacao, comprovante, criado_em
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """

        params = (
            dados.get("veiculo_id"),
            dados.get("contrato_id"),
            dados.get("tipo_custo"),
            dados.get("descricao", ""),
            dados.get("data"),
            valor,
            format_float(dados.get("litros")),
            format_float(dados.get("preco_litro")),
            format_float(dados.get("km_atual")),
            dados.get("local", ""),
            dados.get("fornecedor", ""),
            dados.get("observacao", ""),
            comprovante_url
        )

        result = execute_query(query, params, fetchone=True, commit=True)
        
        if result:
            return jsonify({
                "success": True,
                "id": result[0],
                "message": "Custo registrado com sucesso!"
            })
        else:
            return jsonify({"error": "Erro ao criar registro"}), 500

    except Exception as e:
        log_error("criar_custo", e)
        return jsonify({"error": "Erro ao criar custo", "details": str(e)}), 500

# ========================================================================
#   OBTER CUSTO ESPECÍFICO
# ========================================================================

@custos_bp.route("/<int:custo_id>", methods=["GET"])
@require_admin
def obter_custo(custo_id):
    """Obtém detalhes de um custo específico"""
    try:
        query = """
            SELECT c.*, v.placa, v.modelo, v.marca,
                   co.codigo_contrato, co.nome_empresa
            FROM custos_veiculos c
            LEFT JOIN veiculos v ON c.veiculo_id = v.id
            LEFT JOIN contratos co ON c.contrato_id = co.id
            WHERE c.id = %s
        """

        result = execute_query(query, (custo_id,), fetchone=True)
        
        if not result:
            return jsonify({"error": "Custo não encontrado"}), 404

        storage = get_storage()
        custo = {
            'id': result[0],
            'veiculo_id': result[1],
            'contrato_id': result[2],
            'tipo_custo': result[3],
            'descricao': result[4],
            'data': result[5].isoformat() if result[5] else None,
            'valor': float(result[6]) if result[6] else 0,
            'litros': float(result[7]) if result[7] else None,
            'preco_litro': float(result[8]) if result[8] else None,
            'km_atual': float(result[9]) if result[9] else None,
            'local': result[10],
            'fornecedor': result[11],
            'observacao': result[12],
            'comprovante': result[13],
            'comprovante_url': storage.get_url(result[13]) if result[13] else None,
            'criado_em': result[14].isoformat() if result[14] else None,
            'placa': result[15],
            'modelo': result[16],
            'marca': result[17],
            'codigo_contrato': result[18],
            'nome_empresa': result[19]
        }

        return jsonify(custo)

    except Exception as e:
        log_error("obter_custo", e)
        return jsonify({"error": "Erro ao buscar custo"}), 500

# ========================================================================
#   RESUMO DE CUSTOS
# ========================================================================

@custos_bp.route("/resumo", methods=["GET"])
@require_admin
def resumo_custos():
    """Retorna resumo estatístico dos custos"""
    try:
        veiculo_id = request.args.get("veiculo_id")
        contrato_id = request.args.get("contrato_id")
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")

        query = """
            SELECT 
                tipo_custo,
                COUNT(*) as total_registros,
                SUM(valor) as valor_total,
                AVG(valor) as valor_medio
            FROM custos_veiculos
            WHERE 1=1
        """
        params = []

        if veiculo_id:
            query += " AND veiculo_id = %s"
            params.append(veiculo_id)

        if contrato_id:
            query += " AND contrato_id = %s"
            params.append(contrato_id)

        if data_inicio:
            query += " AND data >= %s"
            params.append(data_inicio)

        if data_fim:
            query += " AND data <= %s"
            params.append(data_fim)

        query += " GROUP BY tipo_custo ORDER BY tipo_custo"

        result = execute_query(query, params, fetchall=True)

        resumo_tipos = []
        for r in result:
            resumo_tipos.append({
                'tipo_custo': r[0],
                'total_registros': r[1],
                'valor_total': float(r[2]) if r[2] else 0,
                'valor_medio': float(r[3]) if r[3] else 0
            })

        # Total geral
        query_total = """
            SELECT 
                COUNT(*) as total_custos,
                SUM(valor) as valor_total_geral,
                AVG(valor) as valor_medio_geral
            FROM custos_veiculos
            WHERE 1=1
        """
        
        if params:
            query_total += query.split('WHERE')[1]
        
        total_result = execute_query(query_total, params, fetchone=True)

        resumo = {
            'por_tipo': resumo_tipos,
            'totais_gerais': {
                'total_custos': total_result[0] if total_result[0] else 0,
                'valor_total_geral': float(total_result[1]) if total_result[1] else 0,
                'valor_medio_geral': float(total_result[2]) if total_result[2] else 0
            }
        }

        return jsonify(resumo)

    except Exception as e:
        log_error("resumo_custos", e)
        return jsonify({"error": "Erro ao gerar resumo"}), 500

# ========================================================================
#   CONSUMO MÉDIO POR VEÍCULO
# ========================================================================

@custos_bp.route("/consumo-medio", methods=["GET"])
@require_admin
def consumo_medio():
    """Calcula consumo médio por veículo"""
    try:
        query = """
            SELECT 
                v.id as veiculo_id,
                v.placa,
                v.modelo,
                COUNT(c.id) as total_abastecimentos,
                SUM(c.litros) as total_litros,
                SUM(c.valor) as total_gasto,
                MAX(c.km_atual) - MIN(c.km_atual) as km_percorridos,
                CASE 
                    WHEN SUM(c.litros) > 0 
                    THEN (MAX(c.km_atual) - MIN(c.km_atual)) / SUM(c.litros)
                    ELSE 0 
                END as consumo_medio
            FROM veiculos v
            LEFT JOIN custos_veiculos c ON v.id = c.veiculo_id 
                AND c.tipo_custo = 'abastecimento'
                AND c.litros IS NOT NULL 
                AND c.km_atual IS NOT NULL
            WHERE v.status = 'ativo'
            GROUP BY v.id, v.placa, v.modelo
            HAVING COUNT(c.id) >= 2
            ORDER BY v.placa
        """

        result = execute_query(query, fetchall=True)

        consumo = []
        for r in result:
            consumo.append({
                'veiculo_id': r[0],
                'placa': r[1],
                'modelo': r[2],
                'total_abastecimentos': r[3],
                'total_litros': float(r[4]) if r[4] else 0,
                'total_gasto': float(r[5]) if r[5] else 0,
                'km_percorridos': float(r[6]) if r[6] else 0,
                'consumo_medio': float(r[7]) if r[7] else 0
            })

        return jsonify(consumo)

    except Exception as e:
        log_error("consumo_medio", e)
        return jsonify({"error": "Erro ao calcular consumo médio"}), 500

# ========================================================================
#   SERVIR ARQUIVOS
# ========================================================================

@custos_bp.route("/uploads/<path:filename>")
@require_admin
def servir_arquivo(filename):
    """Serve arquivos de comprovantes (delegação ao storage)."""
    try:
        key = f"uploads/custos/{filename}"
        storage = get_storage()
        
        file_bytes = storage.open(key)
        return send_file(io.BytesIO(file_bytes), download_name=filename.split('/')[-1])
        
    except FileNotFoundError:
        log_error("servir_arquivo", f"Arquivo não encontrado com a chave: {key}")
        return jsonify({"error": "Arquivo não encontrado"}), 404
    except Exception as e:
        log_error("servir_arquivo", e)
        return jsonify({"error": "Erro ao servir o arquivo"}), 500

# ========================================================================
#   HEALTH CHECK
# ========================================================================

@custos_bp.route("/health")
def health():
    """Verifica se a API está funcionando"""
    try:
        # Testar conexão com banco
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected"
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ========================================================================
#   ENDPOINT DE DEBUG (remover em produção)
# ========================================================================

if os.environ.get("ENABLE_DEBUG_ROUTES") == "1":
    @custos_bp.route("/debug/estrutura", methods=["GET"])
    @require_admin
    def debug_estrutura():
        """Mostra estrutura das tabelas para debug"""
        try:
            # Estrutura de veiculos
            query_veiculos = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'veiculos'
                ORDER BY ordinal_position
            """
            cols_veiculos = execute_query(query_veiculos, fetchall=True)
            
            # Estrutura de contratos
            query_contratos = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'contratos'
                ORDER BY ordinal_position
            """
            cols_contratos = execute_query(query_contratos, fetchall=True)
            
            # Estrutura de custos_veiculos
            query_custos = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'custos_veiculos'
                ORDER BY ordinal_position
            """
            cols_custos = execute_query(query_custos, fetchall=True)
            
            return jsonify({
                "veiculos": [{"coluna": c[0], "tipo": c[1], "nulo": c[2]} for c in cols_veiculos],
                "contratos": [{"coluna": c[0], "tipo": c[1], "nulo": c[2]} for c in cols_contratos],
                "custos_veiculos": [{"coluna": c[0], "tipo": c[1], "nulo": c[2]} for c in cols_custos]
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500