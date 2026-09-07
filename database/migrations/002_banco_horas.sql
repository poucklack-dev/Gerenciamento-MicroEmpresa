BEGIN;
ALTER TABLE public.colaboradores ADD COLUMN IF NOT EXISTS setor TEXT;
ALTER TABLE public.colaboradores ADD COLUMN IF NOT EXISTS chefe_direto_id BIGINT REFERENCES public.colaboradores(id) ON DELETE SET NULL;
ALTER TABLE public.ponto ADD COLUMN IF NOT EXISTS intervalo_minutos INTEGER NOT NULL DEFAULT 0 CHECK (intervalo_minutos >= 0);
ALTER TABLE public.ponto ADD COLUMN IF NOT EXISTS situacao_dia TEXT NOT NULL DEFAULT 'presente' CHECK (situacao_dia IN ('presente','ausente','ausencia_justificada','folga','ferias','afastamento'));

CREATE TABLE IF NOT EXISTS public.banco_horas_periodos (
 id BIGSERIAL PRIMARY KEY, competencia DATE UNIQUE NOT NULL CHECK (competencia = date_trunc('month', competencia)::date),
 metodo_carga TEXT NOT NULL DEFAULT 'direto' CHECK (metodo_carga IN ('calculado','direto')),
 carga_diaria_minutos INTEGER, dias_considerados INTEGER, carga_base_minutos INTEGER NOT NULL DEFAULT 0,
 carga_prevista_padrao_minutos INTEGER NOT NULL DEFAULT 0, observacao TEXT,
 criado_por BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL, criado_em TIMESTAMP DEFAULT NOW(), atualizado_em TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.banco_horas_ajustes (
 id BIGSERIAL PRIMARY KEY, periodo_id BIGINT NOT NULL REFERENCES public.banco_horas_periodos(id) ON DELETE CASCADE,
 minutos INTEGER NOT NULL, motivo TEXT, criado_em TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.banco_horas_colaborador (
 id BIGSERIAL PRIMARY KEY, periodo_id BIGINT NOT NULL REFERENCES public.banco_horas_periodos(id) ON DELETE CASCADE,
 colaborador_id BIGINT NOT NULL REFERENCES public.colaboradores(id) ON DELETE CASCADE,
 horas_previstas_minutos INTEGER, origem_horas TEXT NOT NULL DEFAULT 'registros' CHECK (origem_horas IN ('registros','manual')),
 horas_trabalhadas_manual_minutos INTEGER, origem_frequencia TEXT NOT NULL DEFAULT 'registros' CHECK (origem_frequencia IN ('registros','manual')),
 dias_presentes_manual INTEGER, dias_ausentes_manual INTEGER, excluido_periodo BOOLEAN NOT NULL DEFAULT FALSE,
 motivo_exclusao TEXT, excluido_por BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL, excluido_em TIMESTAMP,
 observacao TEXT, atualizado_por BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL, atualizado_em TIMESTAMP DEFAULT NOW(),
 UNIQUE(periodo_id,colaborador_id)
);
CREATE TABLE IF NOT EXISTS public.banco_horas_auditoria (
 id BIGSERIAL PRIMARY KEY, periodo_id BIGINT REFERENCES public.banco_horas_periodos(id) ON DELETE SET NULL,
 colaborador_id BIGINT REFERENCES public.colaboradores(id) ON DELETE SET NULL, usuario_id BIGINT REFERENCES public.usuarios(id) ON DELETE SET NULL,
 acao TEXT NOT NULL, valor_anterior TEXT, valor_novo TEXT, motivo TEXT, criado_em TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bh_colaborador_periodo ON public.banco_horas_colaborador(periodo_id,colaborador_id);
CREATE INDEX IF NOT EXISTS idx_bh_auditoria_periodo ON public.banco_horas_auditoria(periodo_id,criado_em DESC);
COMMIT;
