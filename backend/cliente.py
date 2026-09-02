# clientes.py - VERSÃO SEM JWT
# ============================================================
#  PATAGONIA • Backend de Clientes
# ============================================================

from flask import Blueprint, request, jsonify, render_template
from core.database import get_conn
import traceback
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

clientes_pages_bp = Blueprint('clientes_pages', __name__, template_folder='templates')
clientes_bp = Blueprint("clientes_bp", __name__, url_prefix="/api/clientes")


def row_to_dict(row, cols):
    """Converte uma linha do cursor em dicionário"""
    return {cols[i]: row[i] for i in range(len(cols))}


def exec_query(query, params=None, fetchone=False, fetchall=False, commit=False):
    """Executa uma query no banco de dados"""
    try:
        conn = get_conn()
        if conn is None:
            logger.error("Falha na conexão com o banco: get_conn() retornou None")
            raise Exception("Falha na conexão com o banco de dados")
            
        cur = conn.cursor()
        logger.debug(f"Executando query: {query}")
        logger.debug(f"Parâmetros: {params}")
        
        cur.execute(query, params or ())

        data = None
        if fetchone:
            data = cur.fetchone()
        elif fetchall:
            data = cur.fetchall()

        if commit:
            conn.commit()

        cols = [c.name for c in cur.description] if (fetchone or fetchall) and cur.description else None

        cur.close()
        conn.close()

        if fetchone and data:
            return row_to_dict(data, cols)
        if fetchall and data:
            return [row_to_dict(r, cols) for r in data]
        return data
    except Exception as e:
        logger.error(f"Erro na execução da query: {str(e)}")
        logger.error(f"Query: {query}")
        logger.error(f"Parâmetros: {params}")
        traceback.print_exc()
        raise


# ============================================================
# 1) LISTAR CLIENTES
# ============================================================
@clientes_bp.get("")
def listar_clientes():
    """Lista clientes com paginação e filtros"""
    try:
        logger.info("=== LISTAR CLIENTES INICIADO ===")
        
        # Obter parâmetros
        q = request.args.get("q", "").strip()
        cidade = request.args.get("cidade", "").strip()
        estado = request.args.get("estado", "").strip()
        
        # Paginação
        try:
            pagina = int(request.args.get("pagina", 1))
            tamanho = int(request.args.get("tamanho", 20))
        except ValueError:
            pagina = 1
            tamanho = 20

        if pagina < 1: pagina = 1
        if tamanho < 1: tamanho = 20
        if tamanho > 200: tamanho = 200

        offset = (pagina - 1) * tamanho

        # Construir filtros
        filtros = []
        valores = []

        if q:
            filtros.append("(nome ILIKE %s OR cpf_cnpj ILIKE %s OR email ILIKE %s OR telefone ILIKE %s)")
            like = f"%{q}%"
            valores += [like, like, like, like]

        if cidade:
            filtros.append("cidade ILIKE %s")
            valores.append(f"%{cidade}%")

        if estado:
            filtros.append("estado ILIKE %s")
            valores.append(f"%{estado}%")

        where_sql = "WHERE " + " AND ".join(filtros) if filtros else ""

        # Consulta principal
        query = f"""
            SELECT
                id,
                nome,
                cpf_cnpj,
                tipo,
                email,
                telefone,
                cidade,
                estado,
                responsavel,
                criado_em
            FROM clientes
            {where_sql}
            ORDER BY criado_em DESC
            LIMIT %s OFFSET %s
        """
        
        # Adicionar parâmetros de paginação
        if valores:
            valores_paginados = valores + [tamanho, offset]
        else:
            valores_paginados = [tamanho, offset]

        logger.debug(f"Query: {query}")
        logger.debug(f"Valores: {valores_paginados}")

        # Executar consulta
        conn = get_conn()
        if not conn:
            logger.error("Falha na conexão com o banco de dados")
            return jsonify({"erro": "Falha na conexão com o banco de dados"}), 500
            
        cur = conn.cursor()
        
        # Executar query principal
        cur.execute(query, tuple(valores_paginados))
        rows = cur.fetchall()
        cols = [c.name for c in cur.description] if cur.description else []
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM clientes {where_sql}"
        if valores:
            cur.execute(count_query, tuple(valores))
        else:
            cur.execute(count_query)
        total = cur.fetchone()[0]

        cur.close()
        conn.close()

        # Converter resultados
        clientes = []
        if cols:
            clientes = [row_to_dict(r, cols) for r in rows]

        logger.info(f"Consulta retornou {len(clientes)} clientes de {total} total")
        
        return jsonify({
            "pagina": pagina,
            "tamanho": tamanho,
            "total": total,
            "clientes": clientes
        })
        
    except Exception as e:
        logger.error(f"Erro em listar_clientes: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao listar clientes", "detalhes": str(e)}), 500


