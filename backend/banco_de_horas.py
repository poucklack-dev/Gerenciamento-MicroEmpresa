# banco_horas_routes.py - BANCO DE HORAS INTELIGENTE (CORRIGIDO)
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, date, time
from decimal import Decimal, ROUND_HALF_UP
import json
import traceback
from core.database import get_conn

banco_horas_bp = Blueprint("banco_horas", __name__, url_prefix="/api/banco_horas")

# ============================================================
# FUNÇÕES AUXILIARES RIGOROSAS
# ============================================================

def calcular_horas_registro(entrada, saida):
    """
    Calcula horas entre entrada e saída.
    RETORNA 0.0 se qualquer for None.
    NÃO SUPÕE NADA.
    """
    if not entrada or not saida:
        return 0.0
    
    try:
        # Se são strings, converter para datetime.time
        if isinstance(entrada, str):
            try:
                entrada = datetime.strptime(entrada, "%H:%M:%S").time()
            except:
                try:
                    entrada = datetime.strptime(entrada, "%H:%M").time()
                except:
                    return 0.0
        
        if isinstance(saida, str):
            try:
                saida = datetime.strptime(saida, "%H:%M:%S").time()
            except:
                try:
                    saida = datetime.strptime(saida, "%H:%M").time()
                except:
                    return 0.0
        
        # Se já são time objects
        if isinstance(entrada, time) and isinstance(saida, time):
            # Criar datetimes no mesmo dia
            entrada_dt = datetime.combine(date.today(), entrada)
            saida_dt = datetime.combine(date.today(), saida)
            
            # Se saída é antes da entrada, adicionar 1 dia (trabalho noturno)
            if saida_dt < entrada_dt:
                saida_dt += timedelta(days=1)
            
            delta = saida_dt - entrada_dt
            horas = delta.total_seconds() / 3600
            
            # Arredondar para 2 casas
            return float(Decimal(str(horas)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    except Exception as e:
        print(f"Erro ao calcular horas: {e}")
    
    return 0.0

def formatar_hora_para_front(hora_obj):
    """Formata hora para exibição no frontend"""
    if not hora_obj:
        return None
    
    if isinstance(hora_obj, time):
        return hora_obj.strftime("%H:%M")
    elif isinstance(hora_obj, str):
        if ':' in hora_obj:
            # Extrair apenas HH:MM
            partes = hora_obj.split(':')
            return f"{partes[0]}:{partes[1]}"
    
    return str(hora_obj)

def converter_carga_para_horas(valor):
    """Converte carga (HH:MM ou float) para horas decimais - SEM SUPOR NADA"""
    if valor is None:
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)
    
    valor_str = str(valor).strip()
    
    if valor_str == "":
        return 0.0
    
    if ":" in valor_str:
        try:
            partes = valor_str.split(":")
            horas = int(partes[0])
            minutos = int(partes[1]) if len(partes) > 1 else 0
            return horas + (minutos / 60.0)
        except:
            return 0.0
    else:
        try:
            return float(valor_str)
        except:
            return 0.0

def formatar_horas_para_exibicao(horas_decimais):
    """Formata horas decimais para HH:MM ou decimal"""
    if horas_decimais is None:
        return "0.0"
    
    try:
        horas = float(horas_decimais)
        # Se for inteiro ou com .0, mostra como decimal simples
        if horas.is_integer():
            return f"{int(horas)}.0"
        else:
            # Converte para HH:MM
            horas_int = int(horas)
            minutos = int((horas - horas_int) * 60)
            return f"{horas_int:02d}:{minutos:02d}"
    except:
        return "0.0"

# ============================================================
# 1. ENDPOINT: LISTAR COLABORADORES (CORRIGIDO PARA SUA ESTRUTURA)
# ============================================================

@banco_horas_bp.get("/colaboradores")
def get_colaboradores():
    """Retorna lista de colaboradores ativos para select - CORRIGIDO"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Usando a estrutura REAL da sua tabela colaboradores
        # Campos mínimos necessários: id, nome, cargo, status, cpf, matricula
        cur.execute("""
            SELECT 
                id, 
                nome, 
                cargo, 
                status, 
                cpf 
            FROM colaboradores 
            WHERE status = 'ativo'
            ORDER BY nome
        """)
        
        rows = cur.fetchall()
        colaboradores = []
        
        for r in rows:
            colaboradores.append({
                "id": r[0],
                "nome": r[1] or "Sem nome",
                "cargo": r[2] or "Sem cargo",
                "status": r[3] or "ativo",
                "cpf": r[4],
            })
        
        cur.close()
        conn.close()
        
        return jsonify(colaboradores), 200
        
    except Exception as e:
        print(f"Erro ao buscar colaboradores: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 2. ENDPOINT PRINCIPAL: BANCO DE HORAS DIÁRIO
# ============================================================

@banco_horas_bp.post("/saldo-diario")
def calcular_saldo_diario():
    """
    Calcula saldo de horas por dia SEM NENHUMA SUPOSIÇÃO.
    REGRAS ABSOLUTAS:
    1. Nunca usar "8h/dia" como padrão
    2. Nunca preencher lacunas
    3. Nunca estimar ou inferir dias úteis
    4. Tudo deve ser explícito: registro real ou configuração manual
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validar campos obrigatórios
        obrigatorios = ["colaborador_id", "inicio", "fim", "carga_base_diaria"]
        for campo in obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório faltando: {campo}"}), 400
        
        # Validar datas
        try:
            inicio = datetime.strptime(dados["inicio"], "%Y-%m-%d").date()
            fim = datetime.strptime(dados["fim"], "%Y-%m-%d").date()
        except:
            return jsonify({"erro": "Datas inválidas. Use YYYY-MM-DD"}), 400
        
        if fim < inicio:
            return jsonify({"erro": "Data fim não pode ser anterior à data início"}), 400
        
        # Validar carga base diária
        carga_base_horas = converter_carga_para_horas(dados["carga_base_diaria"])
        if carga_base_horas < 0:
            return jsonify({"erro": "Carga base não pode ser negativa"}), 400
        
        # Validar dias excluídos
        dias_excluidos = dados.get("dias_excluidos", [])
        if not isinstance(dias_excluidos, list):
            return jsonify({"erro": "dias_excluidos deve ser uma lista de datas"}), 400
        
        dias_excluidos_validos = []
        for data_str in dias_excluidos:
            try:
                data_excluida = datetime.strptime(data_str, "%Y-%m-%d").date()
                if inicio <= data_excluida <= fim:
                    dias_excluidos_validos.append(data_str)
            except:
                pass  # Ignora datas inválidas
        
        # Validar overrides
        overrides = dados.get("overrides", {})
        if not isinstance(overrides, dict):
            return jsonify({"erro": "overrides deve ser um objeto {data: carga}"}), 400
        
        overrides_validos = {}
        for data_str, carga_override in overrides.items():
            try:
                data_override = datetime.strptime(data_str, "%Y-%m-%d").date()
                if inicio <= data_override <= fim:
                    carga_horas = converter_carga_para_horas(carga_override)
                    if carga_horas >= 0:
                        overrides_validos[data_str] = carga_horas
            except:
                pass  # Ignora datas inválidas
        
        # Buscar informações do colaborador
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, nome, cargo, status
            FROM colaboradores 
            WHERE id = %s
        """, (dados["colaborador_id"],))
        
        colab_info = cur.fetchone()
        if not colab_info:
            cur.close()
            conn.close()
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # Buscar TODOS os registros do período
        # AJUSTE: Verificar o nome correto da tabela de ponto
        cur.execute("""
            SELECT 
                id,
                data_registro,
                hora_entrada,
                hora_saida,
                tipo_registro,
                observacao
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro BETWEEN %s AND %s
            ORDER BY data_registro, 
                CASE WHEN hora_entrada IS NOT NULL THEN 0 ELSE 1 END,
                hora_entrada
        """, (dados["colaborador_id"], inicio, fim))
        
        registros_brutos = cur.fetchall()
        cur.close()
        conn.close()
        
        # Organizar registros por data
        registros_por_data = {}
        for reg in registros_brutos:
            reg_id, data_reg, entrada, saida, tipo, obs = reg
            data_str = data_reg.strftime("%Y-%m-%d")
            
            if data_str not in registros_por_data:
                registros_por_data[data_str] = []
            
            registros_por_data[data_str].append({
                "id": reg_id,
                "entrada": entrada,
                "saida": saida,
                "tipo": tipo or "normal",
                "observacao": obs or ""
            })
        
        # DIAS DA SEMANA CORRETOS: Seg, Ter, Qua, Qui, Sex, Sáb, Dom
        dias_semana_abreviados = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        dias_semana_completos = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        
        # Processar cada dia do período
        dias_resultado = []
        horas_trabalhadas_total = 0.0
        carga_total_calculada = 0.0
        registros_completos_total = 0
        registros_incompletos_total = 0
        
        data_atual = inicio
        while data_atual <= fim:
            data_str = data_atual.strftime("%Y-%m-%d")
            dia_semana_num = data_atual.weekday()  # 0=Segunda, 6=Domingo
            
            # 1. Determinar se o dia está incluído na carga
            incluido_na_carga = data_str not in dias_excluidos_validos
            
            # 2. Determinar carga do dia
            if data_str in overrides_validos:
                carga_dia = overrides_validos[data_str]
            else:
                carga_dia = carga_base_horas if incluido_na_carga else 0.0
            
            # 3. Calcular horas trabalhadas no dia
            horas_trabalhadas_dia = 0.0
            incompletos_dia = 0
            registros_dia = []
            
            if data_str in registros_por_data:
                for reg in registros_por_data[data_str]:
                    tem_entrada = reg["entrada"] is not None
                    tem_saida = reg["saida"] is not None
                    
                    if tem_entrada and tem_saida:
                        # Registro COMPLETO - calcular horas
                        horas_reg = calcular_horas_registro(reg["entrada"], reg["saida"])
                        horas_trabalhadas_dia += horas_reg
                        registros_completos_total += 1
                        status_reg = "completo"
                    else:
                        # Registro INCOMPLETO - NÃO calcular horas
                        horas_reg = 0.0
                        incompletos_dia += 1
                        registros_incompletos_total += 1
                        if tem_entrada and not tem_saida:
                            status_reg = "sem_saida"
                        elif not tem_entrada and tem_saida:
                            status_reg = "sem_entrada"
                        else:
                            status_reg = "vazio"
                    
                    registros_dia.append({
                        "id": reg["id"],
                        "entrada": formatar_hora_para_front(reg["entrada"]),
                        "saida": formatar_hora_para_front(reg["saida"]),
                        "horas": round(horas_reg, 2),
                        "status": status_reg,
                        "tipo": reg["tipo"],
                        "observacao": reg["observacao"]
                    })
            
            # 4. Calcular saldo do dia
            saldo_dia = horas_trabalhadas_dia - carga_dia
            
            # 5. Acumular totais
            horas_trabalhadas_total += horas_trabalhadas_dia
            if incluido_na_carga:
                carga_total_calculada += carga_dia
            
            # 6. Adicionar informações do dia
            dias_resultado.append({
                "data": data_str,
                "dia_semana": dias_semana_abreviados[dia_semana_num],
                "dia_semana_completo": dias_semana_completos[dia_semana_num],
                "incluido_na_carga": incluido_na_carga,
                "carga_dia": round(carga_dia, 2),
                "horas_trabalhadas": round(horas_trabalhadas_dia, 2),
                "saldo_dia": round(saldo_dia, 2),
                "incompletos": incompletos_dia,
                "registros": registros_dia,
                "tem_registro": data_str in registros_por_data
            })
            
            data_atual += timedelta(days=1)
        
        # Calcular saldo total
        saldo_total = horas_trabalhadas_total - carga_total_calculada
        
        # Formatar resposta
        dias_totais = (fim - inicio).days + 1
        dias_incluidos = sum(1 for d in dias_resultado if d["incluido_na_carga"])
        
        resposta = {
            "colaborador": {
                "id": colab_info[0],
                "nome": colab_info[1] or "Sem nome",
                "cargo": colab_info[2] or "Sem cargo",
                "status": colab_info[3] or "ativo",
            },
            "periodo": {
                "inicio": inicio.strftime("%Y-%m-%d"),
                "fim": fim.strftime("%Y-%m-%d"),
                "dias_totais": dias_totais,
                "dias_incluidos_na_carga": dias_incluidos
            },
            "inputs": {
                "carga_base_diaria": round(carga_base_horas, 2),
                "carga_base_diaria_formatada": formatar_horas_para_exibicao(carga_base_horas),
                "dias_excluidos": dias_excluidos_validos,
                "overrides": {k: round(v, 2) for k, v in overrides_validos.items()}
            },
            "totais": {
                "horas_trabalhadas": round(horas_trabalhadas_total, 2),
                "carga_calculada": round(carga_total_calculada, 2),
                "saldo": round(saldo_total, 2),
                "registros_completos": registros_completos_total,
                "registros_incompletos": registros_incompletos_total
            },
            "dias": dias_resultado,
            "observacoes": [
                "Horas calculadas apenas com registros completos (entrada + saída).",
                "Registros incompletos (sem entrada ou sem saída) não entram no cálculo de horas.",
                "Carga esperada é soma diária configurada (base + overrides - exclusões).",
                "Nenhuma suposição de jornada, dias úteis ou preenchimento de lacunas.",
                "Dias excluídos têm carga = 0 e não entram no total de carga.",
                "Overrides substituem a carga base apenas no dia específico."
            ]
        }
        
        return jsonify(resposta), 200
        
    except Exception as e:
        print(f"Erro no saldo-diario: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 3. ENDPOINT DASHBOARD
# ============================================================

@banco_horas_bp.get("/dashboard")
def get_dashboard():
    """Dashboard com dados REAIS do banco de horas"""
    try:
        periodo = request.args.get("periodo", "semana")
        hoje = date.today()
        
        # Definir datas baseado no período
        if periodo == "hoje":
            inicio = hoje
            fim = hoje
        elif periodo == "semana":
            inicio = hoje - timedelta(days=hoje.weekday())
            fim = hoje
        elif periodo == "mes":
            inicio = date(hoje.year, hoje.month, 1)
            if hoje.month == 12:
                fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
            else:
                fim = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)
        elif periodo == "trimestre":
            trimestre = (hoje.month - 1) // 3
            inicio = date(hoje.year, trimestre * 3 + 1, 1)
            if trimestre == 3:  # Outubro, Novembro, Dezembro
                fim = date(hoje.year + 1, 1, 1) - timedelta(days=1)
            else:
                fim = date(hoje.year, trimestre * 3 + 4, 1) - timedelta(days=1)
        else:
            return jsonify({"erro": "Período inválido. Use: hoje, semana, mes, trimestre"}), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        # 1. TOTAL DE COLABORADORES ATIVOS
        cur.execute("SELECT COUNT(*) FROM colaboradores WHERE status = 'ativo'")
        total_colaboradores = cur.fetchone()[0] or 0
        
        # 2. COLABORADORES COM REGISTRO HOJE
        cur.execute("""
            SELECT COUNT(DISTINCT colaborador_id)
            FROM ponto
            WHERE data_registro = %s
            AND (hora_entrada IS NOT NULL OR hora_saida IS NOT NULL)
        """, (hoje,))
        com_registro_hoje = cur.fetchone()[0] or 0
        
        # 3. HORAS TRABALHADAS NO PERÍODO
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                    ELSE 0 
                END
            ), 0)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
        """, (inicio, fim))
        total_horas = float(cur.fetchone()[0] or 0)
        
        # 4. REGISTROS INCOMPLETOS NO PERÍODO
        cur.execute("""
            SELECT COUNT(*)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
            AND (hora_entrada IS NULL OR hora_saida IS NULL)
            AND NOT (hora_entrada IS NULL AND hora_saida IS NULL)
        """, (inicio, fim))
        registros_incompletos = cur.fetchone()[0] or 0
        
        # 5. TOTAL DE REGISTROS NO PERÍODO
        cur.execute("""
            SELECT COUNT(*)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
        """, (inicio, fim))
        total_registros = cur.fetchone()[0] or 0
        
        # 6. TOP 5 COLABORADORES POR HORAS
        cur.execute("""
            SELECT 
                c.id,
                c.nome,
                c.cargo,
                c.status,
                COALESCE(SUM(
                    CASE 
                        WHEN p.hora_entrada IS NOT NULL AND p.hora_saida IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (p.hora_saida - p.hora_entrada)) / 3600
                        ELSE 0 
                    END
                ), 0) as total_horas
            FROM colaboradores c
            LEFT JOIN ponto p ON c.id = p.colaborador_id 
                AND p.data_registro BETWEEN %s AND %s
            WHERE c.status = 'ativo'
            GROUP BY c.id, c.nome, c.cargo, c.status
            HAVING COALESCE(SUM(
                CASE 
                    WHEN p.hora_entrada IS NOT NULL AND p.hora_saida IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (p.hora_saida - p.hora_entrada)) / 3600
                    ELSE 0 
                END
            ), 0) > 0
            ORDER BY total_horas DESC
            LIMIT 5
        """, (inicio, fim))
        
        top_colaboradores = []
        for row in cur.fetchall():
            top_colaboradores.append({
                "id": row[0],
                "nome": row[1] or "Sem nome",
                "cargo": row[2] or "Sem cargo",
                "status": row[3] or "ativo",
                "horas": round(float(row[4] or 0), 1)
            })
        
        # 7. ÚLTIMOS 7 DIAS DE REGISTROS
        dias_semana_abreviados = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        ultimos_7_dias = []
        
        for i in range(6, -1, -1):
            data_ref = hoje - timedelta(days=i)
            
            # Registros completos do dia
            cur.execute("""
                SELECT COUNT(*)
                FROM ponto
                WHERE data_registro = %s
                AND hora_entrada IS NOT NULL
                AND hora_saida IS NOT NULL
            """, (data_ref,))
            registros_dia = cur.fetchone()[0] or 0
            
            # Horas do dia
            cur.execute("""
                SELECT COALESCE(SUM(
                    EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                ), 0)
                FROM ponto
                WHERE data_registro = %s
                AND hora_entrada IS NOT NULL
                AND hora_saida IS NOT NULL
            """, (data_ref,))
            horas_dia = float(cur.fetchone()[0] or 0)
            
            ultimos_7_dias.append({
                "data": data_ref.strftime("%Y-%m-%d"),
                "data_formatada": data_ref.strftime("%d/%m"),
                "dia_semana": dias_semana_abreviados[data_ref.weekday()],
                "registros": registros_dia,
                "horas": round(horas_dia, 1),
                "tem_registro": registros_dia > 0
            })
        
        cur.close()
        conn.close()
        
        # Calcular estatísticas
        dias_periodo = (fim - inicio).days + 1
        media_horas = round(total_horas / max(1, total_colaboradores), 1) if total_colaboradores > 0 else 0
        dias_com_registro = len([d for d in ultimos_7_dias if d["tem_registro"]])
        
        return jsonify({
            "periodo": periodo,
            "datas": {
                "inicio": inicio.strftime("%Y-%m-%d"),
                "fim": fim.strftime("%Y-%m-%d"),
                "dias_totais": dias_periodo
            },
            "estatisticas": {
                "total_colaboradores": total_colaboradores,
                "colaboradores_com_registro_hoje": com_registro_hoje,
                "total_horas_periodo": round(total_horas, 1),
                "media_horas_por_colaborador": media_horas,
                "registros_incompletos": registros_incompletos,
                "total_registros_periodo": total_registros,
                "dias_com_registro_7dias": dias_com_registro
            },
            "top_colaboradores": top_colaboradores,
            "evolucao_7_dias": ultimos_7_dias,
            "observacoes": [
                "Todos os dados são baseados em registros reais de ponto",
                "Horas calculadas apenas de registros completos (entrada + saída)",
                "Nenhuma suposição de jornada padrão",
                "Dias sem registros não são considerados"
            ]
        }), 200
        
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 4. ENDPOINT RESUMO COLABORADOR
# ============================================================

