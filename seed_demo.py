"""Cria dados fictícios opcionais para a demonstração local do portfólio."""
import os
from dotenv import load_dotenv
from core.auth import hash_senha
from core.database import get_conn

def main():
    load_dotenv()
    if os.getenv("DEMO_SEED", "").strip().lower() not in {"1", "true", "yes"}:
        raise SystemExit("Defina DEMO_SEED=1 para criar os dados de demonstração.")
    password = os.getenv("DEMO_ADMIN_PASSWORD", "")
    username = os.getenv("DEMO_ADMIN_USER", "admin_demo").strip()
    password_hash = hash_senha(password)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO usuarios (nome,usuario,senha_hash,cargo,email,status) VALUES (%s,%s,%s,'admin',%s,'ativo') ON CONFLICT (usuario) DO UPDATE SET nome=EXCLUDED.nome,senha_hash=EXCLUDED.senha_hash,cargo=EXCLUDED.cargo,email=EXCLUDED.email,status='ativo',atualizado_em=NOW()""", ("Administrador Demo",username,password_hash,"admin.demo@example.test"))
        cur.execute("""INSERT INTO empresa(id,nome_fantasia,razao_social,cpf_cnpj,telefone,email,cidade,estado,segmento,responsavel) VALUES(1,'Aurora Serviços Empresariais','Aurora Serviços Empresariais Ltda.','00.000.000/0001-00','(11) 3000-0000','contato@aurora.example.test','São Paulo','SP','Serviços','Administrador Demo') ON CONFLICT(id) DO UPDATE SET nome_fantasia=EXCLUDED.nome_fantasia""")
        cur.execute("""INSERT INTO clientes(nome,cpf_cnpj,tipo,email,telefone,cidade,estado,responsavel,status) SELECT v.* FROM (VALUES ('Almeida Consultoria','11.111.111/0001-11','Pessoa Jurídica','financeiro@almeida.example.test','(11) 3111-1000','São Paulo','SP','Marina Almeida','ativo'),('Café Horizonte','22.222.222/0001-22','Pessoa Jurídica','contato@horizonte.example.test','(11) 3222-2000','Campinas','SP','Paulo Mendes','ativo'),('Estúdio Ipê','33.333.333/0001-33','Pessoa Jurídica','ola@ipe.example.test','(21) 3333-3000','Rio de Janeiro','RJ','Carla Nunes','ativo')) v(nome,cpf_cnpj,tipo,email,telefone,cidade,estado,responsavel,status) WHERE NOT EXISTS(SELECT 1 FROM clientes c WHERE c.cpf_cnpj=v.cpf_cnpj)""")
        cur.execute("""INSERT INTO fornecedores(nome_fantasia,razao_social,cnpj,telefone,email,categoria,ativo,prazo_pagamento) VALUES ('Papelaria Central','Papelaria Central Ltda.','44.444.444/0001-44','(11) 3444-4000','vendas@papelaria.example.test','Material de Escritório',TRUE,'30 dias'),('Conecta Tecnologia','Conecta Tecnologia Ltda.','55.555.555/0001-55','(11) 3555-5000','atendimento@conecta.example.test','Tecnologia',TRUE,'15 dias') ON CONFLICT(cnpj) DO NOTHING""")
        cur.execute("""INSERT INTO colaboradores(nome,cargo,funcao,status,email,telefone,data_admissao,cpf) SELECT v.* FROM (VALUES ('Beatriz Costa','Analista Financeiro','Financeiro','ativo','beatriz.costa@example.test','(11) 90000-1001',CURRENT_DATE-INTERVAL '18 months','111.111.111-11'),('Rafael Lima','Assistente Administrativo','Administrativo','ativo','rafael.lima@example.test','(11) 90000-1002',CURRENT_DATE-INTERVAL '9 months','222.222.222-22')) v(nome,cargo,funcao,status,email,telefone,data_admissao,cpf) WHERE NOT EXISTS(SELECT 1 FROM colaboradores c WHERE c.cpf=v.cpf)""")
        cur.execute("""INSERT INTO contratos(codigo_contrato,nome_empresa,descricao_servico,valor_orcado,data_inicio,data_fim,status) VALUES ('DEMO-001','Almeida Consultoria','Apoio administrativo mensal',48000,CURRENT_DATE-INTERVAL '5 months',CURRENT_DATE+INTERVAL '7 months','ativo'),('DEMO-002','Café Horizonte','Consultoria de processos',18500,CURRENT_DATE-INTERVAL '2 months',CURRENT_DATE+INTERVAL '28 days','ativo') ON CONFLICT(codigo_contrato) DO NOTHING""")
        cur.execute("""INSERT INTO contas_receber(cliente,descricao,valor,vencimento,categoria,status) SELECT v.* FROM (VALUES ('Almeida Consultoria','Mensalidade de serviços',8450.00,CURRENT_DATE-INTERVAL '5 days','Serviços','recebido'),('Café Horizonte','Parcela de consultoria',4200.00,CURRENT_DATE+INTERVAL '8 days','Consultoria','pendente'),('Estúdio Ipê','Serviços administrativos',3100.00,CURRENT_DATE-INTERVAL '4 days','Serviços','pendente')) v(cliente,descricao,valor,vencimento,categoria,status) WHERE NOT EXISTS(SELECT 1 FROM contas_receber WHERE descricao=v.descricao AND cliente=v.cliente)""")
        cur.execute("""INSERT INTO contas_pagar(fornecedor,descricao,valor,vencimento,categoria,status) SELECT v.* FROM (VALUES ('Papelaria Central','Materiais de escritório',680.00,CURRENT_DATE-INTERVAL '3 days','Material de Escritório','pago'),('Conecta Tecnologia','Assinaturas de software',1290.00,CURRENT_DATE+INTERVAL '6 days','Softwares e Licenças','pendente'),('Imobiliária Exemplo','Aluguel do escritório',2800.00,CURRENT_DATE-INTERVAL '2 days','Aluguel','pendente')) v(fornecedor,descricao,valor,vencimento,categoria,status) WHERE NOT EXISTS(SELECT 1 FROM contas_pagar WHERE descricao=v.descricao AND fornecedor=v.fornecedor)""")
        cur.execute("""INSERT INTO documentos(nome,categoria,validade,tipo_origem,observacoes,status) SELECT v.* FROM (VALUES ('Contrato social','Empresa',CURRENT_DATE+INTERVAL '1 year','empresa','Documento demonstrativo','ativo'),('Certificado de serviço','Contratos',CURRENT_DATE+INTERVAL '25 days','contrato','Documento fictício','ativo')) v(nome,categoria,validade,tipo_origem,observacoes,status) WHERE NOT EXISTS(SELECT 1 FROM documentos WHERE nome=v.nome)""")
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: cur.close(); conn.close()
    print(f"Demonstração pronta: {username} e dados fictícios da Aurora.")

if __name__ == "__main__": main()
