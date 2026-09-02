from flask import Blueprint, request, jsonify, send_file, redirect, current_app
from core.database import get_conn
from core.storage import get_storage
import io

bp_contratos = Blueprint("contratos", __name__, url_prefix="/api/contratos")

# ============================================================
# SERIALIZADOR
# ============================================================
def serialize_contrato(row):
    storage = get_storage()
    return {
        "id": row[0],
        "codigo_contrato": row[1],
        "nome_empresa": row[2],
        "descricao_servico": row[3],
        "valor_orcado": float(row[4]),
        "data_inicio": row[5],
        "data_fim": row[6],
        "status": row[7],
        "criado_em": row[8],
        "atualizado_em": row[9],
        "arquivo": row[10],
        "arquivo_nome": row[11],
        "arquivo_url": storage.get_url(row[10]) if row[10] else None
    }


# ============================================================
# LISTAR
# ============================================================
@bp_contratos.get("/")
def listar_contratos():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, codigo_contrato, nome_empresa, descricao_servico,
               valor_orcado, data_inicio, data_fim, status,
               criado_em, atualizado_em, arquivo, arquivo_nome
        FROM contratos
        ORDER BY id DESC
    """)

    contratos = [serialize_contrato(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(contratos)


# ============================================================
# CRIAR CONTRATO (SUPORTA UPLOAD)
# ============================================================
@bp_contratos.post("/")
def criar_contrato():
    try:
        file = request.files.get("arquivo")
        arquivo_path = None
        arquivo_nome = None
        storage = get_storage()

        if file and file.filename:
            arquivo_path = storage.save(file, subdir='contratos')
            arquivo_nome = file.filename

        data = request.form if request.form else request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO contratos
                (codigo_contrato, nome_empresa, descricao_servico,
                 valor_orcado, data_inicio, data_fim, arquivo, arquivo_nome)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data["codigo_contrato"],
            data["nome_empresa"],
            data.get("descricao_servico"),
            data["valor_orcado"],
            data.get("data_inicio"),
            data.get("data_fim"),
            arquivo_path,
            arquivo_nome
        ))

        novo_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify({
            "id": novo_id, 
            "mensagem": "Contrato criado com sucesso!",
            "arquivo_url": storage.get_url(arquivo_path) if arquivo_path else None
        }), 201

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ============================================================
# DOWNLOAD DE ARQUIVO
# ============================================================
@bp_contratos.get("/download/<int:id>")
def download_arquivo(id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT arquivo, arquivo_nome FROM contratos WHERE id=%s", (id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({"erro": "Arquivo não encontrado"}), 404

    key, nome_arquivo = row
    storage = get_storage()

    try:
        file_bytes = storage.open(key)
        return send_file(
            io.BytesIO(file_bytes),
            as_attachment=True,
            download_name=nome_arquivo or "arquivo"
        )
    except FileNotFoundError:
        return jsonify({"erro": "Arquivo não encontrado no storage."}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ============================================================
# DETALHAR CONTRATO + PERFORMANCE
# ============================================================
@bp_contratos.get("/<int:id>")
def detalhe_contrato(id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, codigo_contrato, nome_empresa, descricao_servico,
               valor_orcado, data_inicio, data_fim, status,
               criado_em, atualizado_em, arquivo, arquivo_nome
        FROM contratos
        WHERE id = %s
    """, (id,))
    contrato = cur.fetchone()

    if not contrato:
        return jsonify({"error": "Contrato não encontrado"}), 404

    contrato_dict = serialize_contrato(contrato)

    # GASTOS REAIS
    cur.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM contas_pagar
        WHERE contrato_id = %s
    """, (id,))
    gastos = float(cur.fetchone()[0])

    contrato_dict["gastos_reais"] = gastos
    contrato_dict["saldo_atual"] = contrato_dict["valor_orcado"] - gastos

    # MOVIMENTAÇÕES
    cur.execute("""
        SELECT id, fornecedor, descricao, valor, vencimento, status
        FROM contas_pagar
        WHERE contrato_id = %s
        ORDER BY vencimento DESC
    """, (id,))

    contrato_dict["movimentacoes"] = [
        {
            "id": r[0],
            "fornecedor": r[1],
            "descricao": r[2],
            "valor": float(r[3]),
            "vencimento": r[4],
            "status": r[5]
        } for r in cur.fetchall()
    ]

    conn.close()
    return jsonify(contrato_dict)


# ============================================================
# ATUALIZAR (SUPORTA TROCA DE ARQUIVO)
# ============================================================
@bp_contratos.put("/<int:id>")
def atualizar_contrato(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT arquivo FROM contratos WHERE id=%s", (id,))
        atual = cur.fetchone()
        arquivo_atual = atual[0] if atual else None

        file = request.files.get("arquivo")
        arquivo_path = arquivo_atual
        arquivo_nome = request.form.get("arquivo_nome")

        if file and file.filename:
            storage = get_storage()
            # remove previous via storage (works for local and gcs)
            if arquivo_atual:
                try:
                    storage.delete(arquivo_atual)
                except Exception as e:
                    print(f"Failed to delete old file: {e}") # Log error

            arquivo_path = storage.save(file, subdir='contratos')
            arquivo_nome = file.filename

        data = request.form if request.form else request.json

        cur.execute("""
            UPDATE contratos SET
                codigo_contrato=%s,
                nome_empresa=%s,
                descricao_servico=%s,
                valor_orcado=%s,
                data_inicio=%s,
                data_fim=%s,
                arquivo=%s,
                arquivo_nome=%s,
                atualizado_em=NOW()
            WHERE id=%s
        """, (
            data.get("codigo_contrato"),
            data.get("nome_empresa"),
            data.get("descricao_servico"),
            data.get("valor_orcado"),
            data.get("data_inicio"),
            data.get("data_fim"),
            arquivo_path,
            arquivo_nome,
            id
        ))

        conn.commit()
        conn.close()
        return jsonify({"mensagem": "Contrato atualizado com sucesso!"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ============================================================
# EXCLUIR CONTRATO + ARQUIVO
# ============================================================
@bp_contratos.delete("/<int:id>")
def excluir_contrato(id):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT arquivo FROM contratos WHERE id=%s", (id,))
        row = cur.fetchone()

        if row and row[0]:
            storage = get_storage()
            try:
                storage.delete(row[0])
            except Exception as e:
                print(f"Failed to delete file on GCS/local: {e}") # Log error


        cur.execute("DELETE FROM contratos WHERE id=%s", (id,))
        conn.commit()
        conn.close()

        return jsonify({"mensagem": "Contrato removido com sucesso!"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
