# documentos_backend_final.py

from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import io
from functools import wraps
import logging
import traceback
from flask_login import login_required, current_user
from core.storage import get_storage
from core.auth import admin_required


# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp_documentos = Blueprint("documentos", __name__, url_prefix="/api/documentos")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'xlsm',
    'jpg', 'jpeg', 'png', 'gif', 'txt', 'csv',
    'ppt', 'pptx', 'zip', 'rar', '7z'
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

CATEGORIAS_VALIDAS = [
    'contrato', 'fiscal', 'rh', 'tecnico', 
    'comercial', 'operacional', 'juridico',
    'financeiro', 'marketing', 'outro'
]

STATUS_VALIDOS = ['ativo', 'vencido', 'pendente', 'arquivado']

# ============================================================
# UTILITÁRIOS
# ============================================================
def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida"""
    if not filename:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    """Valida o tamanho do arquivo"""
    if not file:
        return True
    
    file.seek(0, 2)  # Ir para o final
    size = file.tell()  # Obter tamanho
    file.seek(0)  # Voltar para o início
    
    if size > MAX_FILE_SIZE:
        return False
    return True

def get_file_icon(filename):
    """Retorna o ícone baseado no tipo de arquivo"""
    if not filename:
        return 'file'
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    icon_map = {
        'pdf': 'file-pdf',
        'doc': 'file-word',
        'docx': 'file-word',
        'xls': 'file-excel',
        'xlsx': 'file-excel',
        'xlsm': 'file-excel',
        'jpg': 'file-image',
        'jpeg': 'file-image',
        'png': 'file-image',
        'gif': 'file-image',
        'txt': 'file-alt',
        'csv': 'file-csv',
        'ppt': 'file-powerpoint',
        'pptx': 'file-powerpoint',
        'zip': 'file-archive',
        'rar': 'file-archive',
        '7z': 'file-archive'
    }
    
    return icon_map.get(ext, 'file')

def validate_document_data(data, is_update=False):
    """Valida os dados do documento"""
    errors = []
    
    # Nome obrigatório para criação
    if not is_update and not data.get('nome', '').strip():
        errors.append("Nome do documento é obrigatório")
    
    nome = data.get('nome', '').strip()
    if nome and len(nome) > 200:
        errors.append("Nome muito longo (máx. 200 caracteres)")
    
    # Categoria
    categoria = data.get('categoria', '').strip()
    if categoria and categoria not in CATEGORIAS_VALIDAS:
        errors.append(f"Categoria inválida. Opções: {', '.join(CATEGORIAS_VALIDAS)}")
    
    # Status
    status = data.get('status', '').strip()
    if status and status not in STATUS_VALIDOS:
        errors.append(f"Status inválido. Opções: {', '.join(STATUS_VALIDOS)}")
    
    # Validade (se fornecida)
    validade = data.get('validade')
    if validade:
        try:
            datetime.strptime(validade, '%Y-%m-%d')
        except ValueError:
            errors.append("Data de validade inválida. Use o formato YYYY-MM-DD")
    
    # Observações
    observacoes = data.get('observacoes', '').strip()
    if len(observacoes) > 1000:
        errors.append("Observações muito longas (máx. 1000 caracteres)")
    
    return errors

def get_column_names(conn, table_name='documentos'):
    """Obtém os nomes das colunas da tabela"""
    cur = conn.cursor()
    cur.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s 
        ORDER BY ordinal_position
    """, (table_name,))
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns

# ============================================================
# SERIALIZADOR DINÂMICO
# ============================================================
def serialize_documento(row, columns):
    """Serializa uma linha do banco para dicionário de forma dinâmica"""
    if not row or not columns:
        return None
    
    doc_dict = dict(zip(columns, row))
    
    # Processar campos especiais
    arquivo_nome = doc_dict.get('arquivo')
    storage = get_storage()
    arquivo_icon = get_file_icon(arquivo_nome) if arquivo_nome else None
    
    # Determinar status baseado na validade se necessário
    status = doc_dict.get('status', 'ativo')
    validade = doc_dict.get('validade')
    
    if validade and status != 'arquivado':
        try:
            if isinstance(validade, datetime):
                data_validade = validade.date()
            elif isinstance(validade, str):
                data_validade = datetime.strptime(validade, '%Y-%m-%d').date()
            else:
                data_validade = validade
            
            hoje = datetime.now().date()
            if hasattr(data_validade, 'date'):
                data_validade = data_validade.date()
            
            if data_validade < hoje:
                status = 'vencido'
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Erro ao processar data de validade: {e}")
    
    # Formatar datas
    resultado = {
        "id": doc_dict.get('id'),
        "nome": doc_dict.get('nome'),
        "categoria": doc_dict.get('categoria'),
        "validade": doc_dict.get('validade').strftime('%Y-%m-%d') if doc_dict.get('validade') else None,
        "arquivo": arquivo_nome,
        "arquivo_url": storage.get_url(arquivo_nome) if arquivo_nome else None,
        "arquivo_icon": arquivo_icon,
        "tipo_origem": doc_dict.get('tipo_origem'),
        "origem_id": doc_dict.get('origem_id'),
        "observacoes": doc_dict.get('observacoes'),
        "criado_em": doc_dict.get('criado_em').strftime('%Y-%m-%d %H:%M:%S') if doc_dict.get('criado_em') else None,
        "status": status,
        "atualizado_em": doc_dict.get('atualizado_em').strftime('%Y-%m-%d %H:%M:%S') if doc_dict.get('atualizado_em') else None,
        "tamanho_arquivo": doc_dict.get('tamanho_arquivo'),
        "usuario_id": doc_dict.get('usuario_id')
    }
    
    return resultado

# ============================================================
# MIDDLEWARE DE CONEXÃO
# ============================================================
def with_db_connection(func):
    """Decorator para gerenciar conexões com o banco de dados"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        from core.database import get_conn
        conn = None
        try:
            conn = get_conn()
            return func(conn, *args, **kwargs)
        except Exception as e:
            logger.error(f"Database error: {e}\n{traceback.format_exc()}")
            if conn:
                conn.rollback()
            return jsonify({"erro": f"Erro de banco de dados: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()
    return wrapper

# ============================================================
# ROTAS DA API
# ============================================================
@bp_documentos.get("/")
@login_required
@with_db_connection
def listar_documentos(conn):
    """Lista documentos com filtros"""
    try:
        # Obter parâmetros de filtro
        categoria = request.args.get("categoria")
        status_filter = request.args.get("status")
        tipo_origem = request.args.get("tipo_origem")
        origem_id = request.args.get("origem_id")
        busca = request.args.get("q")
        
        # Paginação
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        offset = (page - 1) * per_page
        
        # Construir query base
        query_base = """
            SELECT {columns}
            FROM documentos d
            WHERE 1=1
        """
        
        count_query = """
            SELECT COUNT(*) as total_count
            FROM documentos d
            WHERE 1=1
        """
        
        where_conditions = []
        params = []
        
        if categoria:
            where_conditions.append("AND d.categoria = %s")
            params.append(categoria)
        
        if status_filter:
            if status_filter == 'vencido':
                where_conditions.append("AND (d.validade < CURRENT_DATE OR d.status = 'vencido')")
            elif status_filter == 'ativo':
                where_conditions.append("AND (d.validade >= CURRENT_DATE OR d.validade IS NULL) AND d.status = 'ativo'")
            else:
                where_conditions.append("AND d.status = %s")
                params.append(status_filter)
        
        if tipo_origem:
            where_conditions.append("AND d.tipo_origem = %s")
            params.append(tipo_origem)
        
        if origem_id:
            where_conditions.append("AND d.origem_id = %s")
            params.append(origem_id)
        
        if busca:
            where_conditions.append("AND (d.nome ILIKE %s OR d.observacoes ILIKE %s)")
            params.extend([f"%{busca}%", f"%{busca}%"])
        
        # Obter colunas da tabela
        columns = get_column_names(conn)
        columns_str = ", ".join([f"d.{col}" for col in columns])
        
        # Query para contagem total
        count_params = params.copy()
        count_query += " ".join(where_conditions)
        
        cur = conn.cursor()
        cur.execute(count_query, count_params)
        total_count = cur.fetchone()[0]
        
        # Query para dados com paginação
        query = query_base.format(columns=columns_str)
        query += " ".join(where_conditions)
        query += " ORDER BY d.criado_em DESC LIMIT %s OFFSET %s"
        
        params.extend([per_page, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Serializar resultados
        documentos = []
        for row in rows:
            documentos.append(serialize_documento(row, columns))
        
        # Estatísticas
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'ativo' THEN 1 END) as ativos,
                COUNT(CASE WHEN status = 'pendente' THEN 1 END) as pendentes,
                COUNT(CASE WHEN status = 'vencido' OR (validade IS NOT NULL AND validade < CURRENT_DATE) THEN 1 END) as vencidos
            FROM documentos
        """)
        stats = cur.fetchone()
        
        return jsonify({
            "success": True,
            "documentos": documentos,
            "paginacao": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page if per_page > 0 else 0
            },
            "estatisticas": {
                "total": stats[0] if stats else 0,
                "ativos": stats[1] if stats else 0,
                "pendentes": stats[2] if stats else 0,
                "vencidos": stats[3] if stats else 0
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar documentos: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": "Erro interno do servidor ao listar documentos"
        }), 500

