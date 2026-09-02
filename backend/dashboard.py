# dashboard_backend.py
import logging
import time
from datetime import date, datetime, timedelta
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from core.database import get_conn
from typing import Dict, List, Any, Optional, Tuple

# Configuração do Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprints
bp_dashboard = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
bp_home = Blueprint("home", __name__, url_prefix="/api")

# ============================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================

# TTL (Time-To-Live) para o cache do schema
SCHEMA_TTL_SECONDS = 21600  # 6 horas

# Estrutura de cache em memória
_SCHEMA_CACHE: Dict[str, Dict] = {}

# Limites para consultas
ALERT_QUERY_LIMIT = 50
CHART_DATA_LIMIT = 100

# ============================================================
# CLASSES E TIPOS
# ============================================================

class DashboardAlert:
    """Classe para representar um alerta do dashboard"""
    
    def __init__(self, alert_type: str, message: str, due_date: Optional[date] = None,
                 source: str = "", source_id: Optional[int] = None, 
                 priority: int = 0, metadata: Optional[Dict] = None):
        self.type = alert_type  # 'danger', 'warning', 'info'
        self.message = message
        self.due_date = due_date
        self.source = source
        self.source_id = source_id
        self.priority = priority
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict:
        return {
            "tipo": self.type,
            "mensagem": self.message,
            "data_vencimento": self.due_date.isoformat() if self.due_date else None,
            "origem": self.source,
            "origem_id": self.source_id,
            "prioridade": self.priority,
            "metadata": self.metadata
        }

class DashboardKPI:
    """Classe para representar um KPI do dashboard"""
    
    def __init__(self, name: str, value: Any, 
                 previous_value: Optional[Any] = None,
                 unit: str = "", 
                 trend: Optional[str] = None,
                 color: str = "primary"):
        self.name = name
        self.value = value
        self.previous_value = previous_value
        self.unit = unit
        self.trend = trend  # 'up', 'down', 'stable'
        self.color = color
        
    def to_dict(self) -> Dict:
        return {
            "nome": self.name,
            "valor": self.value,
            "valor_anterior": self.previous_value,
            "unidade": self.unit,
            "tendencia": self.trend,
            "cor": self.color
        }

# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def get_table_columns(cursor, table_name: str) -> List[Tuple[str, str]]:
    """
    Busca as colunas e tipos de uma tabela com cache.
    """
    current_time = time.time()
    
    # Verifica cache
    if table_name in _SCHEMA_CACHE:
        cache_entry = _SCHEMA_CACHE[table_name]
        if (current_time - cache_entry["ts"]) < SCHEMA_TTL_SECONDS:
            return cache_entry["cols"]
    
    # Consulta banco
    try:
        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """
        cursor.execute(query, (table_name,))
        columns = cursor.fetchall()
        
        # Atualiza cache
        _SCHEMA_CACHE[table_name] = {"ts": current_time, "cols": columns}
        return columns
    except Exception as e:
        logger.error(f"Erro ao obter schema para tabela '{table_name}': {e}")
        return []

def find_first_existing_column(potential_columns: List[str], 
                              existing_columns: List[Tuple[str, str]]) -> Optional[str]:
    """
    Encontra a primeira coluna existente na lista.
    """
    existing_column_names = {col[0] for col in existing_columns}
    for col in potential_columns:
        if col in existing_column_names:
            return col
    return None

def table_exists(cursor, table_name: str) -> bool:
    """
    Verifica se uma tabela existe no banco.
    """
    try:
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """
        cursor.execute(query, (table_name,))
        return cursor.fetchone()[0]
    except Exception:
        return False

# ============================================================
# FUNÇÕES DE KPI
# ============================================================

