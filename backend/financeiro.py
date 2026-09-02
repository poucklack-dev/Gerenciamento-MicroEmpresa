# ===============================================================
#  PATAGONIA · FINANCEIRO 360° — BACKEND COM CATEGORIAS EM TODOS OS DADOS + VEÍCULOS
# ===============================================================

from flask import Blueprint, jsonify, request
from core.database import get_conn
from datetime import date, datetime, timedelta
from decimal import Decimal

from functools import wraps
from flask_login import current_user

financeiro360_bp = Blueprint("financeiro360", __name__, url_prefix="/api/financeiro")

# ===============================================================
#  DECORADOR DE AUTENTICAÇÃO
# ===============================================================
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
# ===============================================================
#  HELPER FUNCTIONS
# ===============================================================

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

def get_period_range(start, end):
    """Get period range for meta information"""
    if start and end:
        try:
            start_date = datetime.strptime(start, '%Y-%m-%d')
            end_date = datetime.strptime(end, '%Y-%m-%d')
            days = (end_date - start_date).days + 1
            return start_date, end_date, days
        except Exception as e:
            print(f"Erro ao converter datas: {e}")
            return None, None, 0
    return None, None, 0

# ===============================================================
#  LISTA DE CATEGORIAS (MESMA DO CONTAS_PAGAR)
# ===============================================================

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

# ===============================================================
#  ENDPOINT PRINCIPAL 360 - COM CATEGORIAS E VEÍCULOS
# ===============================================================

