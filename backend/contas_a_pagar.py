from flask import Blueprint, request, jsonify, send_from_directory, redirect, current_app, send_file
from core.database import get_conn
from core.storage import get_storage
import os
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, date
from decimal import Decimal
from functools import wraps
from flask_login import current_user
import io

bp_pagar = Blueprint("contas_pagar", __name__, url_prefix="/api/contas_pagar")

# ============================================================
# DECORADOR DE AUTENTICAÇÃO
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
# CONFIGURAÇÃO DE UPLOADS
# ============================================================

# Lista de categorias do frontend
CATEGORIAS = [
    "Alimentação", "Diárias de Campo", "Hospedagem", "Transporte Interno da Equipe",
    "Transporte Externo / Intermunicipal", "Pedágios", "Estacionamento", "Reembolso de Campo",
    "Locação de Veículos", "Transporte Terceirizado", "Logística Especial (4x4 / Embarcação)",
    "Combustível", "Troca de Óleo / Filtros", "Manutenção Preventiva", "Manutenção Corretiva",
    "Peças Mecânicas", "Pneus / Alinhamento", "Documentação de Veículos (IPVA / Licenciamento)",
    "Seguro de Veículos", "Rastreamento / Telemetria", "Calibração de Equipamentos",
    "Manutenção de Equipamentos", "Locação de Equipamentos", "Locação de Drone",
    "Acessórios Topográficos", "Softwares de Topografia", "Renovação de Licenças",
    "EPIs", "Reposição de EPIs", "Uniformes", "Treinamentos (NRs)", "ASO / Exames Ocupacionais",
    "Notebooks / Tablets", "Telefonia / Internet Móvel", "Servidores / Nuvem",
    "Certificado Digital", "Manutenção de TI", "Salários", "Encargos", "Benefícios",
    "Férias", "Rescisões", "Horas Extras", "Aluguel", "Energia", "Água", "Internet",
    "Material de Escritório", "Limpeza", "Impressões / Plotagens", "Contabilidade",
    "Impostos", "Taxas Bancárias", "ART / CREA", "Custos de Licitação", "Consultorias",
    "Terceirizados", "Serviços Especializados", "Marketing", "Seguro Empresarial",
    "Seguro de Equipamentos", "Outros"
]

def to_float(value):
    """Convert Decimal/None to float safely"""
    if value is None:
        return 0.0
    try:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(',', '.'))
            except:
                return 0.0
        return float(value)
    except (TypeError, ValueError, AttributeError):
        return 0.0

def serialize_pagar(row):
    """Serialize database row to JSON"""
    if not row:
        return None
    storage = get_storage()
    
    try:
        return {
            "id": row[0],
            "fornecedor": row[1] or "",
            "descricao": row[2] or "",
            "valor": to_float(row[3]),
            "vencimento": row[4].isoformat() if isinstance(row[4], (date, datetime)) else str(row[4]),
            "categoria": row[5] or "",
            "status": row[6] or "pendente",
            "comprovante": row[7] or "",
            "comprovante_nome": row[8] or "",
            "contrato_id": row[9],
            "criado_em": row[10].isoformat() if row[10] and isinstance(row[10], (date, datetime)) else str(row[10]) if row[10] else None,
            "comprovante_url": storage.get_url(row[7]) if row[7] else None
        }
    except Exception as e:
        print(f"Erro ao serializar linha: {e}, row: {row}")
        return None

# ============================================================
# ENDPOINT PARA LISTAR CATEGORIAS
# ============================================================

