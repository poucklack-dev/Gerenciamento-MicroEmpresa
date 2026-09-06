-- Patagonia Topografia - schema oficial do banco de dados
-- Contém somente a estrutura necessária para executar o projeto, sem dados reais.

CREATE TABLE IF NOT EXISTS public.usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    usuario TEXT UNIQUE NOT NULL,
    senha_hash TEXT,
    cargo TEXT,
    email TEXT,
    telefone TEXT,
    cpf TEXT,
    status TEXT DEFAULT 'ativo',
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW(),
    foto TEXT,
    facial_cadastrado BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    role TEXT
);

CREATE TABLE IF NOT EXISTS public.colaboradores (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    cargo TEXT,
    funcao TEXT,
    status TEXT,
    email TEXT,
    telefone TEXT,
    cnh TEXT,
    validade_cnh DATE,
    endereco TEXT,
    salario NUMERIC(14,2),
    data_admissao DATE,
    data_demissao DATE,
    foto TEXT,
    foto_path TEXT,
    cpf TEXT,
    data_nascimento DATE,
    rg TEXT,
    orgao_emissor TEXT,
    pis_pasep TEXT,
    ctps_numero TEXT,
    ctps_serie TEXT,
    estado_civil TEXT,
    nome_mae TEXT,
    nome_pai TEXT,
    titulo_eleitor TEXT,
    comprovante_residencia TEXT,
    comprovante_escolaridade TEXT,
    banco TEXT,
    agencia TEXT,
    conta TEXT,
    aso_admissional TEXT,
    aso_periodico TEXT,
    aso_mudanca_funcao TEXT,
    aso_retorno_trabalho TEXT,
    aso_demissional TEXT,
    validade_aso DATE,
    exames_complementares TEXT,
    afastamento_tipo TEXT,
    afastamento_inicio DATE,
    afastamento_fim DATE,
    afastamento_laudo TEXT,
    nr01_validade DATE,
    nr06_validade DATE,
    nr10_validade DATE,
    nr11_validade DATE,
    nr12_validade DATE,
    nr17_validade DATE,
    nr18_validade DATE,
    nr33_validade DATE,
    nr35_validade DATE,
    curso_topografia_validade DATE,
    curso_estacao_total_validade DATE,
    curso_gnss_validade DATE,
    curso_drone_validade DATE,
    anac_rpa_validade DATE,
    curso_iso9001_validade DATE,
    curso_iso14001_validade DATE,
    brigada_incendio_validade DATE,
    primeiros_socorros_validade DATE,
    crea_numero TEXT,
    crea_validade DATE,
    cria_profissao TEXT,
    art_responsavel TEXT,
    saldo_ferias NUMERIC(10,2),
    ferias_ultimo_periodo_inicio DATE,
    ferias_ultimo_periodo_fim DATE,
    ferias_agendadas_inicio DATE,
    ferias_agendadas_fim DATE,
    termo_responsabilidade_veiculo TEXT,
    apto_dirigir BOOLEAN,
    aso_admissional_status TEXT,
    aso_admissional_data DATE,
    aso_periodico_status TEXT,
    aso_periodico_data DATE,
    aso_mudanca_funcao_status TEXT,
    aso_mudanca_funcao_data DATE,
    aso_retorno_trabalho_status TEXT,
    aso_retorno_trabalho_data DATE,
    aso_demissional_status TEXT,
    aso_demissional_data DATE,
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.nrs (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT UNIQUE NOT NULL,
    nome TEXT,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS public.nrs_colaboradores (
    id BIGSERIAL PRIMARY KEY,
    colaborador_id BIGINT NOT NULL REFERENCES public.colaboradores(id) ON DELETE CASCADE,
    nr_id BIGINT NOT NULL REFERENCES public.nrs(id) ON DELETE RESTRICT,
    data_emissao DATE,
    data_validade DATE,
    certificado_path TEXT,
    UNIQUE (colaborador_id, nr_id)
);

CREATE INDEX IF NOT EXISTS idx_nrs_colaboradores_validade
    ON public.nrs_colaboradores(data_validade);

CREATE TABLE IF NOT EXISTS public.epis (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS public.epis_colaboradores (
    id BIGSERIAL PRIMARY KEY,
    colaborador_id BIGINT,
    epi_id BIGINT,
    data_entrega DATE,
    assinatura BOOLEAN,
    criado_em TIMESTAMP DEFAULT NOW(),
    UNIQUE (colaborador_id, epi_id),
    FOREIGN KEY (colaborador_id) REFERENCES public.colaboradores(id) ON DELETE CASCADE,
    FOREIGN KEY (epi_id) REFERENCES public.epis(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS public.habilidades (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS public.habilidades_colaboradores (
    id BIGSERIAL PRIMARY KEY,
    colaborador_id BIGINT,
    habilidade_id BIGINT,
    nivel TEXT,
    criado_em TIMESTAMP DEFAULT NOW(),
    UNIQUE (colaborador_id, habilidade_id),
    FOREIGN KEY (colaborador_id) REFERENCES public.colaboradores(id) ON DELETE CASCADE,
    FOREIGN KEY (habilidade_id) REFERENCES public.habilidades(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS public.clientes (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    cpf_cnpj TEXT,
    tipo TEXT,
    email TEXT,
    telefone TEXT,
    endereco TEXT,
    cidade TEXT,
    estado TEXT,
    cep TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    responsavel TEXT,
    observacoes TEXT,
    status TEXT DEFAULT 'ativo',
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.contatos (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    telefone TEXT,
    email TEXT,
    cargo TEXT,
    origem TEXT,
    origem_id BIGINT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.documentos (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT,
    categoria TEXT,
    validade DATE,
    arquivo TEXT,
    tipo_origem TEXT,
    origem_id BIGINT,
    observacoes TEXT,
    status TEXT,
    tamanho_arquivo BIGINT,
    usuario_id BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.contratos (
    id BIGSERIAL PRIMARY KEY,
    codigo_contrato TEXT UNIQUE NOT NULL,
    nome_empresa TEXT,
    descricao_servico TEXT,
    valor_orcado NUMERIC(14,2),
    data_inicio DATE,
    data_fim DATE,
    status TEXT DEFAULT 'ativo',
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW(),
    arquivo TEXT,
    arquivo_nome TEXT
);

CREATE TABLE IF NOT EXISTS public.contas_pagar (
    id BIGSERIAL PRIMARY KEY,
    fornecedor TEXT,
    descricao TEXT,
    valor NUMERIC(14,2),
    vencimento DATE,
    categoria TEXT,
    status TEXT,
    comprovante TEXT,
    comprovante_nome TEXT,
    contrato_id BIGINT REFERENCES public.contratos(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.contas_receber (
    id BIGSERIAL PRIMARY KEY,
    cliente TEXT,
    descricao TEXT,
    valor NUMERIC(14,2),
    vencimento DATE,
    categoria TEXT,
    status TEXT,
    comprovante TEXT,
    comprovante_nome TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.fornecedores (
    id BIGSERIAL PRIMARY KEY,
    nome_fantasia TEXT,
    razao_social TEXT,
    cnpj TEXT UNIQUE,
    inscricao_estadual TEXT,
    inscricao_municipal TEXT,
    telefone TEXT,
    email TEXT,
    site TEXT,
    contato_nome TEXT,
    contato_email TEXT,
    contato_telefone TEXT,
    cep TEXT,
    endereco TEXT,
    numero TEXT,
    complemento TEXT,
    bairro TEXT,
    cidade TEXT,
    estado TEXT,
    categoria TEXT,
    rating TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    prazo_pagamento TEXT,
    forma_pagamento TEXT,
    limite_credito NUMERIC(14,2),
    certificado_iso TEXT,
    validade_documentos DATE,
    observacoes TEXT,
    arquivo_url TEXT,
    contrato_id BIGINT REFERENCES public.contratos(id) ON DELETE SET NULL,
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.equipe_campo (
    id BIGSERIAL PRIMARY KEY,
    colaborador_id BIGINT REFERENCES public.colaboradores(id) ON DELETE SET NULL,
    veiculo_id BIGINT,
    cliente_id BIGINT REFERENCES public.clientes(id) ON DELETE SET NULL,
    data_saida DATE,
    hora_saida TIME,
    km_saida NUMERIC(12,2),
    local_lat DOUBLE PRECISION,
    local_lon DOUBLE PRECISION,
    observacoes TEXT,
    status TEXT,
    anexo_saida TEXT,
    data_retorno DATE,
    hora_retorno TIME,
    km_retorno NUMERIC(12,2),
    anexo_retorno TEXT,
    observacoes_retorno TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.ponto (
    id BIGSERIAL PRIMARY KEY,
    colaborador_id BIGINT REFERENCES public.colaboradores(id) ON DELETE SET NULL,
    data_registro DATE,
    hora_entrada TIMESTAMP,
    hora_saida TIMESTAMP,
    cpf TEXT,
    nome TEXT,
    tipo_registro TEXT,
    observacao TEXT,
    localizacao TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    localizacao_saida TEXT,
    latitude_saida DOUBLE PRECISION,
    longitude_saida DOUBLE PRECISION,
    endereco TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.veiculos (
    id BIGSERIAL PRIMARY KEY,
    placa TEXT UNIQUE NOT NULL,
    modelo TEXT,
    marca TEXT,
    ano INT,
    combustivel TEXT,
    km_atual NUMERIC(12,2),
    status TEXT,
    foto TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.custos_veiculos (
    id BIGSERIAL PRIMARY KEY,
    veiculo_id BIGINT REFERENCES public.veiculos(id) ON DELETE CASCADE,
    contrato_id BIGINT REFERENCES public.contratos(id) ON DELETE SET NULL,
    tipo_custo TEXT,
    descricao TEXT,
    data DATE,
    valor NUMERIC(14,2),
    litros NUMERIC(12,3),
    preco_litro NUMERIC(12,3),
    km_atual NUMERIC(12,2),
    local TEXT,
    fornecedor TEXT,
    observacao TEXT,
    comprovante TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.abastecimentos (
    id BIGSERIAL PRIMARY KEY,
    veiculo_id BIGINT REFERENCES public.veiculos(id) ON DELETE CASCADE,
    data DATE,
    litros NUMERIC(12,3),
    valor_total NUMERIC(14,2),
    km_atual NUMERIC(12,2),
    nota_fiscal TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.quilometragem (
    id BIGSERIAL PRIMARY KEY,
    veiculo_id BIGINT REFERENCES public.veiculos(id) ON DELETE CASCADE,
    data_registro DATE,
    km_inicial NUMERIC(12,2),
    km_final NUMERIC(12,2),
    foto_odometro TEXT,
    observacao TEXT
);

CREATE TABLE IF NOT EXISTS public.fluxo_caixa (
    id BIGSERIAL PRIMARY KEY,
    data DATE,
    tipo TEXT,
    origem TEXT,
    valor NUMERIC(14,2),
    descricao TEXT,
    referencia TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.gastos_contrato (
    id BIGSERIAL PRIMARY KEY,
    contrato_id BIGINT REFERENCES public.contratos(id) ON DELETE CASCADE,
    data_gasto DATE,
    valor NUMERIC(14,2),
    descricao TEXT,
    categoria TEXT,
    comprovante TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.servicos (
    id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT REFERENCES public.clientes(id) ON DELETE CASCADE,
    equipe_id BIGINT REFERENCES public.equipe_campo(id) ON DELETE SET NULL,
    descricao TEXT,
    data DATE,
    valor NUMERIC(14,2),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.logs_sistema (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL,
    acao TEXT,
    detalhes TEXT,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clientes_nome ON public.clientes(nome);
CREATE INDEX IF NOT EXISTS idx_colaboradores_status ON public.colaboradores(status);
CREATE INDEX IF NOT EXISTS idx_contratos_status ON public.contratos(status);
CREATE INDEX IF NOT EXISTS idx_contas_pagar_vencimento ON public.contas_pagar(vencimento);
CREATE INDEX IF NOT EXISTS idx_contas_pagar_status ON public.contas_pagar(status);
CREATE INDEX IF NOT EXISTS idx_contas_receber_vencimento ON public.contas_receber(vencimento);
CREATE INDEX IF NOT EXISTS idx_documentos_validade ON public.documentos(validade);
CREATE INDEX IF NOT EXISTS idx_ponto_colaborador_data ON public.ponto(colaborador_id, data_registro);
CREATE INDEX IF NOT EXISTS idx_logs_sistema_usuario ON public.logs_sistema(usuario_id, criado_em DESC);