@financeiro360_bp.get("/360")
@require_admin
def financeiro_360():
    start = request.args.get("inicio") or request.args.get("start")
    end = request.args.get("fim") or request.args.get("end")
    
    # Pagination parameters
    limit = request.args.get("limit", type=int, default=1000)
    offset = request.args.get("offset", type=int, default=0)
    
    conn = get_conn()
    cur = conn.cursor()
    resultado = {"meta": {"periodo": {}, "gerado_em": datetime.now().isoformat(), "warnings": []}}
    
    try:
        # ======================================================
        # META INFORMATION
        # ======================================================
        start_date, end_date, days = get_period_range(start, end)
        resultado["meta"]["periodo"] = {
            "inicio": start,
            "fim": end,
            "dias": days,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
        
        # ======================================================
        # 2. DESPESAS POR CATEGORIA (COMPLETO)
        # ======================================================
        query_categorias = """
            SELECT 
                COALESCE(categoria, 'Não categorizado') as categoria,
                SUM(valor) as total,
                COUNT(*) as quantidade,
                SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END) as pendente,
                SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END) as pago,
                COUNT(CASE WHEN status = 'pendente' THEN 1 END) as qtd_pendente,
                COUNT(CASE WHEN status = 'pago' THEN 1 END) as qtd_pago
            FROM contas_pagar
            WHERE 1=1
        """
        params_categorias = []
        
        if start and end:
            query_categorias += " AND vencimento BETWEEN %s AND %s"
            params_categorias.extend([start, end])
        
        query_categorias += """
            GROUP BY categoria
            ORDER BY total DESC
        """
        
        try:
            cur.execute(query_categorias, params_categorias)
            categorias_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de categorias: {e}")
            categorias_rows = []
        
        despesas_por_categoria = []
        total_categorias = 0
        
        for r in categorias_rows:
            try:
                if len(r) >= 7:
                    total = to_float(r[1])
                    categoria_info = {
                        "categoria": r[0] or "Não categorizado",
                        "total": total,
                        "quantidade": r[2] or 0,
                        "pendente": to_float(r[3]),
                        "pago": to_float(r[4]),
                        "qtd_pendente": r[5] or 0,
                        "qtd_pago": r[6] or 0,
                        "percentual": 0
                    }
                    despesas_por_categoria.append(categoria_info)
                    total_categorias += total
            except Exception as e:
                print(f"Erro ao processar categoria: {e}")
                continue
        
        # Calcular percentuais
        for cat in despesas_por_categoria:
            if total_categorias > 0:
                cat["percentual"] = round((cat["total"] / total_categorias) * 100, 2)
        
        # Adicionar categorias que não têm registros (valor zero)
        categorias_com_dados = [cat["categoria"] for cat in despesas_por_categoria]
        for cat_nome in CATEGORIAS:
            if cat_nome not in categorias_com_dados:
                despesas_por_categoria.append({
                    "categoria": cat_nome,
                    "total": 0,
                    "quantidade": 0,
                    "pendente": 0,
                    "pago": 0,
                    "qtd_pendente": 0,
                    "qtd_pago": 0,
                    "percentual": 0
                })
        
        # Ordenar novamente após adicionar todas as categorias
        despesas_por_categoria.sort(key=lambda x: x["total"], reverse=True)
        
        resultado["despesas_por_categoria"] = despesas_por_categoria
        resultado["total_despesas_categorias"] = total_categorias
        
        # ======================================================
        # 2.1 TOP 5 CATEGORIAS COM MAIOR GASTO
        # ======================================================
        top_categorias = []
        for cat in despesas_por_categoria[:5]:
            top_categorias.append({
                "categoria": cat["categoria"],
                "total": cat["total"],
                "percentual": cat["percentual"],
                "quantidade": cat["quantidade"]
            })
        
        resultado["top_categorias"] = top_categorias
        
        # ======================================================
        # 2.2 DISTRIBUIÇÃO POR STATUS EM CADA CATEGORIA
        # ======================================================
        categorias_status = []
        for cat in despesas_por_categoria[:10]:  # Top 10 para não ficar muito grande
            if cat["total"] > 0:
                categorias_status.append({
                    "categoria": cat["categoria"],
                    "pago": cat["pago"],
                    "pendente": cat["pendente"],
                    "percent_pago": round((cat["pago"] / cat["total"]) * 100, 2) if cat["total"] > 0 else 0,
                    "percent_pendente": round((cat["pendente"] / cat["total"]) * 100, 2) if cat["total"] > 0 else 0
                })
        
        resultado["categorias_status"] = categorias_status
        
        # ======================================================
        # 1. CONTRATOS COM ANÁLISE DE RENTABILIDADE E CATEGORIAS
        # ======================================================
        query_contratos = """
            SELECT 
                c.id, c.codigo_contrato, c.nome_empresa, c.valor_orcado,
                c.data_inicio, c.data_fim, c.status,
                COALESCE(SUM(g.valor), 0) as gasto_acumulado,
                COALESCE(SUM(cp.valor), 0) as contas_pagar_acumulado,
                COUNT(DISTINCT g.id) as qtd_gastos,
                COUNT(DISTINCT cp.id) as qtd_contas_pagar,
                -- Adicionando categorias dos gastos do contrato
                (
                    SELECT STRING_AGG(DISTINCT cp2.categoria, ', ')
                    FROM contas_pagar cp2 
                    WHERE cp2.contrato_id = c.id 
                    AND cp2.categoria IS NOT NULL 
                    AND cp2.categoria != ''
                    LIMIT 5
                ) as categorias_principais
            FROM contratos c
            LEFT JOIN gastos_contrato g ON c.id = g.contrato_id
                AND (%s IS NULL OR %s IS NULL OR g.data_gasto BETWEEN %s AND %s)
            LEFT JOIN contas_pagar cp ON c.id = cp.contrato_id 
                AND cp.status = 'pago'
                AND (%s IS NULL OR %s IS NULL OR cp.vencimento BETWEEN %s AND %s)
            GROUP BY c.id, c.codigo_contrato, c.nome_empresa, c.valor_orcado,
                     c.data_inicio, c.data_fim, c.status
            ORDER BY c.data_inicio DESC
            LIMIT %s OFFSET %s
        """
        params_contratos = [start, end, start, end, start, end, start, end, limit, offset]
        
        try:
            cur.execute(query_contratos, params_contratos)
            contratos_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de contratos: {e}")
            contratos_rows = []
        
        contratos = []
        total_contratos_ativo = 0
        total_valor_orcado = 0
        total_gasto_contratos = 0
        total_contas_pagar_contratos = 0
        
        for r in contratos_rows:
            try:
                if len(r) < 12:
                    continue
                    
                valor_orcado = to_float(r[3])
                gasto_acumulado = to_float(r[7])
                contas_pagar_acumulado = to_float(r[8])
                gasto_total = gasto_acumulado + contas_pagar_acumulado
                saldo_disponivel = valor_orcado - gasto_total
                
                if valor_orcado > 0:
                    percent_utilizado = round((gasto_total / valor_orcado) * 100, 2)
                else:
                    percent_utilizado = 0
                
                status = r[6] if r[6] else ""
                categorias_principais = r[11] or ""
                
                # Converter string de categorias em lista
                if categorias_principais:
                    categorias_lista = [cat.strip() for cat in categorias_principais.split(',')]
                else:
                    categorias_lista = []
                
                contrato = {
                    "id": r[0],
                    "codigo": r[1] or "",
                    "empresa": r[2] or "",
                    "valor_orcado": valor_orcado,
                    "gasto_acumulado": gasto_acumulado,
                    "contas_pagar_acumulado": contas_pagar_acumulado,
                    "gasto_total": gasto_total,
                    "saldo_disponivel": saldo_disponivel,
                    "percent_utilizado": percent_utilizado,
                    "data_inicio": r[4].isoformat() if r[4] else None,
                    "data_fim": r[5].isoformat() if r[5] else None,
                    "status": status,
                    "qtd_gastos": r[9] or 0,
                    "qtd_contas_pagar": r[10] or 0,
                    "categorias_principais": categorias_lista,
                    "categorias_string": categorias_principais,
                    "situacao": "critico" if percent_utilizado > 80 else 
                               "atencao" if percent_utilizado > 60 else 
                               "saudavel"
                }
                
                contratos.append(contrato)
                
                if status == 'ativo':
                    total_contratos_ativo += 1
                    total_valor_orcado += valor_orcado
                    total_gasto_contratos += gasto_acumulado
                    total_contas_pagar_contratos += contas_pagar_acumulado
                    
            except Exception as e:
                print(f"Erro ao processar contrato: {e}")
                continue

        # Total count for pagination
        try:
            cur.execute("SELECT COUNT(*) FROM contratos")
            count_row = cur.fetchone()
            total_contratos = count_row[0] if count_row else 0
        except:
            total_contratos = 0
        
        total_gasto_total_contratos = total_gasto_contratos + total_contas_pagar_contratos
        
        resultado["contratos"] = contratos
        resultado["contratos_kpi"] = {
            "ativos": total_contratos_ativo,
            "total_orcado": total_valor_orcado,
            "total_gasto_contrato": total_gasto_contratos,
            "total_contas_pagar_contrato": total_contas_pagar_contratos,
            "total_gasto": total_gasto_total_contratos,
            "total_saldo": total_valor_orcado - total_gasto_total_contratos,
            "media_gasto_contrato": total_gasto_total_contratos / total_contratos_ativo if total_contratos_ativo > 0 else 0,
            "total_count": total_contratos,
            "limit": limit,
            "offset": offset,
            "truncated": len(contratos) >= limit
        }

        # ======================================================
        # 3. GASTOS TOTAIS POR MÊS COM CATEGORIAS
        # ======================================================
        query_gastos_mes_categoria = """
            SELECT 
                TO_CHAR(vencimento, 'YYYY-MM') as mes,
                TO_CHAR(vencimento, 'Mon') as mes_nome,
                EXTRACT(YEAR FROM vencimento) as ano,
                EXTRACT(MONTH FROM vencimento) as mes_numero,
                COALESCE(categoria, 'Não categorizado') as categoria,
                SUM(valor) as total,
                COUNT(*) as quantidade,
                SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END) as pendente,
                SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END) as pago
            FROM contas_pagar
            WHERE 1=1
        """
        params_gastos_mes_categoria = []
        
        if start and end:
            query_gastos_mes_categoria += " AND vencimento BETWEEN %s AND %s"
            params_gastos_mes_categoria.extend([start, end])
        
        query_gastos_mes_categoria += """
            GROUP BY TO_CHAR(vencimento, 'YYYY-MM'), 
                     TO_CHAR(vencimento, 'Mon'),
                     EXTRACT(YEAR FROM vencimento),
                     EXTRACT(MONTH FROM vencimento),
                     categoria
            ORDER BY ano, mes_numero, total DESC
        """
        
        try:
            cur.execute(query_gastos_mes_categoria, params_gastos_mes_categoria)
            gastos_mes_categoria_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de gastos mensais por categoria: {e}")
            gastos_mes_categoria_rows = []
        
        # Organizar por mês
        gastos_por_mes = {}
        for r in gastos_mes_categoria_rows:
            try:
                if len(r) >= 9:
                    mes_key = r[0] or "N/A"
                    if mes_key not in gastos_por_mes:
                        gastos_por_mes[mes_key] = {
                            "mes": mes_key,
                            "mes_nome": str(r[1]).capitalize() if r[1] else "N/A",
                            "ano": int(r[2]) if r[2] else 0,
                            "mes_numero": int(r[3]) if r[3] else 0,
                            "total": 0,
                            "categorias": [],
                            "quantidade": 0
                        }
                    
                    total_mes = to_float(r[5])
                    gastos_por_mes[mes_key]["total"] += total_mes
                    gastos_por_mes[mes_key]["quantidade"] += r[6] or 0
                    
                    gastos_por_mes[mes_key]["categorias"].append({
                        "categoria": r[4] or "Não categorizado",
                        "total": total_mes,
                        "quantidade": r[6] or 0,
                        "pendente": to_float(r[7]),
                        "pago": to_float(r[8]),
                        "percent_mes": 0
                    })
            except Exception as e:
                print(f"Erro ao processar gasto mensal por categoria: {e}")
                continue
        
        # Calcular percentuais por categoria dentro de cada mês
        gastos_mes_final = []
        for mes_key, mes_data in gastos_por_mes.items():
            for cat in mes_data["categorias"]:
                if mes_data["total"] > 0:
                    cat["percent_mes"] = round((cat["total"] / mes_data["total"]) * 100, 2)
            
            mes_data["categorias"].sort(key=lambda x: x["total"], reverse=True)
            mes_data["tendencia"] = "alta" if mes_data["total"] > 10000 else \
                                   "estavel" if mes_data["total"] > 5000 else "baixa"
            gastos_mes_final.append(mes_data)
        
        # Ordenar por mês
        gastos_mes_final.sort(key=lambda x: (x["ano"], x["mes_numero"]))
        
        resultado["gastos_mes_categoria"] = gastos_mes_final

        # ======================================================
        # 4. CONTAS A PAGAR RESUMO POR CATEGORIA
        # ======================================================
        query_contas_pagar_categoria = """
            SELECT 
                COALESCE(categoria, 'Não categorizado') as categoria,
                COALESCE(SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END), 0) as pendente,
                COALESCE(SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END), 0) as pago,
                COALESCE(SUM(CASE WHEN status = 'pendente' AND vencimento < CURRENT_DATE THEN valor ELSE 0 END), 0) as vencidas,
                COALESCE(SUM(CASE WHEN status = 'pendente' AND vencimento BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days' THEN valor ELSE 0 END), 0) as vencer_7dias,
                COALESCE(SUM(CASE WHEN status = 'pendente' AND vencimento BETWEEN CURRENT_DATE + INTERVAL '8 days' AND CURRENT_DATE + INTERVAL '30 days' THEN valor ELSE 0 END), 0) as vencer_30dias,
                COUNT(CASE WHEN status = 'pendente' THEN 1 END) as quantidade_pendente,
                COUNT(CASE WHEN status = 'pago' THEN 1 END) as quantidade_pago,
                COUNT(*) as total_contas
            FROM contas_pagar
            WHERE 1=1
        """
        params_contas_pagar_categoria = []
        
        if start and end:
            query_contas_pagar_categoria += " AND vencimento BETWEEN %s AND %s"
            params_contas_pagar_categoria.extend([start, end])
        
        query_contas_pagar_categoria += """
            GROUP BY categoria
            ORDER BY pendente DESC
        """
        
        try:
            cur.execute(query_contas_pagar_categoria, params_contas_pagar_categoria)
            cp_categoria_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de contas a pagar por categoria: {e}")
            cp_categoria_rows = []
        
        contas_pagar_categoria = []
        total_pendente = 0
        total_pago = 0
        total_vencidas = 0
        
        for r in cp_categoria_rows:
            try:
                if len(r) >= 9:
                    categoria = r[0] or "Não categorizado"
                    pendente = to_float(r[1])
                    pago = to_float(r[2])
                    vencidas = to_float(r[3])
                    
                    contas_pagar_categoria.append({
                        "categoria": categoria,
                        "pendente": pendente,
                        "pago": pago,
                        "vencidas": vencidas,
                        "vencer_7dias": to_float(r[4]),
                        "vencer_30dias": to_float(r[5]),
                        "quantidade_pendente": r[6] or 0,
                        "quantidade_pago": r[7] or 0,
                        "total_contas": r[8] or 0
                    })
                    
                    total_pendente += pendente
                    total_pago += pago
                    total_vencidas += vencidas
            except Exception as e:
                print(f"Erro ao processar contas a pagar por categoria: {e}")
                continue
        
        resultado["contas_pagar"] = {
            "por_categoria": contas_pagar_categoria,
            "resumo": {
                "pendente": total_pendente,
                "pago": total_pago,
                "vencidas": total_vencidas,
                "vencer_7dias": sum([cat["vencer_7dias"] for cat in contas_pagar_categoria]),
                "vencer_30dias": sum([cat["vencer_30dias"] for cat in contas_pagar_categoria]),
                "quantidade_pendente": sum([cat["quantidade_pendente"] for cat in contas_pagar_categoria]),
                "quantidade_pago": sum([cat["quantidade_pago"] for cat in contas_pagar_categoria]),
                "total_contas": sum([cat["total_contas"] for cat in contas_pagar_categoria]),
                "situacao_vencimentos": "critica" if total_vencidas > 5000 else 
                                       "atencao" if total_vencidas > 1000 else "normal"
            }
        }

        # ======================================================
        # 5. RESUMO FINANCEIRO COM CATEGORIAS
        # ======================================================
        # Receitas totais (serviços)
        try:
            cur.execute("""
                SELECT COALESCE(SUM(valor), 0) as receita_servicos
                FROM servicos
                WHERE 1=1
            """, ())
            servicos_row = cur.fetchone()
            receita_servicos = to_float(servicos_row[0]) if servicos_row else 0
        except:
            receita_servicos = 0
        
        # Despesas totais do período
        despesas_periodo = total_categorias  # Já calculado acima
        
        # Calcular indicadores financeiros
        receitas_total = receita_servicos
        despesas_total = despesas_periodo
        lucro = receitas_total - despesas_total
        
        # Calcular margem (evitar divisão por zero)
        if receitas_total > 0:
            margem = (lucro / receitas_total * 100)
        else:
            margem = 0
        
        # Burn Rate (gasto mensal médio)
        if start and end and days > 0:
            burn_rate = (despesas_total / days) * 30  # Projeção mensal
        else:
            burn_rate = despesas_total
        
        # Saldo de caixa (fluxo_caixa)
        try:
            cur.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END), 0) as saldo
                FROM fluxo_caixa
                WHERE 1=1
            """ + (" AND data BETWEEN %s AND %s" if start and end else ""), 
            ([start, end] if start and end else []))
            saldo_row = cur.fetchone()
            saldo_caixa = to_float(saldo_row[0]) if saldo_row else 0
        except:
            saldo_caixa = 0
        
        # Runway Financeiro (evitar divisão por zero)
        if burn_rate > 0:
            runway = saldo_caixa / burn_rate
        else:
            runway = 0
        
        resultado["resumo_360"] = {
            "receitas_total": receitas_total,
            "despesas_total": despesas_total,
            "lucro": lucro,
            "margem": round(margem, 2),
            "saldo_caixa": saldo_caixa,
            "valor_contratos": total_valor_orcado,
            "burn_rate": round(burn_rate, 2),
            "runway": round(runway, 1),
            "custo_medio_contrato": total_gasto_total_contratos / total_contratos_ativo if total_contratos_ativo > 0 else 0,
            "distribuicao_categorias": {
                "total_categorias": len(despesas_por_categoria),
                "categorias_com_gasto": len([cat for cat in despesas_por_categoria if cat["total"] > 0]),
                "categoria_maior_gasto": top_categorias[0]["categoria"] if top_categorias else "Nenhuma",
                "valor_categoria_maior_gasto": top_categorias[0]["total"] if top_categorias else 0
            }
        }

        # ======================================================
        # 6. PERFORMANCE E TENDÊNCIAS POR CATEGORIA
        # ======================================================
        # Determinar tendência por categoria
        categoria_tendencias = []
        for cat in despesas_por_categoria[:5]:  # Top 5 categorias
            if cat["total"] > 0:
                categoria_tendencias.append({
                    "categoria": cat["categoria"],
                    "total": cat["total"],
                    "percentual": cat["percentual"],
                    "tendencia": "alta" if cat["total"] > 10000 else 
                                "estavel" if cat["total"] > 5000 else "baixa",
                    "alerta": "critico" if cat["pendente"] > cat["pago"] * 2 else 
                             "atencao" if cat["pendente"] > cat["pago"] else "normal"
                })
        
        # Saúde financeira geral
        if margem > 15:
            saude_financeira = "saudavel"
        elif margem > 5:
            saude_financeira = "atencao"
        else:
            saude_financeira = "critica"
        
        resultado["performance"] = {
            "categoria_tendencias": categoria_tendencias,
            "saude_financeira": saude_financeira,
            "eficiencia_operacional": round((receitas_total / despesas_total) * 100, 1) if despesas_total > 0 else 0,
            "concentracao_categorias": {
                "top3_percent": sum([cat["percentual"] for cat in despesas_por_categoria[:3]]),
                "top5_percent": sum([cat["percentual"] for cat in despesas_por_categoria[:5]])
            }
        }

        # ======================================================
        # 7. ALERTAS FINANCEIROS POR CATEGORIA
        # ======================================================
        alertas = []
        
        # Alerta de margem baixa
        if margem < 10:
            alertas.append({
                "tipo": "financeiro",
                "nivel": "critico" if margem < 5 else "warning",
                "mensagem": f"Margem de lucro em {round(margem, 1)}% - Abaixo do recomendado (10%)",
                "acao": "Revise custos operacionais"
            })
        
        # Alerta de runway curto
        if runway < 3:
            alertas.append({
                "tipo": "caixa",
                "nivel": "critico" if runway < 1 else "warning",
                "mensagem": f"Runway financeiro: {round(runway, 1)} meses",
                "acao": "Aumente receitas ou reduza custos"
            })
        
        # Alerta de contas vencidas por categoria
        for cat in contas_pagar_categoria:
            if cat["vencidas"] > 1000:
                alertas.append({
                    "tipo": "pagamento",
                    "nivel": "critico" if cat["vencidas"] > 5000 else "warning",
                    "categoria": cat["categoria"],
                    "mensagem": f"Contas vencidas na categoria {cat['categoria']}: R$ {cat['vencidas']:.2f}",
                    "acao": "Regularize pendências nesta categoria"
                })
        
        # Alerta de categoria com alto gasto
        for cat in despesas_por_categoria[:3]:  # Top 3 categorias
            if cat["total"] > 10000 and cat["percentual"] > 20:
                alertas.append({
                    "tipo": "categoria",
                    "nivel": "warning",
                    "categoria": cat["categoria"],
                    "mensagem": f"Categoria {cat['categoria']} concentra {cat['percentual']}% dos gastos (R$ {cat['total']:.2f})",
                    "acao": "Avalie possíveis reduções nesta categoria"
                })
        
        resultado["alertas"] = alertas

        # ======================================================
        # 8. GASTOS DETALHADOS COM CATEGORIAS
        # ======================================================
        query_todos_gastos_categoria = """
            SELECT 
                cp.id,
                cp.fornecedor,
                cp.descricao, 
                cp.valor, 
                cp.vencimento,
                cp.categoria,
                cp.status,
                c.nome_empresa,
                cp.contrato_id,
                'conta_pagar' as tipo,
                cp.comprovante
            FROM contas_pagar cp
            LEFT JOIN contratos c ON cp.contrato_id = c.id
            WHERE 1=1
        """
        params_todos_gastos_categoria = []
        
        if start and end:
            query_todos_gastos_categoria += " AND cp.vencimento BETWEEN %s AND %s"
            params_todos_gastos_categoria.extend([start, end])
        
        query_todos_gastos_categoria += """
            ORDER BY cp.valor DESC, cp.vencimento DESC
            LIMIT %s OFFSET %s
        """
        params_todos_gastos_categoria.extend([limit, offset])
        
        try:
            cur.execute(query_todos_gastos_categoria, params_todos_gastos_categoria)
            todos_gastos_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de todos gastos: {e}")
            todos_gastos_rows = []
        
        todos_gastos = []
        for r in todos_gastos_rows:
            try:
                if len(r) >= 11:
                    gasto_info = {
                        "id": r[0],
                        "fornecedor": r[1] or "",
                        "descricao": r[2] or "Sem descrição",
                        "valor": to_float(r[3]),
                        "data": r[4].isoformat() if r[4] else None,
                        "categoria": r[5] or "Não categorizado",
                        "status": r[6] or "pendente",
                        "contrato": r[7] or "Não vinculado",
                        "contrato_id": r[8],
                        "tipo": r[9] or "conta_pagar",
                        "comprovante": r[10] or "",
                        "categoria_cor": get_categoria_color(r[5]) if r[5] else "#999999"
                    }
                    todos_gastos.append(gasto_info)
            except Exception as e:
                print(f"Erro ao processar gasto detalhado: {e}")
                continue
        
        resultado["gastos_detalhados"] = todos_gastos

        # ======================================================
        # 9. CONTAS A PAGAR DETALHADAS COM CATEGORIAS
        # ======================================================
        query_contas_detalhadas = """
            SELECT 
                id,
                fornecedor,
                descricao,
                valor,
                vencimento,
                categoria,
                status,
                contrato_id
            FROM contas_pagar
            WHERE 1=1
        """
        params_contas_detalhadas = []
        
        if start and end:
            query_contas_detalhadas += " AND vencimento BETWEEN %s AND %s"
            params_contas_detalhadas.extend([start, end])
        
        query_contas_detalhadas += """
            ORDER BY status, vencimento
            LIMIT %s OFFSET %s
        """
        params_contas_detalhadas.extend([limit, offset])
        
        try:
            cur.execute(query_contas_detalhadas, params_contas_detalhadas)
            contas_detalhadas_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de contas detalhadas: {e}")
            contas_detalhadas_rows = []
        
        contas_detalhadas = []
        for r in contas_detalhadas_rows:
            try:
                if len(r) >= 8:
                    conta_info = {
                        "id": r[0],
                        "fornecedor": r[1] or "",
                        "descricao": r[2] or "",
                        "valor": to_float(r[3]),
                        "vencimento": r[4].isoformat() if r[4] else None,
                        "categoria": r[5] or "Não categorizado",
                        "status": r[6] or "pendente",
                        "contrato_id": r[7],
                        "atrasada": is_atrasada(r[4], r[6]) if r[4] else False
                    }
                    contas_detalhadas.append(conta_info)
            except Exception as e:
                print(f"Erro ao processar conta detalhada: {e}")
                continue
        
        resultado["contas_detalhadas"] = contas_detalhadas

        # ======================================================
        # 10. FLUXO DE CAIXA RESUMIDO
        # ======================================================
        query_fluxo_caixa = """
            SELECT 
                COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END), 0) as entrada,
                COALESCE(SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END), 0) as saida
            FROM fluxo_caixa
            WHERE 1=1
        """
        params_fluxo_caixa = []
        
        if start and end:
            query_fluxo_caixa += " AND data BETWEEN %s AND %s"
            params_fluxo_caixa.extend([start, end])
        
        try:
            cur.execute(query_fluxo_caixa, params_fluxo_caixa)
            fc_row = cur.fetchone()
        except Exception as e:
            print(f"Erro na consulta de fluxo de caixa: {e}")
            fc_row = None
        
        if fc_row and len(fc_row) >= 2:
            saldo_fluxo = to_float(fc_row[0]) - to_float(fc_row[1])
            resultado["fluxo_caixa"] = {
                "entrada": to_float(fc_row[0]),
                "saida": to_float(fc_row[1]),
                "saldo": saldo_fluxo
            }
        else:
            resultado["fluxo_caixa"] = {
                "entrada": 0,
                "saida": 0,
                "saldo": 0
            }

        # ======================================================
        # 11. ESTATÍSTICAS ADICIONAIS POR CATEGORIA
        # ======================================================
        # Média por categoria
        estatisticas_categoria = []
        for cat in despesas_por_categoria:
            if cat["quantidade"] > 0:
                estatisticas_categoria.append({
                    "categoria": cat["categoria"],
                    "media_gasto": cat["total"] / cat["quantidade"],
                    "frequencia_mensal": cat["quantidade"] / max(1, days/30) if days > 0 else 0,
                    "gasto_por_status": {
                        "pago_percent": (cat["pago"] / cat["total"] * 100) if cat["total"] > 0 else 0,
                        "pendente_percent": (cat["pendente"] / cat["total"] * 100) if cat["total"] > 0 else 0
                    }
                })
        
        resultado["estatisticas_categoria"] = estatisticas_categoria
        
        # ======================================================
        # 12. RESUMO POR GRUPO DE CATEGORIAS
        # ======================================================
        grupos_categorias = {
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
        
        resumo_grupos = []
        for grupo_nome, categorias_grupo in grupos_categorias.items():
            total_grupo = 0
            qtd_grupo = 0
            
            for cat_nome in categorias_grupo:
                for cat in despesas_por_categoria:
                    if cat["categoria"] == cat_nome:
                        total_grupo += cat["total"]
                        qtd_grupo += cat["quantidade"]
                        break
            
            if total_grupo > 0:
                resumo_grupos.append({
                    "grupo": grupo_nome,
                    "total": total_grupo,
                    "quantidade": qtd_grupo,
                    "percentual": round((total_grupo / total_categorias) * 100, 2) if total_categorias > 0 else 0,
                    "categorias_count": len(categorias_grupo)
                })
        
        resumo_grupos.sort(key=lambda x: x["total"], reverse=True)
        resultado["resumo_grupos"] = resumo_grupos

        # ======================================================
        # 13. VEÍCULOS - DADOS COMPLETOS
        # ======================================================
        
        # 13.1 Informações básicas dos veículos
        query_veiculos = """
            SELECT 
                v.id,
                v.placa,
                v.modelo,
                v.marca,
                v.ano,
                v.combustivel,
                v.km_atual,
                v.status,
                v.foto,
                -- Calcular custos totais por veículo
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'combustivel' THEN cv.valor ELSE 0 END), 0) as total_combustivel,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'manutencao' THEN cv.valor ELSE 0 END), 0) as total_manutencao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'documentacao' THEN cv.valor ELSE 0 END), 0) as total_documentacao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'seguro' THEN cv.valor ELSE 0 END), 0) as total_seguro,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'outros' THEN cv.valor ELSE 0 END), 0) as total_outros,
                COALESCE(SUM(cv.valor), 0) as total_custos,
                -- Contagem por tipo
                COUNT(CASE WHEN cv.tipo_custo = 'combustivel' THEN 1 END) as qtd_abastecimentos,
                COUNT(CASE WHEN cv.tipo_custo = 'manutencao' THEN 1 END) as qtd_manutencoes,
                -- Última manutenção
                MAX(CASE WHEN cv.tipo_custo = 'manutencao' THEN cv.data END) as ultima_manutencao,
                -- Contratos associados
                COUNT(DISTINCT cv.contrato_id) as contratos_associados,
                -- Kilometragem percorrida no período (se houver registros de km)
                COALESCE((
                    SELECT MAX(km_final) - MIN(km_inicial)
                    FROM quilometragem q 
                    WHERE q.veiculo_id = v.id
                    AND (%s IS NULL OR %s IS NULL OR q.data_registro BETWEEN %s AND %s)
                ), 0) as km_percorrido_periodo
            FROM veiculos v
            LEFT JOIN custos_veiculos cv ON v.id = cv.veiculo_id
                AND (%s IS NULL OR %s IS NULL OR cv.data BETWEEN %s AND %s)
            GROUP BY v.id, v.placa, v.modelo, v.marca, v.ano, v.combustivel, v.km_atual, v.status, v.foto
            ORDER BY v.placa
        """
        params_veiculos = [start, end, start, end, start, end, start, end]
        
        try:
            cur.execute(query_veiculos, params_veiculos)
            veiculos_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de veículos: {e}")
            veiculos_rows = []
        
        veiculos_detalhados = []
        total_custos_veiculos = 0
        total_veiculos_ativos = 0
        total_km_percorrido = 0
        
        for r in veiculos_rows:
            try:
                if len(r) >= 20:
                    total_combustivel = to_float(r[9])
                    total_manutencao = to_float(r[10])
                    total_documentacao = to_float(r[11])
                    total_seguro = to_float(r[12])
                    total_outros = to_float(r[13])
                    total_custos_veiculo = to_float(r[14])
                    km_atual = to_float(r[6])
                    km_percorrido = to_float(r[19])
                    
                    # Calcular custo por km
                    custo_por_km = total_custos_veiculo / km_percorrido if km_percorrido > 0 else 0
                    
                    # Status do veículo baseado em custos e manutenção
                    status_veiculo = r[7] or "ativo"
                    
                    veiculo_info = {
                        "id": r[0],
                        "placa": r[1] or "",
                        "modelo": r[2] or "",
                        "marca": r[3] or "",
                        "ano": r[4] or 0,
                        "combustivel": r[5] or "",
                        "km_atual": km_atual,
                        "status": status_veiculo,
                        "foto": r[8] or "",
                        "custos": {
                            "combustivel": total_combustivel,
                            "manutencao": total_manutencao,
                            "documentacao": total_documentacao,
                            "seguro": total_seguro,
                            "outros": total_outros,
                            "total": total_custos_veiculo
                        },
                        "estatisticas": {
                            "qtd_abastecimentos": r[15] or 0,
                            "qtd_manutencoes": r[16] or 0,
                            "ultima_manutencao": r[17].isoformat() if r[17] else None,
                            "contratos_associados": r[18] or 0,
                            "km_percorrido_periodo": km_percorrido,
                            "custo_por_km": round(custo_por_km, 2),
                            "media_combustivel_mensal": total_combustivel / max(1, days/30) if days > 0 else 0
                        },
                        "indicadores": {
                            "saude": "boa" if total_manutencao < 1000 else "atencao" if total_manutencao < 3000 else "critica",
                            "custo_efetividade": "baixo" if custo_por_km < 1 else "medio" if custo_por_km < 2 else "alto",
                            "manutencao_pendente": True if (r[17] and (date.today() - r[17].date()).days > 180) else False
                        }
                    }
                    
                    veiculos_detalhados.append(veiculo_info)
                    total_custos_veiculos += total_custos_veiculo
                    total_km_percorrido += km_percorrido
                    
                    if status_veiculo == 'ativo':
                        total_veiculos_ativos += 1
                        
            except Exception as e:
                print(f"Erro ao processar veículo: {e}")
                continue
        
        resultado["veiculos"] = {
            "lista": veiculos_detalhados,
            "resumo": {
                "total_veiculos": len(veiculos_detalhados),
                "total_ativos": total_veiculos_ativos,
                "total_custos": total_custos_veiculos,
                "total_km_percorrido": total_km_percorrido,
                "custo_medio_por_km": total_custos_veiculos / total_km_percorrido if total_km_percorrido > 0 else 0,
                "custo_medio_por_veiculo": total_custos_veiculos / len(veiculos_detalhados) if veiculos_detalhados else 0
            },
            "distribuicao_custos": {
                "combustivel_percent": (sum([v["custos"]["combustivel"] for v in veiculos_detalhados]) / total_custos_veiculos * 100) if total_custos_veiculos > 0 else 0,
                "manutencao_percent": (sum([v["custos"]["manutencao"] for v in veiculos_detalhados]) / total_custos_veiculos * 100) if total_custos_veiculos > 0 else 0,
                "documentacao_percent": (sum([v["custos"]["documentacao"] for v in veiculos_detalhados]) / total_custos_veiculos * 100) if total_custos_veiculos > 0 else 0,
                "seguro_percent": (sum([v["custos"]["seguro"] for v in veiculos_detalhados]) / total_custos_veiculos * 100) if total_custos_veiculos > 0 else 0
            }
        }

        # 13.2 Custos detalhados por veículo (últimos 10 registros)
        query_custos_detalhados = """
            SELECT 
                cv.id,
                cv.veiculo_id,
                v.placa,
                cv.tipo_custo,
                cv.descricao,
                cv.valor,
                cv.data,
                cv.local,
                cv.fornecedor,
                cv.observacao,
                c.nome_empresa as contrato_nome,
                cv.contrato_id
            FROM custos_veiculos cv
            JOIN veiculos v ON cv.veiculo_id = v.id
            LEFT JOIN contratos c ON cv.contrato_id = c.id
            WHERE 1=1
        """
        params_custos_detalhados = []
        
        if start and end:
            query_custos_detalhados += " AND cv.data BETWEEN %s AND %s"
            params_custos_detalhados.extend([start, end])
        
        query_custos_detalhados += """
            ORDER BY cv.data DESC, cv.valor DESC
            LIMIT %s
        """
        params_custos_detalhados.extend([50])  # Limitar a 50 registros
        
        try:
            cur.execute(query_custos_detalhados, params_custos_detalhados)
            custos_detalhados_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de custos detalhados: {e}")
            custos_detalhados_rows = []
        
        custos_detalhados = []
        for r in custos_detalhados_rows:
            try:
                if len(r) >= 12:
                    custo_info = {
                        "id": r[0],
                        "veiculo_id": r[1],
                        "placa": r[2] or "",
                        "tipo_custo": r[3] or "",
                        "descricao": r[4] or "",
                        "valor": to_float(r[5]),
                        "data": r[6].isoformat() if r[6] else None,
                        "local": r[7] or "",
                        "fornecedor": r[8] or "",
                        "observacao": r[9] or "",
                        "contrato_nome": r[10] or "Não vinculado",
                        "contrato_id": r[11],
                        "categoria_cor": get_categoria_color_veiculo(r[3]) if r[3] else "#999999"
                    }
                    custos_detalhados.append(custo_info)
            except Exception as e:
                print(f"Erro ao processar custo detalhado: {e}")
                continue
        
        resultado["veiculos"]["custos_detalhados"] = custos_detalhados

        # 13.3 Abastecimentos por veículo (últimos 20)
        query_abastecimentos = """
            SELECT 
                a.id,
                a.veiculo_id,
                v.placa,
                a.data,
                a.litros,
                a.valor_total,
                a.km_atual,
                a.nota_fiscal,
                ROUND(a.valor_total / NULLIF(a.litros, 0), 3) as preco_litro
            FROM abastecimentos a
            JOIN veiculos v ON a.veiculo_id = v.id
            WHERE 1=1
        """
        params_abastecimentos = []
        
        if start and end:
            query_abastecimentos += " AND a.data BETWEEN %s AND %s"
            params_abastecimentos.extend([start, end])
        
        query_abastecimentos += """
            ORDER BY a.data DESC
            LIMIT %s
        """
        params_abastecimentos.extend([20])
        
        try:
            cur.execute(query_abastecimentos, params_abastecimentos)
            abastecimentos_rows = cur.fetchall()
        except Exception as e:
            print(f"Erro na consulta de abastecimentos: {e}")
            abastecimentos_rows = []
        
        abastecimentos = []
        total_litros = 0
        total_valor_abastecimento = 0
        
        for r in abastecimentos_rows:
            try:
                if len(r) >= 9:
                    litros = to_float(r[4])
                    valor_total = to_float(r[5])
                    
                    abastecimento_info = {
                        "id": r[0],
                        "veiculo_id": r[1],
                        "placa": r[2] or "",
                        "data": r[3].isoformat() if r[3] else None,
                        "litros": litros,
                        "valor_total": valor_total,
                        "km_atual": to_float(r[6]),
                        "nota_fiscal": r[7] or "",
                        "preco_litro": to_float(r[8]) if r[8] else 0,
                        "custo_por_km": 0  # Será calculado se houver km anterior
                    }
                    
                    abastecimentos.append(abastecimento_info)
                    total_litros += litros
                    total_valor_abastecimento += valor_total
            except Exception as e:
                print(f"Erro ao processar abastecimento: {e}")
                continue
        
        # Calcular consumo médio se houver dados suficientes
        consumo_medio = total_litros / len(abastecimentos) if abastecimentos else 0
        preco_medio_litro = total_valor_abastecimento / total_litros if total_litros > 0 else 0
        
        resultado["veiculos"]["abastecimentos"] = {
            "lista": abastecimentos,
            "resumo": {
                "total_abastecimentos": len(abastecimentos),
                "total_litros": total_litros,
                "total_valor": total_valor_abastecimento,
                "consumo_medio": round(consumo_medio, 2),
                "preco_medio_litro": round(preco_medio_litro, 2),
                "custo_medio_abastecimento": total_valor_abastecimento / len(abastecimentos) if abastecimentos else 0
            }
        }

        # 13.4 Veículos com maior custo (top 5)
        veiculos_maior_custo = sorted(veiculos_detalhados, key=lambda x: x["custos"]["total"], reverse=True)[:5]
        resultado["veiculos"]["top_custos"] = [
            {
                "placa": v["placa"],
                "modelo": v["modelo"],
                "total_custos": v["custos"]["total"],
                "custo_por_km": v["estatisticas"]["custo_por_km"],
                "status": v["status"],
                "indicador_saude": v["indicadores"]["saude"]
            } for v in veiculos_maior_custo
        ]

        # 13.5 Alertas específicos de veículos
        alertas_veiculos = []
        
        for veiculo in veiculos_detalhados:
            # Alerta de manutenção pendente
            if veiculo["indicadores"]["manutencao_pendente"]:
                alertas_veiculos.append({
                    "tipo": "manutencao",
                    "nivel": "warning",
                    "veiculo": veiculo["placa"],
                    "mensagem": f"Veículo {veiculo['placa']} - Manutenção pendente há mais de 6 meses",
                    "acao": "Agendar manutenção preventiva"
                })
            
            # Alerta de custo alto por km
            if veiculo["indicadores"]["custo_efetividade"] == "alto":
                alertas_veiculos.append({
                    "tipo": "custo",
                    "nivel": "warning",
                    "veiculo": veiculo["placa"],
                    "mensagem": f"Veículo {veiculo['placa']} - Custo por km elevado (R$ {veiculo['estatisticas']['custo_por_km']:.2f}/km)",
                    "acao": "Avaliar necessidade do veículo ou otimizar uso"
                })
            
            # Alerta de muitos abastecimentos (possível vazamento ou uso excessivo)
            if veiculo["estatisticas"]["qtd_abastecimentos"] > 10:
                alertas_veiculos.append({
                    "tipo": "consumo",
                    "nivel": "info",
                    "veiculo": veiculo["placa"],
                    "mensagem": f"Veículo {veiculo['placa']} - {veiculo['estatisticas']['qtd_abastecimentos']} abastecimentos no período",
                    "acao": "Verificar consumo e eficiência do veículo"
                })
        
        resultado["veiculos"]["alertas"] = alertas_veiculos
        
        # Adicionar alertas de veículos aos alertas gerais
        resultado["alertas"].extend(alertas_veiculos[:3])  # Adicionar apenas os 3 principais

        # ======================================================
        # 14. INTEGRAÇÃO DE DADOS DE VEÍCULOS COM OUTRAS SEÇÕES
        # ======================================================
        
        # Atualizar resumo financeiro para incluir custos de veículos
        resultado["resumo_360"]["custo_total_veiculos"] = total_custos_veiculos
        resultado["resumo_360"]["percentual_custo_veiculos"] = round((total_custos_veiculos / despesas_total * 100), 2) if despesas_total > 0 else 0
        
        # Adicionar veículos à seção de performance
        resultado["performance"]["veiculos"] = {
            "custo_medio_por_veiculo": total_custos_veiculos / len(veiculos_detalhados) if veiculos_detalhados else 0,
            "km_total_percorrido": total_km_percorrido,
            "veiculo_mais_caro": veiculos_maior_custo[0]["placa"] if veiculos_maior_custo else "Nenhum",
            "custo_veiculo_mais_caro": veiculos_maior_custo[0]["custos"]["total"] if veiculos_maior_custo else 0
        }

        # ======================================================
        # FINALIZAÇÃO
        # ======================================================
        resultado["status"] = "success"
        resultado["meta"]["total_categorias"] = len(CATEGORIAS)
        resultado["meta"]["categorias_disponiveis"] = CATEGORIAS
        resultado["meta"]["categorias_com_dados"] = len([cat for cat in despesas_por_categoria if cat["total"] > 0])
        resultado["meta"]["total_veiculos"] = len(veiculos_detalhados)
        resultado["meta"]["veiculos_ativos"] = total_veiculos_ativos

    except Exception as e:
        print(f"Erro crítico no endpoint 360: {e}")
        resultado["status"] = "error"
        resultado["erro"] = str(e)
        
        # Retornar estrutura básica em caso de erro
        estrutura_basica = {
            "contratos": [],
            "despesas_por_categoria": [],
            "top_categorias": [],
            "categorias_status": [],
            "gastos_mes_categoria": [],
            "contas_pagar": {"por_categoria": [], "resumo": {}},
            "resumo_360": {},
            "performance": {},
            "alertas": [],
            "gastos_detalhados": [],
            "contas_detalhadas": [],
            "fluxo_caixa": {},
            "estatisticas_categoria": [],
            "resumo_grupos": [],
            "veiculos": {
                "lista": [],
                "resumo": {},
                "custos_detalhados": [],
                "abastecimentos": {"lista": [], "resumo": {}},
                "top_custos": [],
                "alertas": []
            }
        }
        
        for key, value in estrutura_basica.items():
            if key not in resultado:
                resultado[key] = value
                
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
    
    return jsonify(resultado)


# ===============================================================
#  HELPER METHODS PARA CORES E STATUS
# ===============================================================

def get_categoria_color(categoria_nome):
    """Retorna uma cor baseada no nome da categoria"""
    if not categoria_nome:
        return "#999999"
    
    cores_por_grupo = {
        "🏕️ ": "#4CAF50",  # Verde para campo
        "🚗": "#2196F3",   # Azul para veículos
        "🔧": "#FF9800",   # Laranja para equipamentos
        "👥": "#9C27B0",   # Roxo para RH
        "💻": "#00BCD4",   # Ciano para TI
        "💰": "#F44336",   # Vermelho para folha
        "🏢": "#795548",   # Marrom para escritório
        "📋": "#607D8B",   # Azul-cinza para serviços
        "📢": "#E91E63",   # Rosa para marketing
        "📦": "#9E9E9E"    # Cinza para outros
    }
    
    for prefixo, cor in cores_por_grupo.items():
        if categoria_nome.startswith(prefixo):
            return cor
    
    # Se não encontrar prefixo, gerar cor baseada no hash do nome
    import hashlib
    hash_obj = hashlib.md5(categoria_nome.encode())
    hash_int = int(hash_obj.hexdigest()[:6], 16)
    
    # Gerar uma cor agradável baseada no hash
    r = (hash_int >> 16) & 255
    g = (hash_int >> 8) & 255
    b = hash_int & 255
    
    # Ajustar para não ficar muito claro ou escuro
    r = max(50, min(200, r))
    g = max(50, min(200, g))
    b = max(50, min(200, b))
    
    return f"#{r:02x}{g:02x}{b:02x}"

def get_categoria_color_veiculo(tipo_custo):
    """Retorna uma cor baseada no tipo de custo do veículo"""
    cores_veiculo = {
        "combustivel": "#FF5722",    # Laranja escuro
        "manutencao": "#2196F3",     # Azul
        "documentacao": "#4CAF50",   # Verde
        "seguro": "#9C27B0",         # Roxo
        "outros": "#795548"          # Marrom
    }
    return cores_veiculo.get(tipo_custo, "#607D8B")  # Cinza azulado como padrão

def is_atrasada(vencimento, status):
    """Verifica se uma conta está atrasada"""
    if status != "pendente":
        return False
    
    try:
        if isinstance(vencimento, str):
            vencimento_date = datetime.strptime(vencimento.split('T')[0], '%Y-%m-%d').date()
        elif isinstance(vencimento, date):
            vencimento_date = vencimento
        elif isinstance(vencimento, datetime):
            vencimento_date = vencimento.date()
        else:
            return False
        
        return vencimento_date < date.today()
    except:
        return False


# ===============================================================
#  ENDPOINT ESPECÍFICO PARA VEÍCULOS
# ===============================================================

@financeiro360_bp.get("/veiculos/detalhado")
@require_admin
def veiculos_detalhado():
    """Retorna dados detalhados dos veículos com análise de custos"""
    start = request.args.get("inicio") or request.args.get("start")
    end = request.args.get("fim") or request.args.get("end")
    veiculo_id = request.args.get("veiculo_id", type=int)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Query base para veículos
        query = """
            SELECT 
                v.id,
                v.placa,
                v.modelo,
                v.marca,
                v.ano,
                v.combustivel,
                v.km_atual,
                v.status,
                v.foto,
                -- Dados de custos
                COALESCE(SUM(cv.valor), 0) as total_custos,
                COUNT(cv.id) as qtd_custos,
                -- Custo por tipo
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'combustivel' THEN cv.valor ELSE 0 END), 0) as total_combustivel,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'manutencao' THEN cv.valor ELSE 0 END), 0) as total_manutencao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'documentacao' THEN cv.valor ELSE 0 END), 0) as total_documentacao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'seguro' THEN cv.valor ELSE 0 END), 0) as total_seguro,
                -- Última manutenção
                MAX(CASE WHEN cv.tipo_custo = 'manutencao' THEN cv.data END) as ultima_manutencao,
                -- Kilometragem percorrida
                COALESCE((
                    SELECT MAX(km_final) - MIN(km_inicial)
                    FROM quilometragem q 
                    WHERE q.veiculo_id = v.id
                    AND (%s IS NULL OR %s IS NULL OR q.data_registro BETWEEN %s AND %s)
                ), 0) as km_percorrido
            FROM veiculos v
            LEFT JOIN custos_veiculos cv ON v.id = cv.veiculo_id
                AND (%s IS NULL OR %s IS NULL OR cv.data BETWEEN %s AND %s)
            WHERE 1=1
        """
        params = [start, end, start, end, start, end, start, end]
        
        if veiculo_id:
            query += " AND v.id = %s"
            params.append(veiculo_id)
        
        query += """
            GROUP BY v.id, v.placa, v.modelo, v.marca, v.ano, v.combustivel, v.km_atual, v.status, v.foto
            ORDER BY v.placa
        """
        
        cur.execute(query, params)
        veiculos_rows = cur.fetchall()
        
        veiculos = []
        for r in veiculos_rows:
            if len(r) >= 17:
                total_custos = to_float(r[9])
                km_percorrido = to_float(r[16])
                custo_por_km = total_custos / km_percorrido if km_percorrido > 0 else 0
                
                # Calcular média de consumo se houver abastecimentos
                try:
                    cur.execute("""
                        SELECT AVG(valor_total / NULLIF(litros, 0)), SUM(litros), COUNT(*)
                        FROM abastecimentos 
                        WHERE veiculo_id = %s
                        AND (%s IS NULL OR %s IS NULL OR data BETWEEN %s AND %s)
                    """, [r[0], start, end, start, end])
                    consumo_row = cur.fetchone()
                    preco_medio_litro = to_float(consumo_row[0]) if consumo_row else 0
                    total_litros = to_float(consumo_row[1]) if consumo_row else 0
                    qtd_abastecimentos = consumo_row[2] if consumo_row else 0
                    
                    consumo_medio_km_litro = km_percorrido / total_litros if total_litros > 0 else 0
                except:
                    preco_medio_litro = 0
                    consumo_medio_km_litro = 0
                    qtd_abastecimentos = 0
                
                veiculo = {
                    "id": r[0],
                    "placa": r[1] or "",
                    "modelo": r[2] or "",
                    "marca": r[3] or "",
                    "ano": r[4] or 0,
                    "combustivel": r[5] or "",
                    "km_atual": to_float(r[6]),
                    "status": r[7] or "ativo",
                    "foto": r[8] or "",
                    "resumo_custos": {
                        "total": total_custos,
                        "combustivel": to_float(r[11]),
                        "manutencao": to_float(r[12]),
                        "documentacao": to_float(r[13]),
                        "seguro": to_float(r[14]),
                        "outros": total_custos - (to_float(r[11]) + to_float(r[12]) + to_float(r[13]) + to_float(r[14]))
                    },
                    "estatisticas": {
                        "qtd_custos": r[10] or 0,
                        "ultima_manutencao": r[15].isoformat() if r[15] else None,
                        "km_percorrido": km_percorrido,
                        "custo_por_km": round(custo_por_km, 2),
                        "preco_medio_litro": round(preco_medio_litro, 2),
                        "consumo_medio_km_litro": round(consumo_medio_km_litro, 2),
                        "qtd_abastecimentos": qtd_abastecimentos
                    },
                    "saude": {
                        "nivel": "boa" if custo_por_km < 1 else "atencao" if custo_por_km < 2 else "critica",
                        "manutencao_em_dia": False if (r[15] and (date.today() - r[15].date()).days > 180) else True,
                        "documentacao_regular": True  # Aqui poderia verificar documentação
                    }
                }
                veiculos.append(veiculo)
        
        # Se for consulta de um veículo específico, trazer custos detalhados
        custos_detalhados = []
        if veiculo_id and veiculos:
            cur.execute("""
                SELECT 
                    cv.id,
                    cv.tipo_custo,
                    cv.descricao,
                    cv.valor,
                    cv.data,
                    cv.local,
                    cv.fornecedor,
                    cv.observacao,
                    c.nome_empresa as contrato_nome
                FROM custos_veiculos cv
                LEFT JOIN contratos c ON cv.contrato_id = c.id
                WHERE cv.veiculo_id = %s
                AND (%s IS NULL OR %s IS NULL OR cv.data BETWEEN %s AND %s)
                ORDER BY cv.data DESC
            """, [veiculo_id, start, end, start, end])
            
            custos_rows = cur.fetchall()
            for cr in custos_rows:
                if len(cr) >= 9:
                    custos_detalhados.append({
                        "id": cr[0],
                        "tipo": cr[1] or "",
                        "descricao": cr[2] or "",
                        "valor": to_float(cr[3]),
                        "data": cr[4].isoformat() if cr[4] else None,
                        "local": cr[5] or "",
                        "fornecedor": cr[6] or "",
                        "observacao": cr[7] or "",
                        "contrato": cr[8] or "Não vinculado"
                    })
        
        # Abastecimentos do veículo
        abastecimentos = []
        if veiculo_id and veiculos:
            cur.execute("""
                SELECT 
                    id,
                    data,
                    litros,
                    valor_total,
                    km_atual,
                    nota_fiscal,
                    ROUND(valor_total / NULLIF(litros, 0), 3) as preco_litro
                FROM abastecimentos
                WHERE veiculo_id = %s
                AND (%s IS NULL OR %s IS NULL OR data BETWEEN %s AND %s)
                ORDER BY data DESC
            """, [veiculo_id, start, end, start, end])
            
            abast_rows = cur.fetchall()
            for ar in abast_rows:
                if len(ar) >= 7:
                    abastecimentos.append({
                        "id": ar[0],
                        "data": ar[1].isoformat() if ar[1] else None,
                        "litros": to_float(ar[2]),
                        "valor": to_float(ar[3]),
                        "km": to_float(ar[4]),
                        "nota_fiscal": ar[5] or "",
                        "preco_litro": to_float(ar[6]) if ar[6] else 0
                    })
        
        conn.close()
        
        resultado = {
            "status": "success",
            "veiculos": veiculos,
            "periodo": {"inicio": start, "fim": end}
        }
        
        if veiculo_id and veiculos:
            resultado["custos_detalhados"] = custos_detalhados
            resultado["abastecimentos"] = abastecimentos
            # Adicionar histórico de quilometragem
            try:
                cur.execute("""
                    SELECT id, data_registro, km_inicial, km_final, foto_odometro
                    FROM quilometragem
                    WHERE veiculo_id = %s
                    ORDER BY data_registro DESC
                    LIMIT 10
                """, [veiculo_id])
                
                km_rows = cur.fetchall()
                quilometragem = []
                for kmr in km_rows:
                    if len(kmr) >= 5:
                        quilometragem.append({
                            "id": kmr[0],
                            "data": kmr[1].isoformat() if kmr[1] else None,
                            "km_inicial": to_float(kmr[2]),
                            "km_final": to_float(kmr[3]),
                            "km_percorrido": to_float(kmr[3]) - to_float(kmr[2]),
                            "foto": kmr[4] or ""
                        })
                resultado["quilometragem"] = quilometragem
            except:
                resultado["quilometragem"] = []
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "erro": str(e)
        })
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# ===============================================================
#  ENDPOINT PARA ANÁLISE DE CUSTOS POR VEÍCULO
# ===============================================================

@financeiro360_bp.get("/veiculos/analise-custos")
@require_admin
def analise_custos_veiculos():
    """Retorna análise comparativa de custos entre veículos"""
    start = request.args.get("inicio") or request.args.get("start")
    end = request.args.get("fim") or request.args.get("end")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Análise de custos por tipo
        query_analise = """
            SELECT 
                v.placa,
                v.modelo,
                v.combustivel,
                v.status,
                -- Custos por categoria
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'combustivel' THEN cv.valor ELSE 0 END), 0) as combustivel,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'manutencao' THEN cv.valor ELSE 0 END), 0) as manutencao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'documentacao' THEN cv.valor ELSE 0 END), 0) as documentacao,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'seguro' THEN cv.valor ELSE 0 END), 0) as seguro,
                COALESCE(SUM(CASE WHEN cv.tipo_custo = 'outros' THEN cv.valor ELSE 0 END), 0) as outros,
                COALESCE(SUM(cv.valor), 0) as total,
                -- Kilometragem
                COALESCE((
                    SELECT MAX(km_final) - MIN(km_inicial)
                    FROM quilometragem q 
                    WHERE q.veiculo_id = v.id
                    AND (%s IS NULL OR %s IS NULL OR q.data_registro BETWEEN %s AND %s)
                ), 0) as km_percorrido,
                -- Contagem de custos
                COUNT(cv.id) as qtd_custos
            FROM veiculos v
            LEFT JOIN custos_veiculos cv ON v.id = cv.veiculo_id
                AND (%s IS NULL OR %s IS NULL OR cv.data BETWEEN %s AND %s)
            GROUP BY v.id, v.placa, v.modelo, v.combustivel, v.status
            HAVING COUNT(cv.id) > 0 OR (
                SELECT COUNT(*) FROM quilometragem q2 
                WHERE q2.veiculo_id = v.id
                AND (%s IS NULL OR %s IS NULL OR q2.data_registro BETWEEN %s AND %s)
            ) > 0
            ORDER BY total DESC
        """
        params = [start, end, start, end, start, end, start, end, start, end]
        
        cur.execute(query_analise, params)
        analise_rows = cur.fetchall()
        
        analise = []
        totais = {
            "combustivel": 0,
            "manutencao": 0,
            "documentacao": 0,
            "seguro": 0,
            "outros": 0,
            "total": 0,
            "km_total": 0
        }
        
        for r in analise_rows:
            if len(r) >= 13:
                total_veiculo = to_float(r[10])
                km_percorrido = to_float(r[11])
                custo_por_km = total_veiculo / km_percorrido if km_percorrido > 0 else 0
                
                item = {
                    "placa": r[0] or "",
                    "modelo": r[1] or "",
                    "combustivel": r[2] or "",
                    "status": r[3] or "",
                    "custos": {
                        "combustivel": to_float(r[4]),
                        "manutencao": to_float(r[5]),
                        "documentacao": to_float(r[6]),
                        "seguro": to_float(r[7]),
                        "outros": to_float(r[8]),
                        "total": total_veiculo
                    },
                    "km_percorrido": km_percorrido,
                    "custo_por_km": round(custo_por_km, 2),
                    "qtd_custos": r[12] or 0,
                    "eficiencia": "alta" if custo_por_km < 1 else "media" if custo_por_km < 2 else "baixa"
                }
                analise.append(item)
                
                # Acumular totais
                totais["combustivel"] += to_float(r[4])
                totais["manutencao"] += to_float(r[5])
                totais["documentacao"] += to_float(r[6])
                totais["seguro"] += to_float(r[7])
                totais["outros"] += to_float(r[8])
                totais["total"] += total_veiculo
                totais["km_total"] += km_percorrido
        
        # Calcular médias e percentuais
        if totais["total"] > 0:
            percentuais = {
                "combustivel": round((totais["combustivel"] / totais["total"]) * 100, 1),
                "manutencao": round((totais["manutencao"] / totais["total"]) * 100, 1),
                "documentacao": round((totais["documentacao"] / totais["total"]) * 100, 1),
                "seguro": round((totais["seguro"] / totais["total"]) * 100, 1),
                "outros": round((totais["outros"] / totais["total"]) * 100, 1)
            }
        else:
            percentuais = {}
        
        custo_medio_por_km = totais["total"] / totais["km_total"] if totais["km_total"] > 0 else 0
        
        # Recomendações baseadas na análise
        recomendacoes = []
        if len(analise) > 0:
            veiculo_mais_caro = max(analise, key=lambda x: x["custos"]["total"])
            veiculo_mais_economico = min(analise, key=lambda x: x["custo_por_km"])
            
            if veiculo_mais_caro["custo_por_km"] > 2:
                recomendacoes.append({
                    "tipo": "custo",
                    "prioridade": "alta",
                    "mensagem": f"Veículo {veiculo_mais_caro['placa']} tem custo por km elevado (R$ {veiculo_mais_caro['custo_por_km']:.2f}/km)",
                    "acao": "Considerar substituição ou redução de uso"
                })
            
            if percentuais.get("manutencao", 0) > 30:
                recomendacoes.append({
                    "tipo": "manutencao",
                    "prioridade": "media",
                    "mensagem": f"Manutenção representa {percentuais['manutencao']}% dos custos totais",
                    "acao": "Avaliar contrato de manutenção preventiva"
                })
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "analise": analise,
            "totais": totais,
            "percentuais": percentuais,
            "medias": {
                "custo_medio_por_km": round(custo_medio_por_km, 2),
                "custo_medio_por_veiculo": totais["total"] / len(analise) if analise else 0,
                "km_medio_por_veiculo": totais["km_total"] / len(analise) if analise else 0
            },
            "recomendacoes": recomendacoes,
            "periodo": {"inicio": start, "fim": end}
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "erro": str(e)
        })
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# ===============================================================
#  ENDPOINT PARA INFORMAÇÕES DE CATEGORIAS (FRONTEND)
# ===============================================================

@financeiro360_bp.get("/categorias")
def get_categorias():
    """Retorna a lista de categorias usadas no frontend"""
    grupos_categorias = {
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
    
    # Lista plana de todas as categorias
    todas_categorias = []
    for grupo in grupos_categorias.values():
        todas_categorias.extend(grupo)
    
    return jsonify({
        "status": "success",
        "categorias": todas_categorias,
        "grupos": grupos_categorias,
        "total": len(todas_categorias),
        "observacao": "Categorias utilizadas para classificação de todas as despesas"
    })


# ===============================================================
#  ENDPOINT PARA ESTATÍSTICAS POR CATEGORIA
# ===============================================================

@financeiro360_bp.get("/estatisticas/categorias")
@require_admin
def estatisticas_categorias_detalhadas():
    """Retorna estatísticas detalhadas por categoria"""
    start = request.args.get("inicio") or request.args.get("start")
    end = request.args.get("fim") or request.args.get("end")
    
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
                SUM(valor) as total,
                COUNT(CASE WHEN status = 'pendente' AND vencimento < CURRENT_DATE THEN 1 END) as vencidas_qtd,
                SUM(CASE WHEN status = 'pendente' AND vencimento < CURRENT_DATE THEN valor ELSE 0 END) as vencidas_valor,
                MIN(vencimento) as primeiro_vencimento,
                MAX(vencimento) as ultimo_vencimento
            FROM contas_pagar
            WHERE 1=1
        """
        params = []
        
        if start and end:
            query += " AND vencimento BETWEEN %s AND %s"
            params.extend([start, end])
        
        query += """
            GROUP BY categoria
            ORDER BY total DESC
        """
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        categorias_stats = []
        for row in rows:
            categorias_stats.append({
                "categoria": row[0] or "Não categorizado",
                "quantidade": row[1] or 0,
                "pendente": to_float(row[2]),
                "pago": to_float(row[3]),
                "total": to_float(row[4]),
                "vencidas_qtd": row[5] or 0,
                "vencidas_valor": to_float(row[6]),
                "primeiro_vencimento": row[7].isoformat() if row[7] else None,
                "ultimo_vencimento": row[8].isoformat() if row[8] else None,
                "media": to_float(row[4]) / row[1] if row[1] > 0 else 0,
                "percent_pago": (to_float(row[3]) / to_float(row[4]) * 100) if to_float(row[4]) > 0 else 0,
                "percent_pendente": (to_float(row[2]) / to_float(row[4]) * 100) if to_float(row[4]) > 0 else 0
            })
        
        # Totais gerais
        query_totais = """
            SELECT 
                COUNT(*) as total_contas,
                SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as total_pendentes,
                SUM(CASE WHEN status = 'pago' THEN 1 ELSE 0 END) as total_pagas,
                SUM(CASE WHEN status = 'pendente' THEN valor ELSE 0 END) as valor_pendente,
                SUM(CASE WHEN status = 'pago' THEN valor ELSE 0 END) as valor_pago,
                SUM(valor) as valor_total,
                COUNT(DISTINCT categoria) as categorias_distintas
            FROM contas_pagar
            WHERE 1=1
        """
        params_totais = []
        
        if start and end:
            query_totais += " AND vencimento BETWEEN %s AND %s"
            params_totais.extend([start, end])
        
        cur.execute(query_totais, params_totais)
        totais_row = cur.fetchone()
        
        totais = {
            "total_contas": totais_row[0] if totais_row else 0,
            "total_pendentes": totais_row[1] if totais_row else 0,
            "total_pagas": totais_row[2] if totais_row else 0,
            "valor_pendente": to_float(totais_row[3]) if totais_row else 0,
            "valor_pago": to_float(totais_row[4]) if totais_row else 0,
            "valor_total": to_float(totais_row[5]) if totais_row else 0,
            "categorias_distintas": totais_row[6] if totais_row else 0
        }
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "categorias": categorias_stats,
            "totais": totais,
            "categorias_disponiveis": CATEGORIAS,
            "periodo": {
                "inicio": start,
                "fim": end
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "erro": str(e)
        })
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# ===============================================================
#  ENDPOINT PARA CONTRATOS EM RESUMO
# ===============================================================