@bp_documentos.get("/<int:id>")
@login_required
@with_db_connection
def obter_documento(conn, id):
    """Obtém um documento específico"""
    try:
        columns = get_column_names(conn)
        columns_str = ", ".join(columns)
        
        cur = conn.cursor()
        cur.execute(f"SELECT {columns_str} FROM documentos WHERE id = %s", (id,))
        row = cur.fetchone()
        
        if not row:
            return jsonify({
                "success": False,
                "erro": "Documento não encontrado"
            }), 404
        
        documento = serialize_documento(row, columns)
        
        return jsonify({
            "success": True,
            "documento": documento
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter documento {id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": "Erro interno do servidor ao obter documento"
        }), 500

@bp_documentos.post("/")
def criar_documento():
    """Cria um novo documento"""
    try:
        logger.info(f"Criar documento - Headers: {dict(request.headers)}")
        
        # Processar arquivo
        file = request.files.get("arquivo")
        arquivo_path = None
        arquivo_size = 0
        
        if file and file.filename:
            # Validar arquivo
            if not allowed_file(file.filename):
                return jsonify({
                    "success": False,
                    "erro": "Tipo de arquivo não permitido"
                }), 400
            
            if not validate_file_size(file):
                return jsonify({
                    "success": False,
                    "erro": f"Arquivo muito grande. Tamanho máximo: {MAX_FILE_SIZE/(1024*1024)}MB"
                }), 400
            
            # Salvar arquivo
            storage = get_storage()
            arquivo_path = storage.save(file, subdir='documentos')
            
            # Obter tamanho do arquivo
            file.seek(0, 2)
            arquivo_size = file.tell()
        
        # Obter dados
        data = {}
        if request.form:
            data = request.form.to_dict()
        elif request.is_json:
            data = request.get_json()
        
        # Validação dos dados
        validation_errors = validate_document_data(data, is_update=False)
        if validation_errors:
            return jsonify({
                "success": False,
                "erro": validation_errors[0]
            }), 400
        
        # Inserir no banco
        from core.database import get_conn
        conn = get_conn()
        columns = get_column_names(conn)
        
        # Preparar dados para inserção
        insert_data = {
            'nome': data.get('nome', '').strip(),
            'categoria': data.get('categoria', '').strip() or 'outro',
            'validade': data.get('validade') or None,
            'arquivo': arquivo_path,
            'tipo_origem': data.get('tipo_origem'),
            'origem_id': data.get('origem_id'),
            'observacoes': data.get('observacoes', '').strip(),
            'status': data.get('status', 'ativo').strip(),
            'tamanho_arquivo': arquivo_size,
            'usuario_id': data.get('usuario_id'),
            'criado_em': 'NOW()'  # Será processado pelo banco
        }
        
        # Remover None values e preparar query
        filtered_data = {k: v for k, v in insert_data.items() if v is not None and k in columns}
        
        columns_insert = [col for col in filtered_data.keys() if col != 'criado_em']
        placeholders = ['%s' for _ in columns_insert]
        values = [filtered_data[col] for col in columns_insert]
        
        # Se criado_em não estiver nas colunas, adicionar manualmente
        if 'criado_em' in columns:
            columns_insert.append('criado_em')
            placeholders.append('NOW()')
        
        query = f"""
            INSERT INTO documentos ({', '.join(columns_insert)})
            VALUES ({', '.join(placeholders)})
            RETURNING id
        """
        
        cur = conn.cursor()
        cur.execute(query, values if values else None)
        novo_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        
        logger.info(f"Documento criado com sucesso: ID {novo_id}")
        
        return jsonify({
            "success": True,
            "id": novo_id,
            "mensagem": "Documento criado com sucesso!",
            "arquivo_url": storage.get_url(arquivo_path) if arquivo_path else None
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao criar documento: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": f"Erro ao criar documento: {str(e)}"
        }), 500

@bp_documentos.put("/<int:id>")
@bp_documentos.patch("/<int:id>")
def atualizar_documento(id):
    """Atualiza um documento existente"""
    try:
        logger.info(f"Atualizar documento {id}")
        
        # Verificar se o documento existe
        from core.database import get_conn
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT arquivo, tamanho_arquivo FROM documentos WHERE id = %s", (id,))
        documento_atual = cur.fetchone()
        
        if not documento_atual:
            conn.close()
            return jsonify({
                "success": False,
                "erro": "Documento não encontrado"
            }), 404
        
        arquivo_atual = documento_atual[0]
        tamanho_atual = documento_atual[1] or 0
        
        # Processar novo arquivo
        file = request.files.get("arquivo")
        novo_arquivo_path = arquivo_atual
        novo_tamanho = tamanho_atual
        
        if file and file.filename:
            # Validar arquivo
            if not allowed_file(file.filename):
                conn.close()
                return jsonify({
                    "success": False,
                    "erro": "Tipo de arquivo não permitido"
                }), 400
            
            if not validate_file_size(file):
                conn.close()
                return jsonify({
                    "success": False,
                    "erro": f"Arquivo muito grande. Tamanho máximo: {MAX_FILE_SIZE/(1024*1024)}MB"
                }), 400
            
            # Remover arquivo antigo se existir
            if arquivo_atual:
                storage = get_storage()
                try:
                    storage.delete(arquivo_atual)
                    logger.info(f"Arquivo antigo removido: {arquivo_atual}")
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo antigo: {e}")
            
            # Salvar novo arquivo
            storage = get_storage()
            novo_arquivo_path = storage.save(file, subdir='documentos')
            
            # Obter tamanho do novo arquivo
            file.seek(0, 2)
            novo_tamanho = file.tell()
        
        # Obter dados
        data = {}
        if request.form:
            data = request.form.to_dict()
        elif request.is_json:
            data = request.get_json()
        
        # Validação dos dados
        validation_errors = validate_document_data(data, is_update=True)
        if validation_errors:
            conn.close()
            return jsonify({
                "success": False,
                "erro": validation_errors[0]
            }), 400
        
        # Preparar dados para atualização
        update_data = {}
        
        # Campos que sempre podem ser atualizados
        if 'nome' in data:
            update_data['nome'] = data.get('nome', '').strip()
        if 'categoria' in data:
            update_data['categoria'] = data.get('categoria', '').strip() or 'outro'
        if 'validade' in data:
            update_data['validade'] = data.get('validade') or None
        if 'observacoes' in data:
            update_data['observacoes'] = data.get('observacoes', '').strip()
        if 'status' in data:
            update_data['status'] = data.get('status', 'ativo').strip()
        
        # Campos condicionais
        if novo_arquivo_path != arquivo_atual:
            update_data['arquivo'] = novo_arquivo_path
            update_data['tamanho_arquivo'] = novo_tamanho
        
        if 'tipo_origem' in data:
            update_data['tipo_origem'] = data.get('tipo_origem')
        if 'origem_id' in data:
            update_data['origem_id'] = data.get('origem_id')
        if 'usuario_id' in data:
            update_data['usuario_id'] = data.get('usuario_id')
        
        if not update_data:
            conn.close()
            return jsonify({
                "success": False,
                "erro": "Nenhum dado fornecido para atualização"
            }), 400
        
        # Construir query de atualização
        set_clauses = []
        values = []
        
        for key, value in update_data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
        
        values.append(id)
        
        query = f"""
            UPDATE documentos
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING id
        """
        
        cur.execute(query, values)
        updated = cur.fetchone()
        
        if not updated:
            conn.rollback()
            conn.close()
            return jsonify({
                "success": False,
                "erro": "Documento não encontrado para atualização"
            }), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"Documento {id} atualizado com sucesso")
        
        return jsonify({
            "success": True,
            "id": id,
            "mensagem": "Documento atualizado com sucesso!"
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao atualizar documento {id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": f"Erro ao atualizar documento: {str(e)}"
        }), 500

@bp_documentos.delete("/<int:id>")
@with_db_connection
def deletar_documento(conn, id):
    """Exclui um documento"""
    try:
        cur = conn.cursor()
        
        # Obter informações do documento
        cur.execute("SELECT arquivo, nome FROM documentos WHERE id = %s", (id,))
        documento = cur.fetchone()
        
        if not documento:
            return jsonify({
                "success": False,
                "erro": "Documento não encontrado"
            }), 404
        
        arquivo_path, nome_documento = documento
        
        # Remover arquivo físico se existir
        if arquivo_path:
            try:
                storage = get_storage()
                storage.delete(arquivo_path)
                logger.info(f"Arquivo removido: {arquivo_path}")
            except Exception as e:
                logger.warning(f"Não foi possível remover arquivo físico: {e}")
        
        # Excluir do banco
        cur.execute("DELETE FROM documentos WHERE id = %s RETURNING id", (id,))
        deleted_id = cur.fetchone()
        
        if not deleted_id:
            return jsonify({
                "success": False,
                "erro": "Documento não encontrado"
            }), 404
        
        conn.commit()
        
        logger.info(f"Documento {id} excluído com sucesso")
        
        return jsonify({
            "success": True,
            "mensagem": f"Documento '{nome_documento}' excluído com sucesso!",
            "id": deleted_id[0]
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao excluir documento {id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": "Erro interno do servidor ao excluir documento"
        }), 500

@bp_documentos.get("/<int:id>/download")
@with_db_connection
def download_documento(conn, id):
    """Download do arquivo do documento"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT arquivo, nome FROM documentos WHERE id = %s", (id,))
        row = cur.fetchone()
        
        if not row or not row[0]:
            return jsonify({
                "success": False,
                "erro": "Arquivo não encontrado"
            }), 404
        
        arquivo_key, nome_documento = row
        
        storage = get_storage()
        
        try:
            file_bytes = storage.open(arquivo_key)
            
            # Determinar nome do arquivo para download
            if '.' in arquivo_key:
                nome_arquivo = arquivo_key.split('/')[-1]
            else:
                nome_arquivo = f"{nome_documento}.{arquivo_key.split('.')[-1] if '.' in arquivo_key else 'bin'}"
            
            nome_arquivo = secure_filename(nome_arquivo)
            
            return send_file(
                io.BytesIO(file_bytes),
                as_attachment=True,
                download_name=nome_arquivo,
                mimetype='application/octet-stream'
            )
            
        except FileNotFoundError:
            logger.error(f"Arquivo não encontrado no storage: {arquivo_key}")
            return jsonify({
                "success": False,
                "erro": "Arquivo não encontrado no sistema de arquivos"
            }), 404
        except Exception as e:
            logger.error(f"Erro ao baixar arquivo {id}: {e}\n{traceback.format_exc()}")
            return jsonify({
                "success": False,
                "erro": "Erro ao processar arquivo"
            }), 500
            
    except Exception as e:
        logger.error(f"Erro no download do documento {id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": "Erro interno do servidor ao baixar documento"
        }), 500

# ============================================================
# ROTAS AUXILIARES
# ============================================================
@bp_documentos.get("/categorias")
def listar_categorias():
    """Lista todas as categorias disponíveis"""
    return jsonify({
        "success": True,
        "categorias": CATEGORIAS_VALIDAS,
        "status": STATUS_VALIDOS,
        "extensoes_permitidas": list(ALLOWED_EXTENSIONS),
        "tamanho_maximo_mb": MAX_FILE_SIZE / (1024 * 1024)
    })

@bp_documentos.get("/estatisticas")
@with_db_connection
def estatisticas_documentos(conn):
    """Estatísticas gerais dos documentos"""
    try:
        cur = conn.cursor()
        
        # Verificar se a coluna tamanho_arquivo existe
        columns = get_column_names(conn)
        tamanho_column = "tamanho_arquivo" if "tamanho_arquivo" in columns else "0"
        
        # Estatísticas por categoria
        query = f"""
            SELECT 
                categoria,
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'ativo' THEN 1 END) as ativos,
                COUNT(CASE WHEN status = 'vencido' OR (validade IS NOT NULL AND validade < CURRENT_DATE) THEN 1 END) as vencidos,
                COUNT(CASE WHEN status = 'pendente' THEN 1 END) as pendentes,
                SUM({tamanho_column}) as tamanho_total
            FROM documentos
            GROUP BY categoria
            ORDER BY total DESC
        """
        
        cur.execute(query)
        
        categorias_stats = []
        for row in cur.fetchall():
            categorias_stats.append({
                "categoria": row[0],
                "total": row[1],
                "ativos": row[2],
                "vencidos": row[3],
                "pendentes": row[4],
                "tamanho_total": row[5] or 0,
                "tamanho_total_mb": round((row[5] or 0) / (1024 * 1024), 2)
            })
        
        # Documentos próximos do vencimento
        cur.execute("""
            SELECT id, nome, categoria, validade, status
            FROM documentos
            WHERE validade BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
                AND status NOT IN ('vencido', 'arquivado')
            ORDER BY validade ASC
            LIMIT 10
        """)
        
        proximos_vencimentos = []
        for row in cur.fetchall():
            proximos_vencimentos.append({
                "id": row[0],
                "nome": row[1],
                "categoria": row[2],
                "validade": row[3].strftime('%Y-%m-%d') if row[3] else None,
                "status": row[4],
                "dias_para_vencer": (row[3] - datetime.now().date()).days if row[3] else None
            })
        
        return jsonify({
            "success": True,
            "categorias": categorias_stats,
            "proximos_vencimentos": proximos_vencimentos,
            "total_categorias": len(categorias_stats)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": "Erro interno do servidor ao obter estatísticas"
        }), 500

@bp_documentos.get("/health")
@with_db_connection
def health_check(conn):
    """Verifica a saúde do serviço de documentos"""
    try:
        cur = conn.cursor()
        
        # Verificar conexão com banco
        cur.execute("SELECT 1")
        db_ok = cur.fetchone()[0] == 1
        
        # Contar documentos
        cur.execute("SELECT COUNT(*) FROM documentos")
        total_documentos = cur.fetchone()[0]
        
        # Verificar storage
        try:
            storage = get_storage()
            storage_ok = storage is not None
        except:
            storage_ok = False
        
        return jsonify({
            "success": True,
            "status": "healthy",
            "database": "connected" if db_ok else "disconnected",
            "storage": "available" if storage_ok else "unavailable",
            "total_documentos": total_documentos,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "erro": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ============================================================
# ROTA DE TESTE SIMPLES
# ============================================================
@bp_documentos.get("/test")
def test_route():
    """Rota de teste simples"""
    return jsonify({
        "success": True,
        "mensagem": "API de Documentos funcionando",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

# ============================================================
# ROTA PARA VERIFICAR ESTRUTURA DA TABELA
# ============================================================
@bp_documentos.get("/tabela/info")
@with_db_connection
def tabela_info(conn):
    """Retorna informações sobre a estrutura da tabela"""
    try:
        cur = conn.cursor()
        
        # Obter informações das colunas
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = 'documentos'
            ORDER BY ordinal_position
        """)
        
        columns_info = []
        for row in cur.fetchall():
            columns_info.append({
                "nome": row[0],
                "tipo": row[1],
                "nulo": row[2] == 'YES',
                "padrao": row[3]
            })
        
        # Obter constraints
        cur.execute("""
            SELECT 
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'documentos'
        """)
        
        constraints = []
        for row in cur.fetchall():
            constraints.append({
                "nome": row[0],
                "tipo": row[1],
                "coluna": row[2]
            })
        
        return jsonify({
            "success": True,
            "tabela": "documentos",
            "colunas": columns_info,
            "constraints": constraints,
            "total_colunas": len(columns_info)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter info da tabela: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "erro": str(e)
        }), 500