from flask import Blueprint, request, jsonify, send_file, current_app
from core.database import get_conn
from core.storage import get_storage
from datetime import time, date, datetime
import io
import traceback

# ============================================================
# BLUEPRINT
# ============================================================

equipe_campo_bp = Blueprint('equipe_campo', __name__, url_prefix='/api/equipe-campo')

# ============================================================
# HELPERS
# ============================================================
def save_file(file):
    """Save file using central storage service and return the storage key."""
    if not file or not file.filename:
        return None

    try:
        storage = get_storage()
        key = storage.save(file, subdir='equipe_campo')
        return key
    except ValueError as e:
        # Could be an invalid subdir or filename
        print(f"File save error: {e}")
        return None


def dict_row(row, cols):
    result = {}
    for i in range(len(cols)):
        value = row[i]
        if isinstance(value, (time, date, datetime)):
            result[cols[i]] = value.isoformat()
        else:
            result[cols[i]] = value
    return result


# ============================================================
# ROTAS ADICIONAIS - SIMPLIFICADAS
# ============================================================

@equipe_campo_bp.get('/')
def listar_registros():
    """Lista todos os registros de campo"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        sql = """
            SELECT ec.*, 
                   c.nome as colaborador_nome,
                   v.modelo as veiculo_modelo, 
                   v.placa as veiculo_placa,
                   v.marca as veiculo_marca,
                   cl.nome as cliente_nome
            FROM equipe_campo ec
            LEFT JOIN colaboradores c ON ec.colaborador_id = c.id
            LEFT JOIN veiculos v ON ec.veiculo_id = v.id
            LEFT JOIN clientes cl ON ec.cliente_id = cl.id
            ORDER BY ec.data_saida DESC, ec.hora_saida DESC
        """
        
        cur.execute(sql)
        colunas = [desc[0] for desc in cur.description]
        
        storage = get_storage()
        registros = []
        for row in cur.fetchall():
            reg = dict_row(row, colunas)
            reg['anexo_saida_url'] = storage.get_url(reg['anexo_saida']) if reg.get('anexo_saida') else None
            reg['anexo_retorno_url'] = storage.get_url(reg['anexo_retorno']) if reg.get('anexo_retorno') else None
            registros.append(reg)
        
        return jsonify(registros)
        
    except Exception as e:
        print(f"Erro em listar_registros: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@equipe_campo_bp.get('/colaboradores')
def listar_colaboradores():
    """Lista colaboradores disponíveis"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Query SIMPLES - sem WHERE complexo
        sql = "SELECT id, nome FROM colaboradores ORDER BY nome"
        
        cur.execute(sql)
        colunas = [desc[0] for desc in cur.description]
        colaboradores = [dict_row(row, colunas) for row in cur.fetchall()]
        
        return jsonify(colaboradores)
        
    except Exception as e:
        print(f"Erro em listar_colaboradores: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Erro ao buscar colaboradores"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@equipe_campo_bp.get('/veiculos')
def listar_veiculos():
    """Lista veículos disponíveis"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Query SIMPLES
        sql = "SELECT id, modelo, placa, marca FROM veiculos ORDER BY modelo"
        
        cur.execute(sql)
        colunas = [desc[0] for desc in cur.description]
        veiculos = [dict_row(row, colunas) for row in cur.fetchall()]
        
        return jsonify(veiculos)
        
    except Exception as e:
        print(f"Erro em listar_veiculos: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Erro ao buscar veículos"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@equipe_campo_bp.get('/clientes')
def listar_clientes():
    """Lista clientes"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Query SIMPLES
        sql = "SELECT id, nome, cpf_cnpj, telefone FROM clientes ORDER BY nome"
        
        cur.execute(sql)
        colunas = [desc[0] for desc in cur.description]
        clientes = [dict_row(row, colunas) for row in cur.fetchall()]
        
        return jsonify(clientes)
        
    except Exception as e:
        print(f"Erro em listar_clientes: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Erro ao buscar clientes"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@equipe_campo_bp.get('/<int:id>')
def obter_registro(id):
    """Obtém um registro específico"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        sql = """
            SELECT ec.*, 
                   c.nome as colaborador_nome,
                   v.modelo as veiculo_modelo, 
                   v.placa as veiculo_placa,
                   v.marca as veiculo_marca,
                   cl.nome as cliente_nome
            FROM equipe_campo ec
            LEFT JOIN colaboradores c ON ec.colaborador_id = c.id
            LEFT JOIN veiculos v ON ec.veiculo_id = v.id
            LEFT JOIN clientes cl ON ec.cliente_id = cl.id
            WHERE ec.id = %s
        """
        
        cur.execute(sql, (id,))
        colunas = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        
        if not row:
            return jsonify({"error": "Registro não encontrado"}), 404
        
        reg = dict_row(row, colunas)
        storage = get_storage()
        reg['anexo_saida_url'] = storage.get_url(reg['anexo_saida']) if reg.get('anexo_saida') else None
        reg['anexo_retorno_url'] = storage.get_url(reg['anexo_retorno']) if reg.get('anexo_retorno') else None
        return jsonify(reg)
        
    except Exception as e:
        print(f"Erro em obter_registro: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# SAÍDA COM ANEXO
# ============================================================

@equipe_campo_bp.post('/saida')
def registrar_saida():
    conn = None
    cur = None
    try:
        # Obter dados do formulário
        data = request.form.to_dict()
        
        # Obter arquivo se existir
        anexo = request.files.get("anexo_saida")
        anexo_saida_path = save_file(anexo)

        required = ["colaborador_id", "veiculo_id", "cliente_id", "data_saida", "hora_saida", "km_saida"]
        if any(r not in data or not data[r] for r in required):
            return jsonify({"error": "Campos obrigatórios faltando."}), 400

        conn = get_conn()
        cur = conn.cursor()

        sql = """
            INSERT INTO equipe_campo
            (colaborador_id, veiculo_id, cliente_id,
             data_saida, hora_saida, km_saida,
             local_lat, local_lon, observacoes, status,
             anexo_saida)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'em_campo',%s)
            RETURNING id;
        """

        cur.execute(sql, (
            data["colaborador_id"],
            data["veiculo_id"],
            data["cliente_id"],
            data["data_saida"],
            data["hora_saida"],
            data["km_saida"],
            data.get("local_lat"),
            data.get("local_lon"),
            data.get("observacoes"),
            anexo_saida_path
        ))

        registro_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "message": "Saída registrada com sucesso!",
            "id": registro_id
        }), 201
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro em registrar_saida: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Erro ao registrar saída: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# RETORNO COM ANEXO
# ============================================================

@equipe_campo_bp.put('/retorno/<int:id>')
def registrar_retorno(id):
    conn = None
    cur = None
    try:
        data = request.form.to_dict()
        
        # Obter arquivo se existir
        anexo = request.files.get("anexo_retorno")
        anexo_retorno_path = save_file(anexo)

        required = ["data_retorno", "hora_retorno", "km_retorno"]
        if any(r not in data or not data[r] for r in required):
            return jsonify({"error": "Campos obrigatórios faltando."}), 400

        conn = get_conn()
        cur = conn.cursor()

        # obter km saída
        cur.execute("SELECT km_saida FROM equipe_campo WHERE id=%s", (id,))
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Registro não encontrado"}), 404

        km_saida = float(row[0]) if row[0] else 0
        km_retorno = float(data["km_retorno"])

        if km_retorno < km_saida:
            return jsonify({"error": "KM de retorno não pode ser menor que KM saída."}), 400

        sql = """
            UPDATE equipe_campo
            SET data_retorno=%s,
                hora_retorno=%s,
                km_retorno=%s,
                observacoes_retorno=%s,
                anexo_retorno=%s,
                status='finalizado'
            WHERE id=%s
        """

        cur.execute(sql, (
            data["data_retorno"],
            data["hora_retorno"],
            km_retorno,
            data.get("observacoes_retorno"),
            anexo_retorno_path,
            id
        ))

        conn.commit()
        return jsonify({"message": "Retorno registrado com sucesso!"}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro em registrar_retorno: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Erro ao registrar retorno: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# DOWNLOAD DE ANEXOS
# ============================================================

@equipe_campo_bp.get("/download_anexo/<int:id>/<tipo>")
def download_anexo(id, tipo):
    """tipo = saida ou retorno"""

    coluna = "anexo_saida" if tipo == "saida" else "anexo_retorno"
    conn = None
    cur = None
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT {coluna} FROM equipe_campo WHERE id = %s", (id,))
        row = cur.fetchone()

        if not row or not row[0]:
            return jsonify({"error": "Arquivo não encontrado"}), 404

        key = row[0]
        storage = get_storage()
        
        try:
            file_bytes = storage.open(key)
            download_name = key.split('/')[-1]
            return send_file(
                io.BytesIO(file_bytes),
                as_attachment=True,
                download_name=download_name
            )
        except FileNotFoundError:
            return jsonify({"erro": "Arquivo não encontrado no storage."}), 404

    except Exception as e:
        print(f"Erro em download_anexo: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Erro ao baixar arquivo: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# DELETAR REGISTRO + ARQUIVOS
# ============================================================

@equipe_campo_bp.delete('/<int:id>')
def deletar(id):
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT anexo_saida, anexo_retorno FROM equipe_campo WHERE id=%s", (id,))
        row = cur.fetchone()
        
        if row:
            storage = get_storage()
            for path in row:
                if path:
                    try:
                        storage.delete(path)
                    except Exception as e:
                        print(f"Failed to delete file {path}: {e}")

        cur.execute("DELETE FROM equipe_campo WHERE id=%s RETURNING id", (id,))
        deleted = cur.fetchone()

        conn.commit()

        if not deleted:
            return jsonify({"error": "Registro não encontrado"}), 404

        return jsonify({"message": "Registro deletado com sucesso!"}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro em deletar: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Erro ao deletar registro: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
# ROTA DE TESTE - Para verificar se as tabelas existem
# ============================================================

@equipe_campo_bp.get('/teste-tabelas')
def teste_tabelas():
    """Testa se as tabelas existem e mostra alguns dados"""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        resultado = {}
        
        # Testar tabela colaboradores
        try:
            cur.execute("SELECT COUNT(*) as total FROM colaboradores")
            resultado['colaboradores'] = cur.fetchone()[0]
        except Exception as e:
            resultado['colaboradores_error'] = str(e)
            
        # Testar tabela veiculos
        try:
            cur.execute("SELECT COUNT(*) as total FROM veiculos")
            resultado['veiculos'] = cur.fetchone()[0]
        except Exception as e:
            resultado['veiculos_error'] = str(e)
            
        # Testar tabela clientes
        try:
            cur.execute("SELECT COUNT(*) as total FROM clientes")
            resultado['clientes'] = cur.fetchone()[0]
        except Exception as e:
            resultado['clientes_error'] = str(e)
            
        # Testar tabela equipe_campo
        try:
            cur.execute("SELECT COUNT(*) as total FROM equipe_campo")
            resultado['equipe_campo'] = cur.fetchone()[0]
        except Exception as e:
            resultado['equipe_campo_error'] = str(e)
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"error": f"Erro no teste: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()