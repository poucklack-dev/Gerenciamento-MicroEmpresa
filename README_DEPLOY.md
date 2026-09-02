# Deploy seguro — Patagonia

Este é um resumo. Para o fluxo recomendado (scripts), veja `README_DEPLOY_UPDATED.md`.

## Variáveis (produção / Cloud Run)
- `ENV=production`
- `SECRET_KEY` (Secret Manager)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS` (Secret Manager)
- `STORAGE_DRIVER` (`gcs` recomendado ou `local`)
- `GCS_BUCKET`, `UPLOADS_PREFIX` (quando `STORAGE_DRIVER=gcs`)
- `LOCAL_STORAGE_PATH` (quando `STORAGE_DRIVER=local`; em Cloud Run use `/tmp/uploads`)
- `REDIS_URL` (Secret Manager, opcional)
- `ENABLE_DEBUG_ROUTES=0` (recomendado em produção)

## Fluxo recomendado
- Windows: `.\deploy_cloudrun.ps1`
- Linux/macOS: `./deploy_cloudrun.sh`

Os scripts criam/atualizam secrets, build/push no Artifact Registry e fazem deploy no Cloud Run com os env vars necessários (você escolhe público ou privado no prompt).

Nota: Cloud Run executa **apenas o container da aplicação**. Para banco de dados, use Cloud SQL (PostgreSQL gerenciado) — não rode Postgres via `docker run` no Cloud Run.
Alternativa: se o seu Postgres for externo (ex.: Supabase), ative pooler/pgbouncer e limite `max-instances`/`concurrency` no Cloud Run para não estourar conexões.

## Arquivos (uploads/anexos)
- As APIs retornam URLs em `/media/<chave>` e o app faz proxy do conteúdo (Local ou GCS).