@bp_pagar.get("/categorias")
def listar_categorias():
    """Retorna a lista de categorias disponíveis"""
    return jsonify({
        "categorias": CATEGORIAS,
        "total": len(CATEGORIAS),
        "grupos": {
            "🏕️ Despesas de Campo e Operacionais": [
                "Alimentação", "Diárias de Campo", "Hospedagem", "Transporte Interno da Equipe",
                "Transporte Externo / Intermunicipal", "Pedágios", "Estacionamento", "Reembolso de Campo",
                "Locação de Veículos", "Transporte Terceirizado", "Logística Especial (4x4 / Embarcação)"
            ],
            "🚗 Veículos e Transporte": [
                "Combustível", "Troca de Óleo / Filtros", "Manutenção Preventiva", "Manutenção Corretiva",
                "Peças Mecânicas", "Pneus / Alinhamento", "Documentação de Veículos (IPVA / Licenciamento)",
                "Seguro de Veículos", "Rastreamento / Telemetria"
            ],
            "🔧 Equipamentos e Tecnologia": [
                "Calibração de Equipamentos", "Manutenção de Equipamentos", "Locação de Equipamentos",
                "Locação de Drone", "Acessórios Topográficos", "Softwares de Topografia", "Renovação de Licenças"
            ],
            "👥 Recursos Humanos": [
                "EPIs", "Reposição de EPIs", "Uniformes", "Treinamentos (NRs)", "ASO / Exames Ocupacionais"
            ],
            "💻 Tecnologia da Informação": [
                "Notebooks / Tablets", "Telefonia / Internet Móvel", "Servidores / Nuvem",
                "Certificado Digital", "Manutenção de TI"
            ],
            "💰 Folha de Pagamento": [
                "Salários", "Encargos", "Benefícios", "Férias", "Rescisões", "Horas Extras"
            ],
            "🏢 Escritório e Operações": [
                "Aluguel", "Energia", "Água", "Internet", "Material de Escritório",
                "Limpeza", "Impressões / Plotagens"
            ],
            "📋 Serviços e Impostos": [
                "Contabilidade", "Impostos", "Taxas Bancárias", "ART / CREA", "Custos de Licitação",
                "Consultorias", "Terceirizados", "Serviços Especializados"
            ],
            "📢 Marketing e Seguros": [
                "Marketing", "Seguro Empresarial", "Seguro de Equipamentos"
            ],
            "📦 Outros": [
                "Outros"
            ]
        }
    })

# ============================================================
# LISTAR CONTAS COM FILTROS AVANÇADOS
# ============================================================

@bp_pagar.get("/")
@require_admin
def listar():
    conn = get_conn()
    cur = conn.cursor()

    # Parâmetros de filtro
    contrato_id = request.args.get("contrato_id")
    status = request.args.get("status")
    categoria = request.args.get("categoria")
    fornecedor = request.args.get("fornecedor")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    
    # Construir query dinamicamente
    query = """
        SELECT * FROM contas_pagar 
        WHERE 1=1
    """
    params = []
    
    if contrato_id:
        query += " AND contrato_id = %s"
        params.append(contrato_id)
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    if categoria:
        query += " AND categoria = %s"
        params.append(categoria)
    
    if fornecedor:
        query += " AND fornecedor ILIKE %s"
        params.append(f"%{fornecedor}%")
    
    if data_inicio:
        query += " AND vencimento >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query += " AND vencimento <= %s"
        params.append(data_fim)
    
    query += " ORDER BY vencimento DESC, status"
    
    try:
        cur.execute(query, params)
        contas = []
        for row in cur.fetchall():
            conta = serialize_pagar(row)
            if conta:
                contas.append(conta)
        
        conn.close()
        return jsonify(contas)
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# OBTER ESTATÍSTICAS POR CATEGORIA
# ============================================================

@bp_pagar.get("/estatisticas/categorias")
@require_admin
def estatisticas_categorias():
    """Retorna estatísticas agrupadas por categoria"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Estatísticas por categoria
        query = """
            SELECT 
                COALESCE(categoria, 'Não categorizado') as categoria,
                COUNT(*) as quantidade,
                SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END) as pendente,
                SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END) as pago,
                SUM(valor) as total
            FROM contas_pagar
            GROUP BY categoria
            ORDER BY total DESC
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        categorias_stats = []
        for row in rows:
            categorias_stats.append({
                "categoria": row[0] or "Não categorizado",
                "quantidade": row[1] or 0,
                "pendente": to_float(row[2]),
                "pago": to_float(row[3]),
                "total": to_float(row[4])
            })
        
        # Totais gerais
        query_totais = """
            SELECT 
                COUNT(*) as total_contas,
                SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as total_pendentes,
                SUM(CASE WHEN status = 'pago' THEN 1 ELSE 0 END) as total_pagas,
                SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END) as valor_pendente,
                SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END) as valor_pago,
                SUM(valor) as valor_total
            FROM contas_pagar
        """
        
        cur.execute(query_totais)
        totais_row = cur.fetchone()
        
        totais = {
            "total_contas": totais_row[0] if totais_row else 0,
            "total_pendentes": totais_row[1] if totais_row else 0,
            "total_pagas": totais_row[2] if totais_row else 0,
            "valor_pendente": to_float(totais_row[3]) if totais_row else 0,
            "valor_pago": to_float(totais_row[4]) if totais_row else 0,
            "valor_total": to_float(totais_row[5]) if totais_row else 0
        }
        
        conn.close()
        
        return jsonify({
            "categorias": categorias_stats,
            "totais": totais,
            "categorias_disponiveis": CATEGORIAS
        })
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# OBTER UMA CONTA ESPECÍFICA (PARA EDIÇÃO)
# ============================================================