# ============================================================
# 2) CADASTRAR CLIENTE
# ============================================================
@clientes_bp.post("")
def criar_cliente():
    try:
        data = request.json or {}

        if not data.get("nome"):
            return jsonify({"erro": "Campo 'nome' é obrigatório."}), 400

        campos = [
            "nome", "cpf_cnpj", "tipo", "email", "telefone",
            "endereco", "cidade", "estado", "cep",
            "latitude", "longitude", "responsavel", "observacoes"
        ]

        colunas = []
        valores = []
        placeholders = []

        for campo in campos:
            if campo in data and data[campo] is not None:
                colunas.append(campo)
                valores.append(data[campo])
                placeholders.append("%s")

        if not colunas:
            return jsonify({"erro": "Nenhum dado enviado para cadastro."}), 400

        query = f"""
            INSERT INTO clientes ({", ".join(colunas)})
            VALUES ({", ".join(placeholders)})
            RETURNING id, nome, cpf_cnpj, tipo, email, telefone, cidade, estado, responsavel, criado_em;
        """

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, tuple(valores))
        row = cur.fetchone()
        cols = [c.name for c in cur.description]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify(row_to_dict(row, cols)), 201
        
    except Exception as e:
        logger.error(f"Erro em criar_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao criar cliente", "detalhes": str(e)}), 500


# ============================================================
# 3) DETALHAR CLIENTE
# ============================================================
@clientes_bp.get("/<int:cliente_id>")
def detalhes_cliente(cliente_id):
    try:
        cliente = exec_query("""
            SELECT
                id, nome, cpf_cnpj, tipo, email, telefone,
                endereco, cidade, estado, cep,
                latitude, longitude, responsavel, observacoes,
                criado_em
            FROM clientes
            WHERE id = %s
        """, (cliente_id,), fetchone=True)

        if not cliente:
            return jsonify({"erro": "Cliente não encontrado."}), 404

        return jsonify(cliente)
    except Exception as e:
        logger.error(f"Erro em detalhes_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao buscar cliente", "detalhes": str(e)}), 500