@financeiro360_bp.get("/contratos-resumo")
@require_admin
def contratos_resumo():
    """Retorna um resumo dos contratos para dashboard"""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Contratos por status
        query = """
            SELECT 
                status,
                COUNT(*) as quantidade,
                SUM(valor_orcado) as valor_total
            FROM contratos
            GROUP BY status
            ORDER BY status
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        resumo = {
            "total": 0,
            "ativos": 0,
            "finalizados": 0,
            "valor_total": 0,
            "valor_ativos": 0,
            "detalhes": []
        }
        
        for r in rows:
            if len(r) >= 3:
                status = r[0] or "sem_status"
                quantidade = r[1] or 0
                valor = to_float(r[2])
                
                resumo["total"] += quantidade
                resumo["valor_total"] += valor
                
                if status == "ativo":
                    resumo["ativos"] += quantidade
                    resumo["valor_ativos"] += valor
                elif status == "finalizado":
                    resumo["finalizados"] += quantidade
                
                resumo["detalhes"].append({
                    "status": status,
                    "quantidade": quantidade,
                    "valor": valor
                })
        
        return jsonify({
            "status": "success",
            "resumo": resumo
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "erro": str(e)
        })
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# ===============================================================
#  ENDPOINT PARA DESPESAS DO DIA
# ===============================================================

@financeiro360_bp.get("/despesas-hoje")
@require_admin
def despesas_hoje():
    """Retorna despesas do dia atual"""
    hoje = date.today().isoformat()
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Contas pagas hoje com categoria
        query_contas = """
            SELECT 
                COALESCE(categoria, 'Não categorizado') as categoria,
                SUM(valor) as total,
                COUNT(*) as quantidade
            FROM contas_pagar
            WHERE status = 'pago' AND vencimento = %s
            GROUP BY categoria
            ORDER BY total DESC
        """
        
        cur.execute(query_contas, [hoje])
        contas_rows = cur.fetchall()
        
        despesas_hoje = []
        total_contas = 0
        
        for r in contas_rows:
            if len(r) >= 3:
                total_cat = to_float(r[1])
                despesas_hoje.append({
                    "categoria": r[0] or "Não categorizado",
                    "total": total_cat,
                    "quantidade": r[2] or 0,
                    "tipo": "conta_pagar"
                })
                total_contas += total_cat
        
        # Gastos do dia (se houver tabela de gastos_contrato)
        try:
            query_gastos = """
                SELECT 
                    COALESCE(SUM(valor), 0) as total,
                    COUNT(*) as quantidade
                FROM gastos_contrato
                WHERE data_gasto = %s
            """
            
            cur.execute(query_gastos, [hoje])
            gastos_row = cur.fetchone()
            total_gastos = to_float(gastos_row[0]) if gastos_row else 0
        except:
            total_gastos = 0
        
        total_dia = total_contas + total_gastos
        
        return jsonify({
            "status": "success",
            "data": hoje,
            "total": total_dia,
            "despesas_por_categoria": despesas_hoje,
            "gastos_contrato": {
                "total": total_gastos,
                "quantidade": gastos_row[1] if gastos_row else 0
            },
            "contas_pagar": {
                "total": total_contas,
                "quantidade": sum([item["quantidade"] for item in despesas_hoje]),
                "categorias": despesas_hoje
            },
            "alertas": {
                "nivel": "baixo" if total_dia < 1000 else 
                        "medio" if total_dia < 5000 else "alto",
                "mensagem": f"Total de despesas hoje: R$ {total_dia:.2f}"
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "erro": str(e)
        })
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass