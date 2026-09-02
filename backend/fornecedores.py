# ============================================================
#  PATAGONIA • Módulo Unificado de Fornecedores v2025
#  CRUD • Upload • Contratos • Pesquisa
# ============================================================

from flask import Blueprint, request, jsonify, current_app
from core.database import get_conn, get_cursor
from core.storage import get_storage
from datetime import datetime
from werkzeug.utils import secure_filename

fornecedores_bp = Blueprint("fornecedores_bp", __name__, url_prefix="/api/fornecedores")


# ============================================================
# Upload local com pasta individual por fornecedor
# ============================================================

def salvar_arquivo_local(arquivo):
    """
    Save using central storage service. Returns the storage key (not public URL).
    """
    storage = get_storage()
    key = storage.save(arquivo, subdir='fornecedores')
    return key


# ============================================================
# Helpers
# ============================================================

def row_to_dict(cursor, row):
    if not row:
        return None
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


def executar_select(query, params=None, fetchone=False):
    cur = get_cursor()
    cur.execute(query, params or [])
    if fetchone:
        row = cur.fetchone()
        return row_to_dict(cur, row)
    rows = cur.fetchall()
    return [row_to_dict(cur, r) for r in rows]


def executar_commit(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or [])
    conn.commit()
    return cur


# ============================================================
# 1. Listar fornecedores
# ============================================================

@fornecedores_bp.get("/")
def listar_fornecedores():
    try:
        fornecedores = executar_select("""
            SELECT *
            FROM fornecedores
            ORDER BY nome_fantasia ASC
        """)
        return jsonify({"status": "ok", "total": len(fornecedores), "dados": fornecedores})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 2. Criar fornecedor (upload organizado)
# ============================================================

@fornecedores_bp.post("/criar")
def criar_fornecedor():

    dados = dict(request.form)
    arquivo = request.files.get("arquivo")

    # Campos obrigatórios
    for campo in ["nome_fantasia", "cnpj"]:
        if campo not in dados or not dados[campo]:
            return jsonify({"status": "erro", "mensagem": f"Campo obrigatório: {campo}"}), 400

    try:
        # 1) Cria fornecedor SEM arquivo primeiro
        cur = executar_commit("""
            INSERT INTO fornecedores (
                nome_fantasia, razao_social, cnpj, inscricao_estadual, inscricao_municipal,
                telefone, email, site,
                contato_nome, contato_email, contato_telefone,
                cep, endereco, numero, complemento, bairro, cidade, estado,
                categoria, rating, ativo,
                prazo_pagamento, forma_pagamento, limite_credito,
                certificado_iso, validade_documentos, observacoes,
                criado_em, atualizado_em
            )
            VALUES (
                %(nome_fantasia)s, %(razao_social)s, %(cnpj)s, %(inscricao_estadual)s, %(inscricao_municipal)s,
                %(telefone)s, %(email)s, %(site)s,
                %(contato_nome)s, %(contato_email)s, %(contato_telefone)s,
                %(cep)s, %(endereco)s, %(numero)s, %(complemento)s, %(bairro)s, %(cidade)s, %(estado)s,
                %(categoria)s, %(rating)s, TRUE,
                %(prazo_pagamento)s, %(forma_pagamento)s, %(limite_credito)s,
                %(certificado_iso)s, %(validade_documentos)s, %(observacoes)s,
                NOW(), NOW()
            )
            RETURNING id;
        """, dados)

        novo_id = cur.fetchone()[0]

        # 2) Se houver arquivo, salva agora na pasta correta
        arquivo_url = None
        if arquivo:
            key = salvar_arquivo_local(arquivo)

            executar_commit("""
                UPDATE fornecedores
                SET arquivo_url = %s, atualizado_em = NOW()
                WHERE id = %s
            """, (key, novo_id))
            storage = get_storage()
            arquivo_url = storage.get_url(key)

        return jsonify({
            "status": "ok",
            "mensagem": "Fornecedor criado com sucesso",
            "id": novo_id,
            "arquivo_url": arquivo_url
        })

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 3. Obter fornecedor por ID
# ============================================================