@banco_horas_bp.get("/colaborador/<int:colab_id>/resumo")
def get_resumo_colaborador(colab_id):
    """Resumo completo de um colaborador"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Informações básicas do colaborador
        cur.execute("""
            SELECT id, nome, cargo, status, cpf, data_admissao
            FROM colaboradores 
            WHERE id = %s
        """, (colab_id,))
        
        colab_info = cur.fetchone()
        if not colab_info:
            cur.close()
            conn.close()
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # Hoje
        hoje = date.today()
        
        # 1. Dados de HOJE
        cur.execute("""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL THEN 1 END) as completos,
                COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NULL THEN 1 END) as sem_saida,
                COUNT(CASE WHEN hora_entrada IS NULL AND hora_saida IS NOT NULL THEN 1 END) as sem_entrada,
                COALESCE(SUM(
                    CASE 
                        WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                        ELSE 0 
                    END
                ), 0) as horas
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro = %s
        """, (colab_id, hoje))
        
        hoje_data = cur.fetchone()
        
        # 2. Dados da SEMANA
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        cur.execute("""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL THEN 1 END) as completos,
                COALESCE(SUM(
                    CASE 
                        WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                        ELSE 0 
                    END
                ), 0) as horas,
                COUNT(DISTINCT data_registro) as dias_com_registro
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro BETWEEN %s AND %s
            AND hora_entrada IS NOT NULL
            AND hora_saida IS NOT NULL
        """, (colab_id, inicio_semana, hoje))
        
        semana_data = cur.fetchone()
        
        # 3. Dados do MÊS
        inicio_mes = date(hoje.year, hoje.month, 1)
        cur.execute("""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL THEN 1 END) as completos,
                COALESCE(SUM(
                    CASE 
                        WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                        ELSE 0 
                    END
                ), 0) as horas,
                COUNT(DISTINCT data_registro) as dias_com_registro
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro BETWEEN %s AND %s
            AND hora_entrada IS NOT NULL
            AND hora_saida IS NOT NULL
        """, (colab_id, inicio_mes, hoje))
        
        mes_data = cur.fetchone()
        
        # 4. Últimos 7 dias (detalhado)
        dias_semana_abreviados = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        ultimos_7_dias = []
        
        for i in range(6, -1, -1):
            data_ref = hoje - timedelta(days=i)
            
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL THEN 1 END) as completos,
                    COUNT(CASE WHEN hora_entrada IS NOT NULL AND hora_saida IS NULL THEN 1 END) as sem_saida,
                    COUNT(CASE WHEN hora_entrada IS NULL AND hora_saida IS NOT NULL THEN 1 END) as sem_entrada,
                    COALESCE(SUM(
                        CASE 
                            WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                            THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                            ELSE 0 
                        END
                    ), 0) as horas
                FROM ponto
                WHERE colaborador_id = %s 
                AND data_registro = %s
            """, (colab_id, data_ref))
            
            dia_data = cur.fetchone()
            
            ultimos_7_dias.append({
                "data": data_ref.strftime("%Y-%m-%d"),
                "data_formatada": data_ref.strftime("%d/%m"),
                "dia_semana": dias_semana_abreviados[data_ref.weekday()],
                "completos": dia_data[0] or 0,
                "sem_saida": dia_data[1] or 0,
                "sem_entrada": dia_data[2] or 0,
                "horas": round(float(dia_data[3] or 0), 1),
                "tem_registro": (dia_data[0] or 0) > 0 or (dia_data[1] or 0) > 0 or (dia_data[2] or 0) > 0
            })
        
        # 5. Média histórica (últimos 30 dias)
        inicio_30_dias = hoje - timedelta(days=30)
        cur.execute("""
            SELECT 
                COUNT(DISTINCT data_registro) as dias_com_registro,
                COALESCE(SUM(
                    CASE 
                        WHEN hora_entrada IS NOT NULL AND hora_saida IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (hora_saida - hora_entrada)) / 3600
                        ELSE 0 
                    END
                ), 0) as total_horas
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro BETWEEN %s AND %s
        """, (colab_id, inicio_30_dias, hoje))
        
        historico_data = cur.fetchone()
        
        # 6. Total de registros incompletos (histórico)
        cur.execute("""
            SELECT COUNT(*)
            FROM ponto
            WHERE colaborador_id = %s
            AND (hora_entrada IS NULL OR hora_saida IS NULL)
            AND NOT (hora_entrada IS NULL AND hora_saida IS NULL)
        """, (colab_id,))
        
        total_incompletos = cur.fetchone()[0] or 0
        
        cur.close()
        conn.close()
        
        # Calcular médias
        dias_semana = (hoje - inicio_semana).days + 1
        media_semana = round(float(semana_data[2] or 0) / max(1, semana_data[3] or 1), 1) if semana_data else 0
        
        dias_mes = (hoje - inicio_mes).days + 1
        media_mes = round(float(mes_data[2] or 0) / max(1, mes_data[3] or 1), 1) if mes_data else 0
        
        media_30_dias = 0
        if historico_data and historico_data[0] > 0:
            media_30_dias = round(float(historico_data[1] or 0) / historico_data[0], 1)
        
        return jsonify({
            "colaborador": {
                "id": colab_info[0],
                "nome": colab_info[1] or "Sem nome",
                "cargo": colab_info[2] or "Sem cargo",
                "status": colab_info[3] or "ativo",
                "cpf": colab_info[4],
                "data_admissao": str(colab_info[6]) if colab_info[6] else None
            },
            "resumos": {
                "hoje": {
                    "total_registros": hoje_data[0] or 0,
                    "registros_completos": hoje_data[1] or 0,
                    "registros_sem_saida": hoje_data[2] or 0,
                    "registros_sem_entrada": hoje_data[3] or 0,
                    "horas": round(float(hoje_data[4] or 0), 1),
                    "tem_registro": hoje_data[0] > 0
                },
                "semana": {
                    "total_registros": semana_data[0] or 0,
                    "registros_completos": semana_data[1] or 0,
                    "horas": round(float(semana_data[2] or 0), 1),
                    "dias_com_registro": semana_data[3] or 0,
                    "dias_totais": dias_semana,
                    "media_diaria": media_semana,
                    "inicio": inicio_semana.strftime("%Y-%m-%d"),
                    "fim": hoje.strftime("%Y-%m-%d")
                },
                "mes": {
                    "total_registros": mes_data[0] or 0,
                    "registros_completos": mes_data[1] or 0,
                    "horas": round(float(mes_data[2] or 0), 1),
                    "dias_com_registro": mes_data[3] or 0,
                    "dias_totais": dias_mes,
                    "media_diaria": media_mes,
                    "inicio": inicio_mes.strftime("%Y-%m-%d"),
                    "fim": hoje.strftime("%Y-%m-%d")
                },
                "historico_30_dias": {
                    "dias_com_registro": historico_data[0] or 0,
                    "total_horas": round(float(historico_data[1] or 0), 1),
                    "media_diaria": media_30_dias,
                    "inicio": inicio_30_dias.strftime("%Y-%m-%d"),
                    "fim": hoje.strftime("%Y-%m-%d")
                },
                "total_incompletos": total_incompletos
            },
            "evolucao_7_dias": ultimos_7_dias,
            "observacoes": [
                "Dados baseados exclusivamente em registros reais de ponto",
                "Horas calculadas apenas de registros completos (entrada + saída)",
                "Nenhuma suposição de jornada padrão",
                "Registros incompletos não entram no cálculo de horas"
            ]
        }), 200
        
    except Exception as e:
        print(f"Erro no resumo colaborador: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 5. ENDPOINT RELATÓRIO DIÁRIO
# ============================================================

@banco_horas_bp.get("/diario/<int:colab_id>/<string:data>")
def relatorio_diario(colab_id, data):
    """Relatório diário baseado APENAS em registros reais"""
    try:
        # Converter data
        try:
            data_ref = datetime.strptime(data, "%Y-%m-%d").date()
        except:
            return jsonify({"erro": "Data inválida. Use YYYY-MM-DD"}), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        # 1. Buscar informações do colaborador
        cur.execute("""
            SELECT nome, cargo FROM colaboradores WHERE id = %s
        """, (colab_id,))
        colab_info = cur.fetchone()
        
        if not colab_info:
            cur.close()
            conn.close()
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # 2. Buscar TODOS os registros do dia
        cur.execute("""
            SELECT 
                id,
                hora_entrada,
                hora_saida,
                tipo_registro,
                observacao
            FROM ponto
            WHERE colaborador_id = %s 
            AND data_registro = %s
            ORDER BY 
                CASE WHEN hora_entrada IS NOT NULL THEN 0 ELSE 1 END,
                hora_entrada
        """, (colab_id, data_ref))
        
        registros_brutos = cur.fetchall()
        cur.close()
        conn.close()
        
        # 3. Processar registros com regras rigorosas
        registros_processados = []
        total_horas = 0.0
        registros_completos = 0
        registros_incompletos = 0
        
        for reg in registros_brutos:
            reg_id, entrada, saida, tipo, obs = reg
            
            # Determinar status do registro
            tem_entrada = entrada is not None
            tem_saida = saida is not None
            
            if tem_entrada and tem_saida:
                # Registro COMPLETO - calcular horas
                horas = calcular_horas_registro(entrada, saida)
                total_horas += horas
                registros_completos += 1
                status = "completo"
                status_badge = "badge-success"
                status_text = "Completo"
            elif tem_entrada and not tem_saida:
                # Só tem entrada - NÃO calcular
                horas = 0.0
                registros_incompletos += 1
                status = "sem_saida"
                status_badge = "badge-warning"
                status_text = "Sem saída"
            elif not tem_entrada and tem_saida:
                # Só tem saída - NÃO calcular
                horas = 0.0
                registros_incompletos += 1
                status = "sem_entrada"
                status_badge = "badge-danger"
                status_text = "Sem entrada"
            else:
                # Sem entrada nem saída
                horas = 0.0
                status = "vazio"
                status_badge = "badge-neutral"
                status_text = "Vazio"
            
            registros_processados.append({
                "id": reg_id,
                "entrada": formatar_hora_para_front(entrada),
                "saida": formatar_hora_para_front(saida),
                "horas": round(horas, 2),
                "status": status,
                "status_badge": status_badge,
                "status_text": status_text,
                "tipo": tipo or "normal",
                "observacao": obs or ""
            })
        
        # 4. Preparar resposta
        dias_semana_completos = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        dia_semana = dias_semana_completos[data_ref.weekday()]
        
        resposta = {
            "colaborador": {
                "id": colab_id,
                "nome": colab_info[0],
                "cargo": colab_info[1]
            },
            "data": data,
            "dia_semana": dia_semana,
            "total_horas": round(total_horas, 2),
            "resumo": {
                "registros_completos": registros_completos,
                "registros_incompletos": registros_incompletos,
                "total_registros": len(registros_brutos),
                "tem_registro": len(registros_brutos) > 0
            },
            "registros": registros_processados,
            "observacao": "Cálculo baseado apenas em registros completos (entrada + saída). Registros incompletos não entram no total de horas."
        }
        
        return jsonify(resposta), 200
        
    except Exception as e:
        print(f"Erro no relatório diário: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 6. ENDPOINTS DE EDIÇÃO E EXCLUSÃO DE REGISTROS
# ============================================================

@banco_horas_bp.patch("/registro/<int:registro_id>")
def editar_registro(registro_id):
    """Edita um registro específico"""
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validar campos
        hora_entrada = dados.get('hora_entrada')
        hora_saida = dados.get('hora_saida')
        
        # Se fornecido, validar formato HH:MM
        if hora_entrada is not None:
            if hora_entrada != "":
                try:
                    # Aceita HH:MM ou HH:MM:SS
                    if len(hora_entrada) == 5:
                        datetime.strptime(hora_entrada, "%H:%M")
                    else:
                        datetime.strptime(hora_entrada, "%H:%M:%S")
                except:
                    return jsonify({"erro": "Formato de hora_entrada inválido. Use HH:MM ou HH:MM:SS"}), 400
        
        if hora_saida is not None:
            if hora_saida != "":
                try:
                    if len(hora_saida) == 5:
                        datetime.strptime(hora_saida, "%H:%M")
                    else:
                        datetime.strptime(hora_saida, "%H:%M:%S")
                except:
                    return jsonify({"erro": "Formato de hora_saida inválido. Use HH:MM ou HH:MM:SS"}), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Verificar se registro existe
        cur.execute("""
            SELECT id, colaborador_id, data_registro 
            FROM ponto WHERE id = %s
        """, (registro_id,))
        
        registro = cur.fetchone()
        if not registro:
            cur.close()
            conn.close()
            return jsonify({"erro": "Registro não encontrado"}), 404
        
        # Atualizar
        update_fields = []
        params = []
        
        if hora_entrada is not None:
            update_fields.append("hora_entrada = %s")
            params.append(hora_entrada if hora_entrada != "" else None)
        
        if hora_saida is not None:
            update_fields.append("hora_saida = %s")
            params.append(hora_saida if hora_saida != "" else None)
        
        if not update_fields:
            cur.close()
            conn.close()
            return jsonify({"erro": "Nenhum campo para atualizar"}), 400
        
        params.append(registro_id)
        
        query = f"""
            UPDATE ponto 
            SET {', '.join(update_fields)}, 
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, hora_entrada, hora_saida, data_registro, colaborador_id
        """
        
        cur.execute(query, tuple(params))
        updated = cur.fetchone()
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "mensagem": "Registro atualizado com sucesso",
            "registro": {
                "id": updated[0],
                "hora_entrada": updated[1],
                "hora_saida": updated[2],
                "data": str(updated[3]),
                "colaborador_id": updated[4]
            },
            "recalculo_recomendado": True
        }), 200
        
    except Exception as e:
        print(f"Erro ao editar registro: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

@banco_horas_bp.delete("/registro/<int:registro_id>")
def excluir_registro(registro_id):
    """Exclui um registro específico"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Verificar se registro existe
        cur.execute("""
            SELECT id, colaborador_id, data_registro 
            FROM ponto WHERE id = %s
        """, (registro_id,))
        
        registro = cur.fetchone()
        if not registro:
            cur.close()
            conn.close()
            return jsonify({"erro": "Registro não encontrado"}), 404
        
        # Excluir registro
        cur.execute("DELETE FROM ponto WHERE id = %s", (registro_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "mensagem": "Registro excluído com sucesso",
            "registro_excluido": {
                "id": registro[0],
                "colaborador_id": registro[1],
                "data": str(registro[2])
            },
            "recalculo_recomendado": True
        }), 200
        
    except Exception as e:
        print(f"Erro ao excluir registro: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 7. ENDPOINT ADICIONAR REGISTRO
# ============================================================

@banco_horas_bp.post("/registro")
def adicionar_registro():
    """Adiciona um novo registro de ponto"""
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validar campos obrigatórios
        obrigatorios = ["colaborador_id", "data_registro"]
        for campo in obrigatorios:
            if campo not in dados:
                return jsonify({"erro": f"Campo obrigatório faltando: {campo}"}), 400
        
        # Validar data
        try:
            data_registro = datetime.strptime(dados["data_registro"], "%Y-%m-%d").date()
        except:
            return jsonify({"erro": "Data inválida. Use YYYY-MM-DD"}), 400
        
        # Validar horas se fornecidas
        hora_entrada = dados.get("hora_entrada")
        hora_saida = dados.get("hora_saida")
        
        if hora_entrada:
            try:
                datetime.strptime(hora_entrada, "%H:%M")
            except:
                return jsonify({"erro": "Formato de hora_entrada inválido. Use HH:MM"}), 400
        
        if hora_saida:
            try:
                datetime.strptime(hora_saida, "%H:%M")
            except:
                return jsonify({"erro": "Formato de hora_saida inválido. Use HH:MM"}), 400
        
        # Validar que saída é depois da entrada
        if hora_entrada and hora_saida and hora_entrada >= hora_saida:
            return jsonify({"erro": "Hora de saída deve ser após hora de entrada"}), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Verificar se colaborador existe
        cur.execute("SELECT id FROM colaboradores WHERE id = %s", (dados["colaborador_id"],))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"erro": "Colaborador não encontrado"}), 404
        
        # Inserir registro
        cur.execute("""
            INSERT INTO ponto (
                colaborador_id,
                data_registro,
                hora_entrada,
                hora_saida,
                tipo_registro,
                observacao,
                data_criacao,
                data_atualizacao
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, hora_entrada, hora_saida, data_registro, colaborador_id
        """, (
            dados["colaborador_id"],
            data_registro,
            hora_entrada if hora_entrada else None,
            hora_saida if hora_saida else None,
            dados.get("tipo_registro", "normal"),
            dados.get("observacao", "")
        ))
        
        novo_registro = cur.fetchone()
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "mensagem": "Registro adicionado com sucesso",
            "registro": {
                "id": novo_registro[0],
                "hora_entrada": novo_registro[1],
                "hora_saida": novo_registro[2],
                "data": str(novo_registro[3]),
                "colaborador_id": novo_registro[4]
            },
            "recalculo_recomendado": True
        }), 201
        
    except Exception as e:
        print(f"Erro ao adicionar registro: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 8. ENDPOINT BUSCAR REGISTRO ESPECÍFICO
# ============================================================

@banco_horas_bp.get("/registro/<int:registro_id>")
def buscar_registro(registro_id):
    """Busca um registro específico para edição"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                id,
                colaborador_id,
                data_registro,
                hora_entrada,
                hora_saida,
                tipo_registro,
                observacao
            FROM ponto 
            WHERE id = %s
        """, (registro_id,))
        
        registro = cur.fetchone()
        cur.close()
        conn.close()
        
        if not registro:
            return jsonify({"erro": "Registro não encontrado"}), 404
        
        return jsonify({
            "id": registro[0],
            "colaborador_id": registro[1],
            "data": str(registro[2]),
            "hora_entrada": registro[3],
            "hora_saida": registro[4],
            "tipo_registro": registro[5],
            "observacao": registro[6] or ""
        }), 200
        
    except Exception as e:
        print(f"Erro ao buscar registro: {e}")
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# ============================================================
# 9. ENDPOINT DE STATUS
# ============================================================

@banco_horas_bp.get("/status")
def status():
    """Endpoint de status do serviço"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Verificar conexão com banco
        cur.execute("SELECT COUNT(*) FROM ponto LIMIT 1")
        total_registros = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM colaboradores WHERE status = 'ativo'")
        total_colaboradores = cur.fetchone()[0] or 0
        
        cur.execute("SELECT MAX(data_registro) FROM ponto")
        ultimo_registro = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "online",
            "modo": "dados_reais",
            "database": {
                "total_registros": total_registros,
                "total_colaboradores_ativos": total_colaboradores,
                "ultimo_registro": str(ultimo_registro) if ultimo_registro else None
            },
            "regras": [
                "Não supõe jornada padrão",
                "Não cria horas estimadas",
                "Não preenche lacunas",
                "Só calcula com entrada+saída",
                "Nenhuma suposição - apenas dados reais"
            ],
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"Erro no status: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "erro": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ============================================================
# 10. ENDPOINT TESTE DE DADOS
# ============================================================

@banco_horas_bp.get("/teste-dados")
def teste_dados():
    """Endpoint para testar se há dados no sistema"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Dados gerais
        cur.execute("SELECT COUNT(*) FROM colaboradores")
        total_colab = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM colaboradores WHERE status = 'ativo'")
        ativos = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM ponto")
        total_pontos = cur.fetchone()[0] or 0
        
        # Últimos 7 dias
        hoje = date.today()
        inicio_7_dias = hoje - timedelta(days=6)
        
        cur.execute("""
            SELECT COUNT(DISTINCT colaborador_id)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
            AND hora_entrada IS NOT NULL
        """, (inicio_7_dias, hoje))
        colaboradores_com_registro_7d = cur.fetchone()[0] or 0
        
        cur.execute("""
            SELECT COUNT(*)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
            AND hora_entrada IS NOT NULL
            AND hora_saida IS NOT NULL
        """, (inicio_7_dias, hoje))
        registros_completos_7d = cur.fetchone()[0] or 0
        
        cur.execute("""
            SELECT COUNT(*)
            FROM ponto
            WHERE data_registro BETWEEN %s AND %s
            AND (hora_entrada IS NULL OR hora_saida IS NULL)
            AND NOT (hora_entrada IS NULL AND hora_saida IS NULL)
        """, (inicio_7_dias, hoje))
        registros_incompletos_7d = cur.fetchone()[0] or 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            "sistema": {
                "total_colaboradores": total_colab,
                "colaboradores_ativos": ativos,
                "total_registros_ponto": total_pontos
            },
            "ultimos_7_dias": {
                "colaboradores_com_registro": colaboradores_com_registro_7d,
                "registros_completos": registros_completos_7d,
                "registros_incompletos": registros_incompletos_7d,
                "periodo": {
                    "inicio": inicio_7_dias.strftime("%Y-%m-%d"),
                    "fim": hoje.strftime("%Y-%m-%d")
                }
            },
            "status": "dados_disponiveis" if total_pontos > 0 else "sem_dados",
            "mensagem": "Há dados para exibição" if total_pontos > 0 else "Sistema sem dados de ponto"
        }), 200
        
    except Exception as e:
        print(f"Erro no teste dados: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500