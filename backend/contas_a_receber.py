from flask import Blueprint, request, jsonify, send_file, current_app
from core.database import get_conn
from core.storage import get_storage
from werkzeug.utils import secure_filename
import io

bp_receber = Blueprint("contas_receber", __name__, url_prefix="/api/contas_receber")

# ============================================================
# SERIALIZADOR
# ============================================================
def serialize_receber(row):
    storage = get_storage()
    return {
        "id": row[0],
        "cliente": row[1],
        "descricao": row[2],
        "valor": float(row[3]),
        "vencimento": row[4],
        "categoria": row[5],
        "status": row[6],
        "comprovante": row[7],
        "comprovante_nome": row[8],
        "criado_em": row[9],
        "comprovante_url": storage.get_url(row[7]) if row[7] else None
    }


# ============================================================
# LISTAR CONTAS A RECEBER
# ============================================================
@bp_receber.get("/")
def listar():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM contas_receber ORDER BY vencimento DESC")
    contas = [serialize_receber(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(contas)


# ============================================================
# CRIAR CONTA A RECEBER
# - aceita JSON e multipart (upload)
# ============================================================
@bp_receber.post("/")
def criar():
    try:
        file = request.files.get("comprovante")
        comprovante_path = None
        comprovante_nome = None

        storage = get_storage()

        # Upload, se enviado
        if file and file.filename:
            original = secure_filename(file.filename)
            key = storage.save(file, subdir='recebimentos')
            comprovante_path = key
            comprovante_nome = original

        # Dados (pode vir como form ou json)
        data = request.form if request.form else request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO contas_receber
                (cliente, descricao, valor, vencimento, categoria, status,
                 comprovante, comprovante_nome)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data.get("cliente"),
            data.get("descricao"),
            float(data.get("valor", 0)),
            data.get("vencimento"),
            data.get("categoria"),
            data.get("status", "pendente"),
            comprovante_path,
            comprovante_nome
        ))

        novo_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify({
            "id": novo_id, 
            "mensagem": "Criado com sucesso",
            "comprovante_url": storage.get_url(comprovante_path) if comprovante_path else None
        }), 201

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ============================================================
# DOWNLOAD DO COMPROVANTE
# ============================================================
@bp_receber.get("/download/<int:id>")
def download(id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT comprovante, comprovante_nome
        FROM contas_receber WHERE id = %s
    """, (id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({"erro": "Comprovante não encontrado"}), 404

    caminho, nome = row
    storage = get_storage()
    try:
        file_bytes = storage.open(caminho)
        return send_file(io.BytesIO(file_bytes), as_attachment=True, download_name=nome or "arquivo")
    except FileNotFoundError:
        return jsonify({"erro": "Arquivo não encontrado no storage."}), 404


# ============================================================
# ATUALIZAR CONTA A RECEBER
# ============================================================
@bp_receber.put("/<int:id>")
def atualizar(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        storage = get_storage()

        # Recupera o arquivo atual
        cur.execute("SELECT comprovante FROM contas_receber WHERE id = %s", (id,))
        atual = cur.fetchone()
        caminho_atual = atual[0] if atual else None

        file = request.files.get("comprovante")
        comprovante_path = caminho_atual
        comprovante_nome = request.form.get("comprovante_nome")

        # Novo upload
        if file and file.filename:
            if caminho_atual:
                try:
                    storage.delete(caminho_atual)
                except Exception:
                    pass

            original = secure_filename(file.filename)
            new_key = storage.save(file, subdir='recebimentos')
            comprovante_path = new_key
            comprovante_nome = original

        data = request.form if request.form else request.json

        cur.execute("""
            UPDATE contas_receber SET
                cliente=%s, descricao=%s, valor=%s, vencimento=%s,
                categoria=%s, status=%s, comprovante=%s, comprovante_nome=%s
            WHERE id=%s
        """, (
            data.get("cliente"),
            data.get("descricao"),
            float(data.get("valor", 0)),
            data.get("vencimento"),
            data.get("categoria"),
            data.get("status"),
            comprovante_path,
            comprovante_nome,
            id
        ))

        conn.commit()
        conn.close()

        return jsonify({"mensagem": "Atualizado com sucesso"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ============================================================
# EXCLUIR CONTA
# ============================================================
@bp_receber.delete("/<int:id>")
def excluir(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        storage = get_storage()

        # Verifica se existe arquivo
        cur.execute("SELECT comprovante FROM contas_receber WHERE id = %s", (id,))
        row = cur.fetchone()

        if row and row[0]:
            try:
                storage.delete(row[0])
            except Exception:
                pass

        cur.execute("DELETE FROM contas_receber WHERE id = %s", (id,))
        conn.commit()
        conn.close()

        return jsonify({"mensagem": "Removido com sucesso"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