def get_kpis(cursor) -> Dict[str, DashboardKPI]:
    """
    Coleta todos os KPIs do sistema.
    """
    kpis = {}
    hoje = date.today()
    
    # Contagem básica de registros
    def count(table: str, condition: str = "", distinct: str = "") -> int:
        try:
            if distinct:
                query = f"SELECT COUNT(DISTINCT {distinct}) FROM {table}"
            else:
                query = f"SELECT COUNT(*) FROM {table}"
            
            if condition:
                query += f" WHERE {condition}"
            
            cursor.execute(query)
            return cursor.fetchone()[0] or 0
        except Exception as e:
            logger.debug(f"Erro ao contar registros em {table}: {e}")
            return 0
    
    # KPI: Colaboradores ativos
    try:
        ativos = count("colaboradores", "status = 'ativo'")
        total = count("colaboradores")
        kpis["colaboradores_ativos"] = DashboardKPI(
            name="Colaboradores Ativos",
            value=ativos,
            previous_value=total,
            unit="pessoas",
            trend="up" if ativos > 0 else "stable",
            color="success"
        )
    except Exception as e:
        logger.warning(f"Erro ao calcular KPI colaboradores: {e}")
    
    # KPI: Contratos ativos
    try:
        contratos_ativos = count("contratos", "status = 'ativo'")
        kpis["contratos_ativos"] = DashboardKPI(
            name="Contratos Ativos",
            value=contratos_ativos,
            unit="contratos",
            color="info"
        )
    except Exception:
        pass
    
    # KPI: Contas a pagar em aberto
    try:
        contas_pagar = count("contas_pagar", "status != 'pago'")
        cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM contas_pagar WHERE status != 'pago'")
        total_pagar = cursor.fetchone()[0] or 0
        kpis["contas_pagar"] = DashboardKPI(
            name="Contas a Pagar",
            value=contas_pagar,
            metadata={"valor_total": float(total_pagar)},
            unit="contas",
            color="danger"
        )
    except Exception:
        pass
    
    # KPI: Contas a receber em aberto
    try:
        contas_receber = count("contas_receber", "status != 'recebido'")
        cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM contas_receber WHERE status != 'recebido'")
        total_receber = cursor.fetchone()[0] or 0
        kpis["contas_receber"] = DashboardKPI(
            name="Contas a Receber",
            value=contas_receber,
            metadata={"valor_total": float(total_receber)},
            unit="contas",
            color="success"
        )
    except Exception:
        pass
    
    # KPI: NRs a vencer
    try:
        if table_exists(cursor, "nrs_colaboradores"):
            cursor.execute("""
                SELECT COUNT(*) 
                FROM nrs_colaboradores nc
                JOIN colaboradores c ON c.id = nc.colaborador_id
                WHERE c.status = 'ativo' 
                AND nc.data_validade BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            """)
            nrs_a_vencer = cursor.fetchone()[0] or 0
            kpis["nrs_a_vencer"] = DashboardKPI(
                name="NRs a Vencer (30 dias)",
                value=nrs_a_vencer,
                unit="NRs",
                color="warning"
            )
    except Exception:
        pass
    
    # KPI: Veículos ativos
    try:
        veiculos_ativos = count("veiculos", "status = 'ativo'")
        kpis["veiculos_ativos"] = DashboardKPI(
            name="Veículos Ativos",
            value=veiculos_ativos,
            unit="veículos",
            color="primary"
        )
    except Exception:
        pass
    
    # KPI: Clientes ativos
    try:
        clientes_ativos = count("clientes", "status = 'ativo'")
        kpis["clientes_ativos"] = DashboardKPI(
            name="Clientes Ativos",
            value=clientes_ativos,
            unit="clientes",
            color="info"
        )
    except Exception:
        pass
    
    # KPI: Documentos vencidos
    try:
        if table_exists(cursor, "documentos"):
            cursor.execute("SELECT COUNT(*) FROM documentos WHERE validade < CURRENT_DATE")
            docs_vencidos = cursor.fetchone()[0] or 0
            kpis["docs_vencidos"] = DashboardKPI(
                name="Documentos Vencidos",
                value=docs_vencidos,
                unit="documentos",
                color="danger"
            )
    except Exception:
        pass
    
    # KPI: Colaboradores com CNH vencida
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM colaboradores 
            WHERE status = 'ativo' 
            AND validade_cnh IS NOT NULL 
            AND validade_cnh < CURRENT_DATE
        """)
        cnh_vencida = cursor.fetchone()[0] or 0
        kpis["cnh_vencida"] = DashboardKPI(
            name="CNHs Vencidas",
            value=cnh_vencida,
            unit="colaboradores",
            color="danger"
        )
    except Exception:
        pass
    
    return {k: v.to_dict() for k, v in kpis.items()}

# ============================================================
# FUNÇÕES DE ALERTAS
# ============================================================

def get_nrs_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de NRs vencidas ou a vencer.
    """
    alertas = []
    
    try:
        if not table_exists(cursor, "nrs_colaboradores"):
            return alertas
        
        # NRs vencidas
        cursor.execute("""
            SELECT 
                nc.id,
                c.nome as colaborador_nome,
                c.id as colaborador_id,
                n.codigo as nr_codigo,
                n.nome as nr_nome,
                nc.data_validade,
                DATE_PART('day', CURRENT_DATE - nc.data_validade)::integer as dias_vencido
            FROM nrs_colaboradores nc
            JOIN colaboradores c ON c.id = nc.colaborador_id
            JOIN nrs n ON n.id = nc.nr_id
            WHERE c.status = 'ativo'
                AND nc.data_validade < %s
            ORDER BY nc.data_validade ASC
            LIMIT %s;
        """, (hoje, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            dias_vencido = row[6]
            alertas.append({
                "tipo": "perigo",
                "mensagem": f"NR {row[3]} ({row[4]}) do colaborador {row[1]} está vencida há {dias_vencido} dias.",
                "data_vencimento": row[5].isoformat(),
                "origem": "nrs_colaboradores",
                "origem_id": row[0],
                "metadata": {
                    "colaborador_id": row[2],
                    "colaborador_nome": row[1],
                    "nr_codigo": row[3],
                    "nr_nome": row[4],
                    "dias_vencido": dias_vencido
                }
            })
        
        # NRs a vencer em 7 dias
        cursor.execute("""
            SELECT 
                nc.id,
                c.nome as colaborador_nome,
                c.id as colaborador_id,
                n.codigo as nr_codigo,
                n.nome as nr_nome,
                nc.data_validade,
                DATE_PART('day', nc.data_validade - CURRENT_DATE)::integer as dias_para_vencer
            FROM nrs_colaboradores nc
            JOIN colaboradores c ON c.id = nc.colaborador_id
            JOIN nrs n ON n.id = nc.nr_id
            WHERE c.status = 'ativo'
                AND nc.data_validade BETWEEN %s AND %s
            ORDER BY nc.data_validade ASC
            LIMIT %s;
        """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            dias_para_vencer = row[6]
            alertas.append({
                "tipo": "alerta",
                "mensagem": f"NR {row[3]} ({row[4]}) do colaborador {row[1]} vence em {dias_para_vencer} dias.",
                "data_vencimento": row[5].isoformat(),
                "origem": "nrs_colaboradores",
                "origem_id": row[0],
                "metadata": {
                    "colaborador_id": row[2],
                    "colaborador_nome": row[1],
                    "nr_codigo": row[3],
                    "nr_nome": row[4],
                    "dias_para_vencer": dias_para_vencer
                }
            })
        
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de NRs: {e}")
    
    return alertas

def get_documentos_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de documentos.
    """
    alertas = []
    
    try:
        if not table_exists(cursor, "documentos"):
            return alertas
        
        table_cols = get_table_columns(cursor, "documentos")
        date_col = find_first_existing_column(['validade', 'data_validade', 'vencimento'], table_cols)
        name_col = find_first_existing_column(['nome', 'titulo', 'descricao'], table_cols)
        
        if not date_col or not name_col:
            return alertas
        
        # Documentos vencidos
        cursor.execute(f"""
            SELECT id, {name_col}, {date_col} 
            FROM documentos
            WHERE {date_col} < %s
            ORDER BY {date_col} ASC
            LIMIT %s;
        """, (hoje, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            alertas.append({
                "tipo": "perigo",
                "mensagem": f"Documento '{row[1]}' vencido em {row[2].strftime('%d/%m/%Y')}.",
                "data_vencimento": row[2].isoformat(),
                "origem": "documentos",
                "origem_id": row[0]
            })
        
        # Documentos a vencer
        cursor.execute(f"""
            SELECT id, {name_col}, {date_col}
            FROM documentos
            WHERE {date_col} BETWEEN %s AND %s
            ORDER BY {date_col} ASC
            LIMIT %s;
        """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            alertas.append({
                "tipo": "alerta",
                "mensagem": f"Documento '{row[1]}' vence em {row[2].strftime('%d/%m/%Y')}.",
                "data_vencimento": row[2].isoformat(),
                "origem": "documentos",
                "origem_id": row[0]
            })
        
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de documentos: {e}")
    
    return alertas

def get_contratos_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de contratos.
    """
    alertas = []
    
    try:
        if not table_exists(cursor, "contratos"):
            return alertas
        
        table_cols = get_table_columns(cursor, "contratos")
        date_col = find_first_existing_column(['data_fim', 'vencimento', 'termino'], table_cols)
        name_col = find_first_existing_column(['nome', 'cliente', 'empresa'], table_cols)
        
        if not date_col or not name_col:
            return alertas
        
        # Contratos a vencer
        cursor.execute(f"""
            SELECT id, {name_col}, {date_col}
            FROM contratos
            WHERE status = 'ativo' 
            AND {date_col} BETWEEN %s AND %s
            ORDER BY {date_col} ASC
            LIMIT %s;
        """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            alertas.append({
                "tipo": "alerta",
                "mensagem": f"Contrato '{row[1]}' vence em {row[2].strftime('%d/%m/%Y')}.",
                "data_vencimento": row[2].isoformat(),
                "origem": "contratos",
                "origem_id": row[0]
            })
        
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de contratos: {e}")
    
    return alertas

def get_financeiro_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de contas a pagar/receber.
    """
    alertas = []
    
    # Contas a pagar
    try:
        if table_exists(cursor, "contas_pagar"):
            # Vencidas
            cursor.execute("""
                SELECT id, fornecedor, valor, vencimento
                FROM contas_pagar
                WHERE status != 'pago' AND vencimento < %s
                ORDER BY vencimento ASC
                LIMIT %s;
            """, (hoje, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                alertas.append({
                    "tipo": "perigo",
                    "mensagem": f"Conta a pagar para '{row[1]}' vencida: R$ {row[2]:.2f}.",
                    "data_vencimento": row[3].isoformat(),
                    "origem": "contas_pagar",
                    "origem_id": row[0],
                    "metadata": {"valor": float(row[2])}
                })
            
            # A vencer
            cursor.execute("""
                SELECT id, fornecedor, valor, vencimento
                FROM contas_pagar
                WHERE status != 'pago' AND vencimento BETWEEN %s AND %s
                ORDER BY vencimento ASC
                LIMIT %s;
            """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                alertas.append({
                    "tipo": "alerta",
                    "mensagem": f"Conta a pagar para '{row[1]}' vence em breve: R$ {row[2]:.2f}.",
                    "data_vencimento": row[3].isoformat(),
                    "origem": "contas_pagar",
                    "origem_id": row[0],
                    "metadata": {"valor": float(row[2])}
                })
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de contas a pagar: {e}")
    
    # Contas a receber
    try:
        if table_exists(cursor, "contas_receber"):
            # Vencidas
            cursor.execute("""
                SELECT id, descricao, cliente, valor, vencimento
                FROM contas_receber
                WHERE status != 'recebido' AND vencimento < %s
                ORDER BY vencimento ASC
                LIMIT %s;
            """, (hoje, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                descricao = row[1] or row[2] or "Sem descrição"
                alertas.append({
                    "tipo": "perigo",
                    "mensagem": f"Conta a receber '{descricao}' vencida: R$ {row[3]:.2f}.",
                    "data_vencimento": row[4].isoformat(),
                    "origem": "contas_receber",
                    "origem_id": row[0],
                    "metadata": {"valor": float(row[3])}
                })
            
            # A vencer
            cursor.execute("""
                SELECT id, descricao, cliente, valor, vencimento
                FROM contas_receber
                WHERE status != 'recebido' AND vencimento BETWEEN %s AND %s
                ORDER BY vencimento ASC
                LIMIT %s;
            """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                descricao = row[1] or row[2] or "Sem descrição"
                alertas.append({
                    "tipo": "alerta",
                    "mensagem": f"Conta a receber '{descricao}' vence em breve: R$ {row[3]:.2f}.",
                    "data_vencimento": row[4].isoformat(),
                    "origem": "contas_receber",
                    "origem_id": row[0],
                    "metadata": {"valor": float(row[3])}
                })
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de contas a receber: {e}")
    
    return alertas

def get_colaboradores_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de colaboradores (CNH, exames, etc.).
    """
    alertas = []
    
    # CNH vencida
    try:
        cursor.execute("""
            SELECT id, nome, validade_cnh
            FROM colaboradores
            WHERE status = 'ativo' 
            AND validade_cnh IS NOT NULL 
            AND validade_cnh < %s
            ORDER BY validade_cnh ASC
            LIMIT %s;
        """, (hoje, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            alertas.append({
                "tipo": "perigo",
                "mensagem": f"CNH do colaborador {row[1]} vencida em {row[2].strftime('%d/%m/%Y')}.",
                "data_vencimento": row[2].isoformat(),
                "origem": "colaboradores",
                "origem_id": row[0],
                "metadata": {"tipo": "cnh"}
            })
        
        # CNH a vencer
        cursor.execute("""
            SELECT id, nome, validade_cnh
            FROM colaboradores
            WHERE status = 'ativo' 
            AND validade_cnh IS NOT NULL 
            AND validade_cnh BETWEEN %s AND %s
            ORDER BY validade_cnh ASC
            LIMIT %s;
        """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
        
        for row in cursor.fetchall():
            alertas.append({
                "tipo": "alerta",
                "mensagem": f"CNH do colaborador {row[1]} vence em {row[2].strftime('%d/%m/%Y')}.",
                "data_vencimento": row[2].isoformat(),
                "origem": "colaboradores",
                "origem_id": row[0],
                "metadata": {"tipo": "cnh"}
            })
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de CNH: {e}")
    
    return alertas

def get_veiculos_alerts(cursor, hoje: date, daqui_7_dias: date) -> List[Dict]:
    """
    Busca alertas de veículos.
    """
    alertas = []
    
    try:
        if not table_exists(cursor, "veiculos"):
            return alertas
        
        # Busca todas as colunas de data que podem representar vencimentos
        table_cols = get_table_columns(cursor, "veiculos")
        date_columns = [
            col[0] for col in table_cols 
            if ('date' in col[1].lower() or 'timestamp' in col[1].lower())
            and any(term in col[0].lower() for term in ['validade', 'vencimento', 'venc', 'data'])
        ]
        
        for date_col in date_columns:
            # Vencidos
            cursor.execute(f"""
                SELECT id, placa, modelo, {date_col}
                FROM veiculos
                WHERE status = 'ativo' 
                AND {date_col} < %s
                ORDER BY {date_col} ASC
                LIMIT %s;
            """, (hoje, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                alertas.append({
                    "tipo": "perigo",
                    "mensagem": f"Veículo {row[1]} ({row[2]}) - {date_col.replace('_', ' ')} vencido em {row[3].strftime('%d/%m/%Y')}.",
                    "data_vencimento": row[3].isoformat(),
                    "origem": "veiculos",
                    "origem_id": row[0],
                    "metadata": {"tipo": date_col, "placa": row[1]}
                })
            
            # A vencer
            cursor.execute(f"""
                SELECT id, placa, modelo, {date_col}
                FROM veiculos
                WHERE status = 'ativo' 
                AND {date_col} BETWEEN %s AND %s
                ORDER BY {date_col} ASC
                LIMIT %s;
            """, (hoje, daqui_7_dias, ALERT_QUERY_LIMIT))
            
            for row in cursor.fetchall():
                alertas.append({
                    "tipo": "alerta",
                    "mensagem": f"Veículo {row[1]} ({row[2]}) - {date_col.replace('_', ' ')} vence em {row[3].strftime('%d/%m/%Y')}.",
                    "data_vencimento": row[3].isoformat(),
                    "origem": "veiculos",
                    "origem_id": row[0],
                    "metadata": {"tipo": date_col, "placa": row[1]}
                })
        
    except Exception as e:
        logger.error(f"Erro ao buscar alertas de veículos: {e}")
    
    return alertas

# ============================================================
# FUNÇÕES DE GRÁFICOS E ESTATÍSTICAS
# ============================================================

def get_colaboradores_por_cargo(cursor) -> Dict:
    """
    Retorna distribuição de colaboradores por cargo.
    """
    try:
        cursor.execute("""
            SELECT cargo, COUNT(*) as total
            FROM colaboradores
            WHERE status = 'ativo'
            GROUP BY cargo
            ORDER BY total DESC
            LIMIT %s;
        """, (CHART_DATA_LIMIT,))
        
        labels = []
        data = []
        
        for row in cursor.fetchall():
            labels.append(row[0] or "Sem cargo")
            data.append(row[1])
        
        return {
            "labels": labels,
            "datasets": [{
                "label": "Colaboradores por Cargo",
                "data": data,
                "backgroundColor": [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        }
    except Exception as e:
        logger.error(f"Erro ao buscar colaboradores por cargo: {e}")
        return {"labels": [], "datasets": []}

def get_contratos_por_status(cursor) -> Dict:
    """
    Retorna distribuição de contratos por status.
    """
    try:
        if not table_exists(cursor, "contratos"):
            return {"labels": [], "datasets": []}
        
        cursor.execute("""
            SELECT status, COUNT(*) as total
            FROM contratos
            GROUP BY status
            ORDER BY total DESC;
        """)
        
        labels = []
        data = []
        
        for row in cursor.fetchall():
            labels.append(row[0] or "Sem status")
            data.append(row[1])
        
        return {
            "labels": labels,
            "datasets": [{
                "label": "Contratos por Status",
                "data": data,
                "backgroundColor": ['#4CAF50', '#FFC107', '#F44336', '#2196F3']
            }]
        }
    except Exception:
        return {"labels": [], "datasets": []}

def get_contas_por_mes(cursor) -> Dict:
    """
    Retorna contas a pagar/receber por mês.
    """
    try:
        # Últimos 6 meses
        hoje = date.today()
        meses = []
        for i in range(5, -1, -1):
            data = hoje.replace(day=1) - timedelta(days=30*i)
            meses.append(data.strftime("%Y-%m"))
        
        dados = {"labels": meses, "pagar": [0]*6, "receber": [0]*6}
        
        # Contas a pagar
        if table_exists(cursor, "contas_pagar"):
            for i, mes in enumerate(meses):
                cursor.execute("""
                    SELECT COALESCE(SUM(valor), 0)
                    FROM contas_pagar
                    WHERE TO_CHAR(vencimento, 'YYYY-MM') = %s
                    AND status != 'pago';
                """, (mes,))
                dados["pagar"][i] = float(cursor.fetchone()[0] or 0)
        
        # Contas a receber
        if table_exists(cursor, "contas_receber"):
            for i, mes in enumerate(meses):
                cursor.execute("""
                    SELECT COALESCE(SUM(valor), 0)
                    FROM contas_receber
                    WHERE TO_CHAR(vencimento, 'YYYY-MM') = %s
                    AND status != 'recebido';
                """, (mes,))
                dados["receber"][i] = float(cursor.fetchone()[0] or 0)
        
        return {
            "labels": [m[-2:] + "/" + m[:4] for m in meses],
            "datasets": [
                {
                    "label": "Contas a Pagar",
                    "data": dados["pagar"],
                    "borderColor": '#FF6384',
                    "backgroundColor": 'rgba(255, 99, 132, 0.2)'
                },
                {
                    "label": "Contas a Receber",
                    "data": dados["receber"],
                    "borderColor": '#36A2EB',
                    "backgroundColor": 'rgba(54, 162, 235, 0.2)'
                }
            ]
        }
    except Exception as e:
        logger.error(f"Erro ao buscar contas por mês: {e}")
        return {"labels": [], "datasets": []}

def get_nrs_vencimento_stats(cursor) -> Dict:
    """
    Retorna estatísticas de NRs por status de vencimento.
    """
    try:
        if not table_exists(cursor, "nrs_colaboradores"):
            return {"labels": [], "datasets": []}
        
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN data_validade < CURRENT_DATE THEN 'Vencidas'
                    WHEN data_validade <= CURRENT_DATE + INTERVAL '7 days' THEN 'A vencer (7 dias)'
                    WHEN data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN 'A vencer (30 dias)'
                    ELSE 'Em dia'
                END as status,
                COUNT(*) as total
            FROM nrs_colaboradores nc
            JOIN colaboradores c ON c.id = nc.colaborador_id
            WHERE c.status = 'ativo'
            GROUP BY 
                CASE 
                    WHEN data_validade < CURRENT_DATE THEN 'Vencidas'
                    WHEN data_validade <= CURRENT_DATE + INTERVAL '7 days' THEN 'A vencer (7 dias)'
                    WHEN data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN 'A vencer (30 dias)'
                    ELSE 'Em dia'
                END
            ORDER BY 
                CASE 
                    WHEN status = 'Vencidas' THEN 1
                    WHEN status = 'A vencer (7 dias)' THEN 2
                    WHEN status = 'A vencer (30 dias)' THEN 3
                    ELSE 4
                END;
        """)
        
        labels = []
        data = []
        
        for row in cursor.fetchall():
            labels.append(row[0])
            data.append(row[1])
        
        return {
            "labels": labels,
            "datasets": [{
                "label": "NRs por Status",
                "data": data,
                "backgroundColor": ['#F44336', '#FF9800', '#FFC107', '#4CAF50']
            }]
        }
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas de NRs: {e}")
        return {"labels": [], "datasets": []}

# ============================================================
# ROTAS PRINCIPAIS
# ============================================================

@bp_home.get("/dashboard/overview")
@login_required
def dashboard_overview():
    """
    Endpoint principal do dashboard com todos os dados.
    """
    conn = None
    warnings = []
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        hoje = date.today()
        daqui_7_dias = hoje + timedelta(days=7)
        
        # 1. KPIs
        kpis = get_kpis(cur)
        
        # 2. Alertas
        alertas = []
        alertas.extend(get_nrs_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_documentos_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_contratos_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_financeiro_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_colaboradores_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_veiculos_alerts(cur, hoje, daqui_7_dias))
        
        # 3. Estatísticas
        estatisticas = {
            "total": len(alertas),
            "perigo": sum(1 for a in alertas if a["tipo"] == "perigo"),
            "alerta": sum(1 for a in alertas if a["tipo"] == "alerta"),
            "info": sum(1 for a in alertas if a["tipo"] == "info")
        }
        
        # 4. Gráficos
        graficos = {
            "colaboradores_por_cargo": get_colaboradores_por_cargo(cur),
            "contratos_por_status": get_contratos_por_status(cur),
            "contas_por_mes": get_contas_por_mes(cur),
            "nrs_status": get_nrs_vencimento_stats(cur)
        }
        
        # Ordena alertas por data
        alertas.sort(key=lambda x: x.get('data_vencimento') or '9999-12-31')
        
        return jsonify({
            "status": "success",
            "data": {
                "kpis": kpis,
                "alertas": alertas,
                "estatisticas": estatisticas,
                "graficos": graficos
            },
            "timestamp": datetime.now().isoformat(),
            "warnings": warnings
        })
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return jsonify({
            "status": "error",
            "message": "Erro interno do servidor",
            "error": str(e)
        }), 500
    finally:
        if conn:
            conn.close()

@bp_home.get("/dashboard/kpis")
@login_required
def get_dashboard_kpis():
    """
    Endpoint apenas para KPIs (útil para atualização em tempo real).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        kpis = get_kpis(cur)
        conn.close()
        
        return jsonify({
            "status": "success",
            "kpis": kpis,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro ao buscar KPIs: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp_home.get("/dashboard/alertas")
@login_required
def get_dashboard_alertas():
    """
    Endpoint apenas para alertas.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        hoje = date.today()
        daqui_7_dias = hoje + timedelta(days=7)
        
        alertas = []
        alertas.extend(get_nrs_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_documentos_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_contratos_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_financeiro_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_colaboradores_alerts(cur, hoje, daqui_7_dias))
        alertas.extend(get_veiculos_alerts(cur, hoje, daqui_7_dias))
        
        alertas.sort(key=lambda x: x.get('data_vencimento') or '9999-12-31')
        estatisticas = {
            "total": len(alertas),
            "perigo": sum(1 for a in alertas if a["tipo"] == "perigo"),
            "alerta": sum(1 for a in alertas if a["tipo"] == "alerta"),
            "info": sum(1 for a in alertas if a["tipo"] == "info")
        }
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "alertas": alertas,
            "estatisticas": estatisticas,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro ao buscar alertas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp_home.get("/dashboard/graficos")
@login_required
def get_dashboard_graficos():
    """
    Endpoint apenas para gráficos.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        graficos = {
            "colaboradores_por_cargo": get_colaboradores_por_cargo(cur),
            "contratos_por_status": get_contratos_por_status(cur),
            "contas_por_mes": get_contas_por_mes(cur),
            "nrs_status": get_nrs_vencimento_stats(cur)
        }
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "graficos": graficos,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Erro ao buscar gráficos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp_dashboard.route("/")
@login_required
def dashboard_page():
    """
    Renderiza a página do dashboard.
    """
    return render_template("dashboard.html", current_user=current_user)

# ============================================================
# ROTAS DE FILTRO E BUSCA
# ============================================================

@bp_home.get("/dashboard/alertas/filtrar")
@login_required
def filtrar_alertas():
    """
    Filtra alertas por tipo e origem.
    """
    try:
        tipo = request.args.get('tipo')
        origem = request.args.get('origem')
        dias = int(request.args.get('dias', 7))
        
        conn = get_conn()
        cur = conn.cursor()
        
        hoje = date.today()
        data_limite = hoje + timedelta(days=dias)
        
        alertas = []
        # Coleta todos os alertas
        alertas.extend(get_nrs_alerts(cur, hoje, data_limite))
        alertas.extend(get_documentos_alerts(cur, hoje, data_limite))
        alertas.extend(get_contratos_alerts(cur, hoje, data_limite))
        alertas.extend(get_financeiro_alerts(cur, hoje, data_limite))
        alertas.extend(get_colaboradores_alerts(cur, hoje, data_limite))
        alertas.extend(get_veiculos_alerts(cur, hoje, data_limite))
        
        # Aplica filtros
        if tipo:
            alertas = [a for a in alertas if a["tipo"] == tipo]
        if origem:
            alertas = [a for a in alertas if a["origem"] == origem]
        
        alertas.sort(key=lambda x: x.get('data_vencimento') or '9999-12-31')
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "alertas": alertas,
            "filtros": {"tipo": tipo, "origem": origem, "dias": dias},
            "total": len(alertas)
        })
    except Exception as e:
        logger.error(f"Erro ao filtrar alertas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp_home.get("/dashboard/nrs/proximas")
@login_required
def get_nrs_proximas():
    """
    Endpoint específico para NRs próximas do vencimento.
    """
    try:
        dias = int(request.args.get('dias', 30))
        
        conn = get_conn()
        cur = conn.cursor()

        if not table_exists(cur, "nrs_colaboradores"):
            conn.close()
            return jsonify({"status": "success", "nrs": [], "total": 0})

        hoje = date.today()
        data_limite = hoje + timedelta(days=dias)

        cur.execute("""
            SELECT 
                nc.id,
                c.nome as colaborador_nome,
                c.id as colaborador_id,
                n.codigo as nr_codigo,
                n.nome as nr_nome,
                nc.data_validade,
                DATE_PART('day', nc.data_validade - CURRENT_DATE)::integer as dias_para_vencer
            FROM nrs_colaboradores nc
            JOIN colaboradores c ON c.id = nc.colaborador_id
            JOIN nrs n ON n.id = nc.nr_id
            WHERE c.status = 'ativo'
                AND nc.data_validade BETWEEN %s AND %s
            ORDER BY nc.data_validade ASC;
        """, (hoje, data_limite))

        nrs = []
        for row in cur.fetchall():
            nrs.append({
                "id": row[0],
                "colaborador_id": row[2],
                "colaborador_nome": row[1],
                "nr_codigo": row[3],
                "nr_nome": row[4],
                "data_validade": row[5].isoformat(),
                "dias_para_vencer": row[6],
                "status": "alerta" if row[6] <= 7 else "info"
            })

        conn.close()
        
        return jsonify({
            "status": "success",
            "nrs": nrs,
            "total": len(nrs),
            "periodo_dias": dias
        })
    except Exception as e:
        logger.error(f"Erro ao buscar NRs próximas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# ROTAS DE RELATÓRIOS
# ============================================================

@bp_home.get("/dashboard/relatorio/vencimentos")
@login_required
def get_relatorio_vencimentos():
    """
    Gera relatório consolidado de vencimentos.
    """
    try:
        periodo = request.args.get('periodo', '30')  # dias
        
        conn = get_conn()
        cur = conn.cursor()
        
        hoje = date.today()
        data_limite = hoje + timedelta(days=int(periodo))
        
        relatorio = {
            "periodo": periodo,
            "data_geracao": datetime.now().isoformat(),
            "total_alertas": 0,
            "categorias": {}
        }
        
        # Coleta alertas de cada categoria
        categorias = [
            ("NRs", get_nrs_alerts(cur, hoje, data_limite)),
            ("Documentos", get_documentos_alerts(cur, hoje, data_limite)),
            ("Contratos", get_contratos_alerts(cur, hoje, data_limite)),
            ("Financeiro", get_financeiro_alerts(cur, hoje, data_limite)),
            ("Colaboradores", get_colaboradores_alerts(cur, hoje, data_limite)),
            ("Veículos", get_veiculos_alerts(cur, hoje, data_limite))
        ]
        
        for nome, alertas_categoria in categorias:
            if alertas_categoria:
                relatorio["categorias"][nome] = {
                    "total": len(alertas_categoria),
                    "perigo": sum(1 for a in alertas_categoria if a["tipo"] == "perigo"),
                    "alerta": sum(1 for a in alertas_categoria if a["tipo"] == "alerta"),
                    "info": sum(1 for a in alertas_categoria if a["tipo"] == "info")
                }
                relatorio["total_alertas"] += len(alertas_categoria)
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "relatorio": relatorio
        })
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