# ============================================================
# 4) EDITAR CLIENTE
# ============================================================
@clientes_bp.put("/<int:cliente_id>")
def atualizar_cliente(cliente_id):
    try:
        data = request.json or {}

        campos_permitidos = [
            "nome", "cpf_cnpj", "tipo", "email", "telefone",
            "endereco", "cidade", "estado", "cep",
            "latitude", "longitude", "responsavel", "observacoes"
        ]

        sets = []
        valores = []

        for campo in campos_permitidos:
            if campo in data:
                sets.append(f"{campo} = %s")
                valores.append(data[campo])

        if not sets:
            return jsonify({"erro": "Nenhum campo para atualizar."}), 400

        valores.append(cliente_id)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE clientes
            SET {", ".join(sets)}
            WHERE id = %s
            RETURNING id, nome, cpf_cnpj, tipo, email, telefone, cidade, estado, responsavel, criado_em;
        """, tuple(valores))

        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"erro": "Cliente não encontrado."}), 404

        cols = [c.name for c in cur.description]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify(row_to_dict(row, cols))
    except Exception as e:
        logger.error(f"Erro em atualizar_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao atualizar cliente", "detalhes": str(e)}), 500


# ============================================================
# 5) DELETAR CLIENTE
# ============================================================
@clientes_bp.delete("/<int:cliente_id>")
def deletar_cliente(cliente_id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Verificar se há serviços vinculados
        cur.execute("SELECT COUNT(*) FROM servicos WHERE cliente_id = %s", (cliente_id,))
        qtd_servicos = cur.fetchone()[0]

        if qtd_servicos > 0:
            cur.close()
            conn.close()
            return jsonify({
                "erro": "Cliente possui serviços vinculados.",
                "servicos_vinculados": qtd_servicos
            }), 400

        cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
        apagados = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        if apagados == 0:
            return jsonify({"erro": "Cliente não encontrado."}), 404

        return jsonify({"mensagem": "Cliente removido com sucesso."})
    except Exception as e:
        logger.error(f"Erro em deletar_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao deletar cliente", "detalhes": str(e)}), 500


# ============================================================
# 6) RESUMO POR SERVIÇOS
# ============================================================
@clientes_bp.get("/resumo-servicos")
def resumo_por_servicos():
    try:
        query = """
            SELECT
                c.id,
                c.nome,
                c.cidade,
                c.estado,
                c.responsavel,
                COUNT(s.id) AS qtd_servicos,
                COALESCE(SUM(s.valor), 0) AS valor_total,
                MAX(s.data) AS ultima_data
            FROM clientes c
            LEFT JOIN servicos s ON s.cliente_id = c.id
            GROUP BY c.id, c.nome, c.cidade, c.estado, c.responsavel
            ORDER BY valor_total DESC, qtd_servicos DESC;
        """

        dados = exec_query(query, fetchall=True)
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro em resumo_por_servicos: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao buscar resumo de serviços", "detalhes": str(e)}), 500


# ============================================================
# 7) SERVIÇOS DE UM CLIENTE
# ============================================================
@clientes_bp.get("/<int:cliente_id>/servicos")
def servicos_do_cliente(cliente_id):
    try:
        query = """
            SELECT
                s.id,
                s.descricao,
                s.data,
                s.valor,
                s.latitude,
                s.longitude,
                s.observacoes,
                s.criado_em,
                e.id AS equipe_id
            FROM servicos s
            LEFT JOIN equipe_campo e ON e.id = s.equipe_id
            WHERE s.cliente_id = %s
            ORDER BY s.data DESC NULLS LAST, s.criado_em DESC;
        """
        dados = exec_query(query, (cliente_id,), fetchall=True)
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro em servicos_do_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao buscar serviços do cliente", "detalhes": str(e)}), 500


# ============================================================
# 8) CONTATOS DE UM CLIENTE
# ============================================================
@clientes_bp.get("/<int:cliente_id>/contatos")
def contatos_do_cliente(cliente_id):
    try:
        query = """
            SELECT
                id,
                nome,
                telefone,
                email,
                cargo,
                origem,
                origem_id,
                criado_em
            FROM contatos
            WHERE origem = 'cliente' AND origem_id = %s
            ORDER BY criado_em DESC;
        """
        dados = exec_query(query, (cliente_id,), fetchall=True)
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro em contatos_do_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao buscar contatos do cliente", "detalhes": str(e)}), 500


# ============================================================
# 9) DOCUMENTOS DE UM CLIENTE
# ============================================================
@clientes_bp.get("/<int:cliente_id>/documentos")
def documentos_do_cliente(cliente_id):
    try:
        query = """
            SELECT
                id,
                nome,
                categoria,
                validade,
                arquivo,
                tipo_origem,
                origem_id,
                observacoes,
                criado_em
            FROM documentos
            WHERE tipo_origem = 'cliente' AND origem_id = %s
            ORDER BY criado_em DESC;
        """
        dados = exec_query(query, (cliente_id,), fetchall=True)
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro em documentos_do_cliente: {str(e)}")
        traceback.print_exc()
        return jsonify({"erro": "Erro interno ao buscar documentos do cliente", "detalhes": str(e)}), 500


# ============================================================
# 10) PÁGINA HTML
# ============================================================
@clientes_pages_bp.route('/clientes')
def clientes_page():
    try:
        try:
            pagina = int(request.args.get("pagina", 1))
            tamanho = int(request.args.get("tamanho", 20))
        except ValueError:
            pagina = 1
            tamanho = 20
            
        q = request.args.get("q", "").strip()

        offset = (pagina - 1) * tamanho
        
        filtros = []
        valores = []
        if q:
            filtros.append("(nome ILIKE %s OR cpf_cnpj ILIKE %s OR email ILIKE %s)")
            like = f"%{q}%"
            valores.extend([like, like, like])

        where_sql = "WHERE " + " AND ".join(filtros) if filtros else ""
        
        conn = get_conn()
        cur = conn.cursor()

        if valores:
            cur.execute(f"SELECT COUNT(*) FROM clientes {where_sql}", tuple(valores))
        else:
            cur.execute("SELECT COUNT(*) FROM clientes")
        total = cur.fetchone()[0]

        query = f"""
            SELECT id, nome, cpf_cnpj, tipo, email, telefone, cidade, estado, criado_em
            FROM clientes
            {where_sql}
            ORDER BY criado_em DESC
            LIMIT %s OFFSET %s
        """
        
        if valores:
            cur.execute(query, tuple(valores + [tamanho, offset]))
        else:
            cur.execute(query, (tamanho, offset))
            
        rows = cur.fetchall()
        cols = [c.name for c in cur.description] if cur.description else []
        clientes = [row_to_dict(r, cols) for r in rows] if cols else []
        
        cur.close()
        conn.close()

        return render_template(
            'clientes.html',
            clientes=clientes,
            pagina=pagina,
            tamanho=tamanho,
            total=total,
            search_query=q
        )
    except Exception as e:
        logger.error(f"Erro em clientes_page: {str(e)}")
        traceback.print_exc()
        return f"Erro interno: {str(e)}", 500