@fornecedores_bp.get("/<int:fornecedor_id>")
def obter_fornecedor(fornecedor_id):
    try:
        fornecedor = executar_select(
            "SELECT * FROM fornecedores WHERE id = %s",
            (fornecedor_id,),
            fetchone=True
        )
        if not fornecedor:
            return jsonify({"status": "erro", "mensagem": "Fornecedor não encontrado"}), 404

        return jsonify({"status": "ok", "dados": fornecedor})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 4. Atualizar fornecedor
# ============================================================

@fornecedores_bp.put("/<int:fornecedor_id>")
def atualizar_fornecedor(fornecedor_id):
    dados = request.json or {}
    if not dados:
        return jsonify({"status": "erro", "mensagem": "Nenhum campo enviado"}), 400

    try:
        campos = [f"{k} = %({k})s" for k in dados.keys()]
        dados["id"] = fornecedor_id

        executar_commit(f"""
            UPDATE fornecedores
            SET {', '.join(campos)}, atualizado_em = NOW()
            WHERE id = %(id)s
        """, dados)

        return jsonify({"status": "ok", "mensagem": "Fornecedor atualizado com sucesso"})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 5. Upload de arquivo (agora com pasta por fornecedor)
# ============================================================

@fornecedores_bp.post("/<int:fornecedor_id>/upload")
def upload_arquivo_fornecedor(fornecedor_id):
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"status": "erro", "mensagem": "Nenhum arquivo enviado"}), 400

    try:
        key = salvar_arquivo_local(arquivo)

        executar_commit("""
            UPDATE fornecedores
            SET arquivo_url = %s, atualizado_em = NOW()
            WHERE id = %s
        """, (key, fornecedor_id))
        
        storage = get_storage()
        return jsonify({
            "status": "ok",
            "mensagem": "Arquivo enviado com sucesso",
            "arquivo_url": storage.get_url(key)
        })

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 6. Vincular contrato
# ============================================================

@fornecedores_bp.put("/<int:fornecedor_id>/vincular_contrato")
def vincular_contrato(fornecedor_id):
    contrato_id = (request.json or {}).get("contrato_id")
    if not contrato_id:
        return jsonify({"status": "erro", "mensagem": "Contrato não informado"}), 400

    try:
        executar_commit("""
            UPDATE fornecedores
            SET contrato_id = %s, atualizado_em = NOW()
            WHERE id = %s
        """, (contrato_id, fornecedor_id))

        return jsonify({"status": "ok", "mensagem": "Contrato vinculado com sucesso"})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 7. Busca livre
# ============================================================

@fornecedores_bp.get("/buscar")
def buscar_fornecedor():
    termo = request.args.get("q", "").strip()

    try:
        fornecedores = executar_select("""
            SELECT *
            FROM fornecedores
            WHERE nome_fantasia ILIKE %s
               OR cnpj ILIKE %s
            ORDER BY nome_fantasia ASC
        """, (f"%{termo}%", f"%{termo}%"))

        return jsonify({"status": "ok", "total": len(fornecedores), "dados": fornecedores})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 8. Soft delete
# ============================================================

@fornecedores_bp.delete("/desativar/<int:fornecedor_id>")
def desativar_fornecedor(fornecedor_id):
    try:
        executar_commit("""
            UPDATE fornecedores
            SET ativo = FALSE, atualizado_em = NOW()
            WHERE id = %s
        """, (fornecedor_id,))
        return jsonify({"status": "ok", "mensagem": "Fornecedor desativado"})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ============================================================
# 9. Hard delete
# ============================================================

@fornecedores_bp.delete("/delete/<int:fornecedor_id>")
def deletar_fornecedor(fornecedor_id):
    try:
        executar_commit("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
        return jsonify({"status": "ok", "mensagem": "Fornecedor removido permanentemente"})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
