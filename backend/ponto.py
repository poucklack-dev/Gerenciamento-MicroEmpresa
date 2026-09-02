# ============================================================
#  PATAGONIA — Ponto Inteligente v3.0 + Localização
#  Reconhecimento Facial + CPF + Jornada Inteligente + Geolocalização
# ============================================================

from flask import Blueprint, request, jsonify, render_template, current_app
import cv2
import numpy as np
import pickle
import io
from datetime import datetime, date, time, timedelta
import re
import json
from decimal import Decimal
import os
import threading
from core.database import get_conn
from core.storage import get_storage

bp_ponto = Blueprint('ponto', __name__, url_prefix='/ponto')

# ============================================================
# CONFIGURAÇÕES DO SISTEMA
# ============================================================
HORAS_MAXIMO_JORNADA = 14
HORAS_MINIMO_ENTRADA = 4
ENCODINGS_KEY = "data/facial_encodings.pkl"

# ============================================================
#  UTILIDADES
# ============================================================
def formatar_cpf_para_busca(cpf):
    cpf_numeros = re.sub(r'\D', '', cpf)
    if len(cpf_numeros) == 11:
        return f"{cpf_numeros[:3]}.{cpf_numeros[3:6]}.{cpf_numeros[6:9]}-{cpf_numeros[9:]}"
    return cpf


def buscar_colaborador_por_cpf(cpf):
    """Busca colaborador comparando apenas os 11 dígitos do CPF."""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cpf_numeros = re.sub(r'\D', '', cpf or '')
        if len(cpf_numeros) != 11:
            return None
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"🔍 Buscando colaborador pelo CPF final {cpf_numeros[-4:]}")

        cur.execute("""
            SELECT id, nome, email, cpf
            FROM colaboradores
            WHERE regexp_replace(COALESCE(cpf, ''), '[^0-9]', '', 'g') = %s
            LIMIT 1
        """, (cpf_numeros,))
        dados = cur.fetchone()
        return dados

    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print("❌ Erro buscar colaborador:", str(e))
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def processar_dados_localizacao(dados_localizacao):
    """Processa os dados de localização recebidos - SEM PRECISÃO."""
    try:
        if not dados_localizacao:
            return None
        
        localizacao = json.loads(dados_localizacao)
        
        # Extrair apenas latitude e longitude - SEM PRECISÃO
        resultado = {
            "latitude": float(localizacao.get("latitude")) if localizacao.get("latitude") else None,
            "longitude": float(localizacao.get("longitude")) if localizacao.get("longitude") else None,
            "endereco": localizacao.get("endereco", ""),
            "timestamp": localizacao.get("timestamp"),
            "data_obtencao": localizacao.get("data_obtencao")
        }
        
        # Verificar se tem coordenadas válidas
        if resultado["latitude"] and resultado["longitude"]:
            return resultado
        else:
            return None
            
    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro ao processar localização: {str(e)}")
        return None


# ============================================================
#  JORNADA INTELIGENTE
# ============================================================
def verificar_ultimo_ponto(colaborador_id, agora):
    """Decide se deve registrar ENTRADA ou SAÍDA."""
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, data_registro, hora_entrada, hora_saida, tipo_registro
            FROM ponto
            WHERE colaborador_id = %s
            ORDER BY data_registro DESC, hora_entrada DESC
            LIMIT 1
        """, (colaborador_id,))

        ultimo = cur.fetchone()

        if not ultimo:
            if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                print("📋 Primeiro ponto → ENTRADA")
            return {"tipo": "entrada", "motivo": "primeiro_ponto"}

        ponto_id, data_registro, hora_entrada, hora_saida, tipo_registro = ultimo
        agora_timestamp = agora.timestamp()

        # Converter hora_entrada para timestamp
        if hora_entrada:
            entrada_timestamp = hora_entrada.timestamp()
        else:
            entrada_timestamp = None

        # CASO A: Ponto aberto sem saída
        if hora_entrada and not hora_saida:
            if entrada_timestamp:
                horas = (agora_timestamp - entrada_timestamp) / 3600

                if horas > HORAS_MAXIMO_JORNADA:
                    if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                        print("⚠️ Jornada estourada — fechando automaticamente")

                    hora_saida_auto = datetime.fromtimestamp(
                        entrada_timestamp + HORAS_MAXIMO_JORNADA * 3600
                    )

                    cur.execute("""
                        UPDATE ponto
                        SET hora_saida=%s, tipo_registro='saida',
                            observacao=%s
                        WHERE id=%s
                    """, (
                        hora_saida_auto,
                        f"Fechado automaticamente após {HORAS_MAXIMO_JORNADA}h",
                        ponto_id
                    ))
                    conn.commit()

                    return {"tipo": "entrada", "motivo": "jornada_maxima_excedida"}

            return {
                "tipo": "saida",
                "id_ponto": ponto_id,
                "hora_entrada": hora_entrada,
                "motivo": "saida_normal"
            }

        # CASO B: Último ponto completo
        if hora_entrada and hora_saida:
            saida_timestamp = hora_saida.timestamp()
            horas_desde_saida = (agora_timestamp - saida_timestamp) / 3600

            if horas_desde_saida >= HORAS_MINIMO_ENTRADA:
                return {"tipo": "entrada", "motivo": "intervalo_ok"}

            return {"tipo": "entrada", "motivo": "intervalo_curto"}

        return {"tipo": "entrada", "motivo": "indefinido"}

    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print("❌ Erro verificar ponto:", str(e))
        return {"tipo": "entrada", "motivo": "erro"}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================
#  SISTEMA FACIAL
# ============================================================
class SmartFacialSystem:
    """Reconhecimento local por descritores HOG normalizados do rosto."""

    FORMAT_VERSION = 2
    RECOGNITION_THRESHOLD = 0.88
    AMBIGUITY_MARGIN = 0.035

    def __init__(self):
        self.storage = get_storage()
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.encodings = {}
        self._lock = threading.RLock()
        self._hog = cv2.HOGDescriptor((128, 128), (16, 16), (8, 8), (8, 8), 9)
        self.load_encodings()

    def load_encodings(self):
        try:
            if self.storage.key_exists(ENCODINGS_KEY):
                data = self.storage.open(ENCODINGS_KEY)
                payload = pickle.loads(data)
                if isinstance(payload, dict) and payload.get("version") == self.FORMAT_VERSION:
                    profiles = payload.get("profiles", {})
                else:
                    # O formato antigo era apenas um histograma de iluminação e
                    # não é biometricamente compatível nem seguro para reutilizar.
                    profiles = {}
                with self._lock:
                    self.encodings = profiles
                if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                    print(f"📦 Encodings carregados do storage ({len(self.encodings)} rostos)")
        except Exception as e:
            if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                print(f"⚠️ Não foi possível carregar encodings: {e}. Começando com um dicionário vazio.")
            self.encodings = {}

    def save_encodings(self):
        payload = {"version": self.FORMAT_VERSION, "profiles": self.encodings}
        data = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        self.storage.save_bytes(data, subdir="data", filename="facial_encodings.pkl")

    def processar_imagem(self, image_bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return None, "Imagem inválida"

        if img.shape[0] < 240 or img.shape[1] < 240:
            return None, "Imagem com resolução insuficiente"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detection_gray = cv2.equalizeHist(gray)
        faces = self.face_cascade.detectMultiScale(
            detection_gray, scaleFactor=1.15, minNeighbors=6,
            minSize=(100, 100), flags=cv2.CASCADE_SCALE_IMAGE
        )

        if len(faces) == 0:
            return None, "Nenhum rosto detectado"
        if len(faces) > 1:
            return None, "Mantenha apenas uma pessoa em frente à câmera"

        x, y, w, h = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
        margem_x, margem_y = int(w * .12), int(h * .12)
        x1, y1 = max(0, x - margem_x), max(0, y - margem_y)
        x2, y2 = min(gray.shape[1], x + w + margem_x), min(gray.shape[0], y + h + margem_y)
        face = gray[y1:y2, x1:x2]

        brilho = float(np.mean(face))
        nitidez = float(cv2.Laplacian(face, cv2.CV_64F).var())
        if brilho < 35:
            return None, "Ambiente muito escuro. Melhore a iluminação"
        if brilho > 225:
            return None, "Imagem muito clara. Evite luz direta na câmera"
        if nitidez < 28:
            return None, "Imagem desfocada. Fique imóvel e tente novamente"

        face_std = cv2.resize(face, (128, 128), interpolation=cv2.INTER_AREA)
        face_std = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(face_std)
        return face_std, None

    def gerar_encoding(self, face_img):
        descriptor = self._hog.compute(face_img).reshape(-1).astype(np.float32)
        norm = float(np.linalg.norm(descriptor))
        if norm == 0:
            raise ValueError("Não foi possível extrair características do rosto")
        return descriptor / norm

    def reconhecer_face(self, image_bytes):
        # Gunicorn mantém uma instância por worker. Recarregar garante que um
        # cadastro feito em outro worker fique disponível imediatamente.
        self.load_encodings()
        face_img, erro = self.processar_imagem(image_bytes)
        if erro:
            return False, erro

        descriptor = self.gerar_encoding(face_img)
        scores = []
        with self._lock:
            profiles = list(self.encodings.items())
        for cpf, descriptors in profiles:
            if not isinstance(descriptors, list):
                continue
            score = max((float(np.dot(descriptor, saved)) for saved in descriptors), default=0.0)
            scores.append((score, cpf))

        scores.sort(reverse=True)
        if scores:
            melhor_score, melhor_cpf = scores[0]
            segundo_score = scores[1][0] if len(scores) > 1 else 0.0
            if melhor_score >= self.RECOGNITION_THRESHOLD and melhor_score - segundo_score >= self.AMBIGUITY_MARGIN:
                return True, {"cpf": melhor_cpf, "confidence": round(melhor_score, 4)}
        return False, "Rosto não reconhecido"

    def cadastrar_rosto(self, cpf, image_bytes):
        face_img, erro = self.processar_imagem(image_bytes)
        if erro:
            return False, erro

        descriptor = self.gerar_encoding(face_img)
        cpf_fmt = formatar_cpf_para_busca(cpf)

        with self._lock:
            anterior = self.encodings.get(cpf_fmt)
            self.encodings[cpf_fmt] = [descriptor]
            try:
                self.save_encodings()
            except Exception:
                if anterior is None:
                    self.encodings.pop(cpf_fmt, None)
                else:
                    self.encodings[cpf_fmt] = anterior
                raise

        # Salvar a imagem do rosto no storage
        try:
            _, buffer = cv2.imencode('.jpg', face_img)
            self.storage.save_bytes(buffer.tobytes(), subdir='faces', filename=f"{cpf_fmt}.jpg")
            if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                print(f"📷 Foto do rosto de {cpf_fmt} salva no storage.")
        except Exception as e:
            if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
                print(f"❌ Erro ao salvar foto do rosto no storage: {e}")

        return True, f"Rosto cadastrado para {cpf_fmt}"

    def cpf_tem_rosto(self, cpf):
        self.load_encodings()
        descriptors = self.encodings.get(formatar_cpf_para_busca(cpf))
        return isinstance(descriptors, list) and bool(descriptors)



# ============================================================
# INSTÂNCIA GLOBAL DO SISTEMA FACIAL
# ============================================================
facial_system = None

def get_facial_system():
    global facial_system
    if facial_system is None:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print("🔄 Iniciando sistema facial...")
        facial_system = SmartFacialSystem()
    return facial_system


# ============================================================
# ROTA PRINCIPAL — BATER PONTO COM LOCALIZAÇÃO
# ============================================================
@bp_ponto.route("/bater", methods=["GET", "POST"])
def bater_ponto():
    if request.method == "GET":
        return render_template("ponto_inteligente.html")

    try:
        if "foto" not in request.files:
            return jsonify({"success": False, "error": "Nenhuma foto enviada"})

        file = request.files["foto"]
        image_bytes = file.read()

        dados_localizacao_str = request.form.get("localizacao")
        localizacao = processar_dados_localizacao(dados_localizacao_str)
        
        facial = get_facial_system()
        sucesso, resultado = facial.reconhecer_face(image_bytes)

        if sucesso:
            cpf = resultado["cpf"]
            colaborador = buscar_colaborador_por_cpf(cpf)

            if not colaborador:
                return jsonify({"success": False, "acao": "cpf_nao_encontrado", "cpf": cpf})

            agora = datetime.now()
            status = verificar_ultimo_ponto(colaborador[0], agora)

            conn = get_conn()
            cur = conn.cursor()
            localizacao_json = json.dumps(localizacao) if localizacao else None
            
            if status["tipo"] == "entrada":
                cur.execute("""
                    INSERT INTO ponto (colaborador_id, data_registro, hora_entrada,
                                       cpf, nome, tipo_registro, observacao,
                                       localizacao, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, 'entrada', %s, %s, %s, %s)
                """, (
                    colaborador[0], agora.date(), agora,
                    colaborador[3], colaborador[1],
                    status.get("motivo", ""),
                    localizacao_json,
                    localizacao["latitude"] if localizacao else None,
                    localizacao["longitude"] if localizacao else None
                ))
                msg = f"✅ Entrada registrada às {agora.strftime('%H:%M')}"

            else: # Saída
                cur.execute("""
                    UPDATE ponto
                    SET hora_saida=%s, tipo_registro='saida',
                        observacao = COALESCE(observacao,'') || ' ' || %s,
                        localizacao_saida=%s,
                        latitude_saida=%s,
                        longitude_saida=%s
                    WHERE id=%s
                """, (
                    agora, status.get("motivo", ""), localizacao_json,
                    localizacao["latitude"] if localizacao else None,
                    localizacao["longitude"] if localizacao else None,
                    status["id_ponto"]
                ))
                msg = f"✅ Saída registrada às {agora.strftime('%H:%M')}"

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "success": True, "mensagem": msg, "colaborador": colaborador[1],
                "cpf": colaborador[3], "tipo": status["tipo"],
                "localizacao_registrada": bool(localizacao)
            })

        if resultado == "Nenhum rosto detectado":
            return jsonify({"success": False, "acao": "sem_rosto", "error": resultado}), 422

        if resultado != "Rosto não reconhecido":
            return jsonify({"success": False, "acao": "foto_invalida", "error": resultado}), 422

        return jsonify({"success": False, "acao": "rosto_nao_cadastrado"})

    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro ao bater ponto: {str(e)}")
        current_app.logger.exception("Erro ao registrar ponto facial")
        return jsonify({"success": False, "error": "Não foi possível registrar o ponto. Tente novamente."}), 500

# ============================================================
# ROTA — CADASTRAR ROSTO COM CPF E LOCALIZAÇÃO
# ============================================================
@bp_ponto.route("/cadastrar-com-cpf", methods=["POST"])
def cadastrar_com_cpf():
    try:
        cpf = request.form.get("cpf")
        foto = request.files.get("foto")
        dados_localizacao_str = request.form.get("localizacao")
        localizacao = processar_dados_localizacao(dados_localizacao_str)

        if not cpf or not foto:
            return jsonify({"success": False, "error": "CPF e foto são obrigatórios"})

        colaborador = buscar_colaborador_por_cpf(cpf)
        if not colaborador:
            return jsonify({"success": False, "error": "CPF não encontrado"})

        facial = get_facial_system()
        if facial.cpf_tem_rosto(cpf):
            return jsonify({"success": False, "error": "CPF já cadastrado"})

        image_bytes = foto.read()
        sucesso, msg = facial.cadastrar_rosto(cpf, image_bytes)

        if not sucesso:
            return jsonify({"success": False, "error": msg})

        # Registrar entrada automática
        agora = datetime.now()
        localizacao_json = json.dumps(localizacao) if localizacao else None
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ponto (colaborador_id, data_registro, hora_entrada,
                               cpf, nome, tipo_registro,
                               localizacao, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, 'entrada', %s, %s, %s)
        """, (
            colaborador[0], agora.date(), agora,
            colaborador[3], colaborador[1], "Cadastro com Entrada Automática",
            localizacao_json,
            localizacao["latitude"] if localizacao else None,
            localizacao["longitude"] if localizacao else None
        ))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "mensagem": "✅ Rosto cadastrado e entrada registrada!",
            "colaborador": colaborador[1],
            "localizacao_registrada": bool(localizacao)
        })

    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro ao cadastrar com CPF: {str(e)}")
        current_app.logger.exception("Erro ao cadastrar biometria facial")
        return jsonify({"success": False, "error": "Não foi possível salvar a biometria facial."}), 500



# ============================================================
# ROTA — REGISTRO MANUAL COM LOCALIZAÇÃO (SEM PRECISÃO)
# ============================================================
@bp_ponto.route("/registrar-manual", methods=["POST"])
def registrar_manual():
    try:
        cpf = request.form.get("cpf")
        dados_localizacao_str = request.form.get("localizacao")
        localizacao = processar_dados_localizacao(dados_localizacao_str)

        if not cpf:
            return jsonify({"success": False, "error": "CPF obrigatório"})

        colaborador = buscar_colaborador_por_cpf(cpf)
        if not colaborador:
            return jsonify({"success": False, "error": "CPF não encontrado"})

        agora = datetime.now()
        status = verificar_ultimo_ponto(colaborador[0], agora)

        conn = get_conn()
        cur = conn.cursor()

        # Preparar dados de localização
        localizacao_json = json.dumps(localizacao) if localizacao else None

        if status["tipo"] == "entrada":
            cur.execute("""
                INSERT INTO ponto (colaborador_id, data_registro, hora_entrada,
                                   cpf, nome, tipo_registro,
                                   localizacao, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, 'entrada_manual', %s, %s, %s)
            """, (
                colaborador[0], agora.date(), agora,
                colaborador[3], colaborador[1],
                localizacao_json,
                localizacao["latitude"] if localizacao else None,
                localizacao["longitude"] if localizacao else None
            ))
            msg = "✅ Entrada manual registrada."
            if localizacao:
                msg += " Localização capturada."
        else:
            # CORREÇÃO AQUI: Removida a coluna precisao_saida_metros que não existe
            cur.execute("""
                UPDATE ponto
                SET hora_saida=%s, tipo_registro='saida_manual',
                    localizacao_saida=%s,
                    latitude_saida=%s,
                    longitude_saida=%s
                WHERE id=%s
            """, (
                agora,
                localizacao_json,
                localizacao["latitude"] if localizacao else None,
                localizacao["longitude"] if localizacao else None,
                status["id_ponto"]
            ))
            msg = "✅ Saída manual registrada."
            if localizacao:
                msg += " Localização capturada."

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True, 
            "mensagem": msg,
            "localizacao_registrada": bool(localizacao)
        })
        
    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro no registro manual: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


