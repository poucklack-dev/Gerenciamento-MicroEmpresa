BEGIN;
CREATE TABLE IF NOT EXISTS public.empresa (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    nome_fantasia TEXT NOT NULL DEFAULT 'Aurora Serviços Empresariais',
    razao_social TEXT, cpf_cnpj TEXT, telefone TEXT, email TEXT, endereco TEXT,
    cidade TEXT, estado CHAR(2), cep TEXT, segmento TEXT DEFAULT 'Serviços',
    responsavel TEXT, cor_institucional TEXT DEFAULT '#167052',
    atualizado_em TIMESTAMP DEFAULT NOW()
);
INSERT INTO public.empresa (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
COMMIT;
