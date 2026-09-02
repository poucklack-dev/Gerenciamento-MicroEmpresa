from flask import Blueprint, request, jsonify, send_file, current_app
from core.database import get_conn
from core.storage import get_storage
from werkzeug.utils import secure_filename
import io

bp_faces = Blueprint("faces", __name__, url_prefix="/api/faces")

# ============================================================
# CONFIGURAÇÃO DE UPLOAD
# ============================================================

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_face(file):
    """Save face image using central storage; return storage key."""
    storage = get_storage()
    key = storage.save(file, subdir='faces')
    return key


# ============================================================
# UPLOAD / SUBSTITUIR FOTO FACIAL
# ============================================================

@bp_faces.post("/<int:colaborador_id>")
def salvar_foto_facial(colaborador_id):
    try:
        if "foto" not in request.files:
            return jsonify({"erro": "Nenhuma foto enviada"}), 400

        file = request.files["foto"]

        if file.filename == "":
            return jsonify({"erro": "Arquivo inválido"}), 400

        if not allowed(file.filename):
            return jsonify({"erro": "Formato não permitido (use JPG, PNG)"}), 400

        conn = get_conn()
        cur = conn.cursor()

        # Busca foto atual (se existir)
        cur.execute("SELECT foto_path FROM colaboradores WHERE id = %s", (colaborador_id,))
        row = cur.fetchone()
        foto_antiga = row[0] if row else None

        # Salva novo arquivo via storage
        novo_key = save_face(file)

        # Remove antigo se existir
        if foto_antiga:
            try:
                storage = get_storage()
                storage.delete(foto_antiga)
            except Exception:
                pass

        # Atualiza banco (armazenamos a key)
        cur.execute("""
            UPDATE colaboradores
            SET foto_path = %s
            WHERE id = %s
        """, (novo_key, colaborador_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "ok",
            "mensagem": "Foto facial salva com sucesso!",
            "url": get_storage().get_url(novo_key)
        })
    except Exception as e:
        current_app.logger.exception("Erro ao salvar foto facial")
        return jsonify({"erro": str(e)}), 500


# ============================================================
# DOWNLOAD DA FOTO
# ============================================================

@bp_faces.get("/download/<int:colaborador_id>")
def download_face(colaborador_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT foto_path FROM colaboradores WHERE id = %s", (colaborador_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row or not row[0]:
        return jsonify({"erro": "Nenhuma foto cadastrada"}), 404

    key = row[0]
    storage = get_storage()
    try:
        file_bytes = storage.open(key)
        return send_file(io.BytesIO(file_bytes), mimetype="image/jpeg", as_attachment=False)
    except FileNotFoundError:
        return jsonify({"erro": "Arquivo não encontrado no storage."}), 404

# ============================================================
# DELETAR FOTO FACIAL
# ============================================================

@bp_faces.delete("/<int:colaborador_id>")
def deletar_foto_facial(colaborador_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT foto_path FROM colaboradores WHERE id = %s", (colaborador_id,))
    row = cur.fetchone()

    if not row or not row[0]:
        return jsonify({"erro": "Nenhuma foto encontrada"}), 404

    key = row[0]
    try:
        storage = get_storage()
        storage.delete(key)
    except Exception:
        pass

    cur.execute("""
        UPDATE colaboradores
        SET foto_path = NULL
        WHERE id = %s
    """, (colaborador_id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"mensagem": "Foto facial removida com sucesso!"})