# ============================================================
# ROTA — VERIFICAR STATUS DO CPF
# ============================================================
@bp_ponto.route("/verificar-status/<cpf>", methods=["GET"])
def verificar_status(cpf):
    try:
        cpf_puro = re.sub(r"\D", "", cpf)
        colaborador = buscar_colaborador_por_cpf(cpf_puro)

        if not colaborador:
            return jsonify({
                "success": True,
                "existe_no_banco": False,
                "tem_rosto": False,
            })

        facial = get_facial_system()

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, hora_entrada, data_registro
            FROM ponto
            WHERE colaborador_id=%s AND hora_saida IS NULL
            ORDER BY data_registro DESC, hora_entrada DESC
            LIMIT 1
        """, (colaborador[0],))

        aberto = cur.fetchone()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "existe_no_banco": True,
            "tem_rosto": facial.cpf_tem_rosto(cpf_puro),
            "ponto_aberto": bool(aberto),
            "colaborador": {
                "id": colaborador[0],
                "nome": colaborador[1],
                "email": colaborador[2],
                "cpf": colaborador[3]
            }
        })
        
    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro ao verificar status: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


# Routes for statistics and diagnostics can remain as they are, as they don't handle file uploads.
# ============================================================
# ROTA — ESTATÍSTICAS
# ============================================================
@bp_ponto.route("/estatisticas")
def estatisticas():
    try:
        facial = get_facial_system()
        # This route doesn't expose sensitive paths anymore.
        return jsonify({
            "success": True,
            "rostos_cadastrados": len(facial.encodings),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============================================================
# ROTA — DIAGNÓSTICO
# ============================================================
@bp_ponto.route("/diagnostico")
def diagnostico():
    try:
        facial = get_facial_system()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM colaboradores")
        total_colab = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ponto")
        total_pontos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ponto WHERE localizacao IS NOT NULL")
        pontos_com_localizacao = cur.fetchone()[0]
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "total_colaboradores": total_colab,
            "total_pontos": total_pontos,
            "pontos_com_localizacao": pontos_com_localizacao,
            "rostos_cadastrados": len(facial.encodings),
        })
        
    except Exception as e:
        if os.environ.get('PATAGONIA_BOOT_LOGS') == '1':
            print(f"❌ Erro no diagnóstico: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


# ============================================================
# ROTA HTML
# ============================================================
@bp_ponto.route("/")
def index():
    return render_template("ponto_inteligente.html")