@bp_pagar.get("/<int:id>")
@require_admin
def obter_conta(id):
    """Retorna uma conta específica para edição"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT * FROM contas_pagar WHERE id = %s", (id,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"error": "Conta não encontrada"}), 404
        
        conta = serialize_pagar(row)
        
        # Adicionar informações do contrato se existir
        if conta["contrato_id"]:
            cur.execute("SELECT codigo_contrato, nome_empresa FROM contratos WHERE id = %s", 
                       (conta["contrato_id"],))
            contrato_row = cur.fetchone()
            if contrato_row:
                conta["contrato_info"] = {
                    "codigo": contrato_row[0] or "",
                    "empresa": contrato_row[1] or ""
                }
        
        conn.close()
        return jsonify(conta)
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# CRIAR NOVA CONTA
# ============================================================

@bp_pagar.post("/")
@require_admin
def criar():
    try:
        file = request.files.get('comprovante')
        comprovante_nome_salvo = None
        comprovante_nome_original = None
        storage = get_storage()

        if file and file.filename:
            comprovante_nome_original = secure_filename(file.filename)
            comprovante_nome_salvo = storage.save(file, subdir='contas_pagar')

        conn = get_conn()
        cur = conn.cursor()

        fornecedor = request.form.get('fornecedor')
        descricao = request.form.get('descricao')
        valor = request.form.get('valor')
        vencimento = request.form.get('vencimento')
        categoria = request.form.get('categoria')
        status = request.form.get('status', 'pendente')
        contrato_id = request.form.get('contrato_id')

        # Validações
        if not fornecedor or not fornecedor.strip():
            return jsonify({"error": "Fornecedor é obrigatório"}), 400
        
        if not valor:
            return jsonify({"error": "Valor é obrigatório"}), 400
            
        if not vencimento:
            return jsonify({"error": "Vencimento é obrigatório"}), 400

        cur.execute("""
            INSERT INTO contas_pagar (
                fornecedor, descricao, valor, vencimento,
                categoria, status, comprovante, comprovante_nome, contrato_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            fornecedor.strip(),
            descricao.strip() if descricao else "",
            float(valor) if valor else 0,
            vencimento,
            categoria.strip() if categoria else "",
            status,
            comprovante_nome_salvo,
            comprovante_nome_original,
            contrato_id if contrato_id and contrato_id != 'undefined' else None
        ))

        novo_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify({
            "id": novo_id, 
            "message": "Conta criada com sucesso!",
            "categoria": categoria,
            "comprovante_url": storage.get_url(comprovante_nome_salvo) if comprovante_nome_salvo else None
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ATUALIZAR CONTA
# ============================================================

@bp_pagar.put("/<int:id>")
@require_admin
def atualizar(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Verificar se conta existe
        cur.execute("SELECT comprovante FROM contas_pagar WHERE id = %s", (id,))
        atual = cur.fetchone()
        if not atual:
            conn.close()
            return jsonify({"error": "Conta não encontrada"}), 404
            
        comprovante_atual = atual[0] if atual else None

        file = request.files.get('comprovante')
        comprovante_nome_salvo = comprovante_atual
        comprovante_nome_original = request.form.get('comprovante_nome')

        storage = get_storage()

        # novo upload
        if file and file.filename:
            # Remover arquivo antigo via storage
            if comprovante_atual:
                try:
                    storage.delete(comprovante_atual)
                except Exception:
                    pass

            comprovante_nome_original = secure_filename(file.filename)
            comprovante_nome_salvo = storage.save(file, subdir='contas_pagar')

        fornecedor = request.form.get('fornecedor')
        descricao = request.form.get('descricao')
        valor = request.form.get('valor')
        vencimento = request.form.get('vencimento')
        categoria = request.form.get('categoria')
        status = request.form.get('status')
        contrato_id = request.form.get('contrato_id')

        # Validações
        if not fornecedor or not fornecedor.strip():
            conn.close()
            return jsonify({"error": "Fornecedor é obrigatório"}), 400
        
        if not valor:
            conn.close()
            return jsonify({"error": "Valor é obrigatório"}), 400
            
        if not vencimento:
            conn.close()
            return jsonify({"error": "Vencimento é obrigatório"}), 400

        cur.execute("""
            UPDATE contas_pagar
            SET fornecedor=%s, descricao=%s, valor=%s, vencimento=%s,
                categoria=%s, status=%s, comprovante=%s, comprovante_nome=%s,
                contrato_id=%s, updated_at=NOW()
            WHERE id=%s
        """, (
            fornecedor.strip(),
            descricao.strip() if descricao else "",
            float(valor) if valor else 0,
            vencimento,
            categoria.strip() if categoria else "",
            status,
            comprovante_nome_salvo,
            comprovante_nome_original,
            contrato_id if contrato_id and contrato_id != 'undefined' else None,
            id
        ))

        conn.commit()
        conn.close()

        return jsonify({"message": "Conta atualizada com sucesso!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# DOWNLOAD DE COMPROVANTE
# ============================================================

@bp_pagar.get("/download/<int:id>")
@require_admin
def download_comprovante(id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT comprovante, comprovante_nome FROM contas_pagar WHERE id=%s", (id,))
    r = cur.fetchone()
    conn.close()

    if not r or not r[0]:
        return jsonify({"error": "Comprovante não encontrado"}), 404

    key = r[0]
    nome_arquivo = r[1] or "comprovante"
    storage = get_storage()
    
    try:
        file_bytes = storage.open(key)
        return send_file(
            io.BytesIO(file_bytes),
            as_attachment=True,
            download_name=nome_arquivo
        )
    except FileNotFoundError:
        return jsonify({"erro": "Arquivo não encontrado no storage."}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ============================================================
# DELETAR CONTA
# ============================================================

@bp_pagar.delete("/<int:id>")
@require_admin
def excluir(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Verificar se conta existe
        cur.execute("SELECT id, comprovante FROM contas_pagar WHERE id=%s", (id,))
        r = cur.fetchone()
        
        if not r:
            conn.close()
            return jsonify({"error": "Conta não encontrada"}), 404

        # Remover arquivo físico se existir
        if r[1]:  # comprovante key
            try:
                storage = get_storage()
                storage.delete(r[1])
            except Exception:
                pass

        cur.execute("DELETE FROM contas_pagar WHERE id=%s", (id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Conta excluída com sucesso!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ENDPOINT PARA RESUMO DASHBOARD
# ============================================================

@bp_pagar.get("/dashboard/resumo")
@require_admin
def dashboard_resumo():
    """Retorna resumo para dashboard"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Contas vencidas
        cur.execute("""
            SELECT COUNT(*), SUM(valor)
            FROM contas_pagar 
            WHERE status = 'pendente' 
            AND vencimento < CURRENT_DATE
        """)
        vencidas_row = cur.fetchone()
        
        # Contas a vencer (7 dias)
        cur.execute("""
            SELECT COUNT(*), SUM(valor)
            FROM contas_pagar 
            WHERE status = 'pendente' 
            AND vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)
        vencer_7dias_row = cur.fetchone()
        
        # Total por status
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as quantidade,
                SUM(valor) as valor_total
            FROM contas_pagar
            GROUP BY status
        """)
        status_rows = cur.fetchall()
        
        # Top 5 categorias
        cur.execute("""
            SELECT 
                COALESCE(categoria, 'Não categorizado') as categoria,
                COUNT(*) as quantidade,
                SUM(valor) as valor_total
            FROM contas_pagar
            WHERE status = 'pendente'
            GROUP BY categoria
            ORDER BY valor_total DESC
            LIMIT 5
        """)
        top_categorias = cur.fetchall()
        
        resumo = {
            "vencidas": {
                "quantidade": vencidas_row[0] if vencidas_row else 0,
                "valor": to_float(vencidas_row[1]) if vencidas_row else 0
            },
            "vencer_7dias": {
                "quantidade": vencer_7dias_row[0] if vencer_7dias_row else 0,
                "valor": to_float(vencer_7dias_row[1]) if vencer_7dias_row else 0
            },
            "por_status": [],
            "top_categorias": []
        }
        
        for row in status_rows:
            resumo["por_status"].append({
                "status": row[0],
                "quantidade": row[1],
                "valor": to_float(row[2])
            })
        
        for row in top_categorias:
            resumo["top_categorias"].append({
                "categoria": row[0],
                "quantidade": row[1],
                "valor": to_float(row[2])
            })
        
        conn.close()
        return jsonify(resumo)
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# ============================================================
# ENDPOINT PARA MARCAR COMO PAGO
# ============================================================

@bp_pagar.post("/<int:id>/pagar")
@require_admin
def marcar_como_pago(id):
    """Marca uma conta como paga"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE contas_pagar 
            SET status = 'pago', updated_at = NOW()
            WHERE id = %s
            RETURNING id
        """, (id,))
        
        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": "Conta não encontrada"}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({"message": "Conta marcada como paga!"}), 200
        
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500