## Deploy Seguro — Patagonia Topografia (Produção v2.0)
## Deploy Seguro e Automatizado — Patagonia Topografia (Produção)

**Resumo:** Configuração otimizada para Google Cloud Run na região `southamerica-east1`, com banco de dados **Supabase** (externo), armazenamento de arquivos no **Google Cloud Storage (GCS)** e segurança reforçada.
**Resumo:** Deploy de alta segurança no Google Cloud Run. As senhas **não** são armazenadas em código. O script gerencia credenciais via **Google Secret Manager**.

Pré-requisitos
- `gcloud` instalado e autenticado (`gcloud auth login`).
- APIs habilitadas: `run.googleapis.com`, `cloudbuild.googleapis.com`, `artifactregistry.googleapis.com`, `secretmanager.googleapis.com`.
- Permissões para criar Service Accounts, Secrets e Artifact Registry.

Arquivos de deploy incluídos
- `deploy_cloudrun.sh` — **(Recomendado)** Script para Bash (Linux/macOS/WSL) que automatiza todo o processo: cria/atualiza secrets, cria Service Account, faz o build da imagem, envia para o Artifact Registry e realiza o deploy no Cloud Run.
- `deploy_cloudrun.ps1` — Equivalente em PowerShell (Windows).
- `deploy_cloudrun.sh` — Script principal. Automatiza criação de secrets, service accounts, build e deploy.

Configurações de Produção (Já definidas no script `deploy_cloudrun.sh`)
- `REGION`: `southamerica-east1`
- `DB_HOST`: `db.tuygqepfmhxofsikghsm.supabase.co` (Supabase)
- `DB_SSLMODE`: `require` (Obrigatório para conexão segura)
- `GCS_BUCKET`: `patagonia-uploads-prod-123456`
- `ENV=production`: Ativa cookies seguros (`Secure`, `HttpOnly`).
- `SECRET_KEY` (Secret Manager) — obrigatório em produção.
- `STORAGE_DRIVER` — `gcs` (recomendado) ou `local`.
- `GCS_BUCKET`, `UPLOADS_PREFIX` — quando `STORAGE_DRIVER=gcs`.
- `LOCAL_STORAGE_PATH` — quando `STORAGE_DRIVER=local` (em Cloud Run, use `/tmp/uploads`).
- `REDIS_URL` (Secret Manager, opcional) — sessões server-side (evita perda de sessão ao escalar).
- `ENABLE_DEBUG_ROUTES` — manter `0` em produção.
- `SECRET_KEY`: Gerada automaticamente e salva no Secret Manager.
- `DB_PASS`: Solicitada interativamente (input oculto) e salva no Secret Manager.
- `GOOGLE_API_KEY`: Solicitada interativamente e salva no Secret Manager.
- **Proteção contra Bots**:
  - `MAX_INSTANCES=10` (Evita estouro de custos em DDoS).
  - `MIN_INSTANCES=1` (Evita cold start).

Fluxo recomendado (resumido)
1. **Autenticação:** `gcloud auth login`
2. **Configuração do Projeto:** `gcloud config set project patagonia-994314448036`
3. **Execução do Script (Linux/macOS/WSL):**
Fluxo de Execução
1. **Autenticação:**
   ```bash
   gcloud auth login
   ```
2. **Execução do Script:**
   ```bash
   - Dê permissão de execução: `chmod +x deploy_cloudrun.sh`
   - Execute: `./deploy_cloudrun.sh`
4. **Responda aos Prompts:** O script pedirá a URL do Redis (opcional). Você pode simplesmente pressionar Enter para não usá-lo.
   ./deploy_cloudrun.sh
   ```
3. **Inserção de Credenciais:**
   - Se for a primeira vez, o script irá pausar e pedir a **Senha do Banco** e a **API Key**.
   - Digite (ou cole) e aperte Enter. O texto não aparecerá na tela.
   - O script salvará tudo na nuvem e prosseguirá com o deploy.

Segurança e boas práticas
- **Gerenciamento de Segredos:** O script usa o **Google Secret Manager** para armazenar `SECRET_KEY`, `DB_PASS` e `REDIS_URL`. **Nunca** comite senhas ou chaves diretamente no repositório.
- **Princípio do Menor Privilégio:** O script cria uma Service Account (`patagonia-run-sa`) dedicada para o Cloud Run com permissões mínimas: acesso aos secrets (`secretmanager.secretAccessor`) e ao bucket de uploads (`storage.objectUser`).
- **Proteção contra Bots**: O script define `min-instances=1` para evitar latência inicial e `max-instances=10` para limitar custos em caso de ataque.
- **Dados Sensíveis**: A conexão com o banco de dados é forçada a usar criptografia via SSL (`DB_SSLMODE=require`).
- **Controle de Acesso:** O código backend agora possui um decorador `@require_admin` funcional, integrado com o sistema de usuários e cargos, que protege todos os endpoints administrativos e financeiros.
- **Segurança Adicional:** Para proteção máxima, considere usar o **Cloud Armor** na frente do Cloud Run para criar regras de firewall e mitigar ataques DDoS.

Alta disponibilidade (prático)
- Cloud Run: use `min-instances=1` (ou mais) para reduzir cold start e “queda” por instância fria.
- Banco: O Supabase já gerencia a disponibilidade. O script configura timeout de conexão para evitar travamentos.
- Uploads: `STORAGE_DRIVER=gcs` é a configuração correta, pois o disco local do Cloud Run é efêmero e não compartilhado entre instâncias.

Comandos rápidos (exemplos)
PowerShell (script):
1. `gcloud auth login`
2. `.\deploy_cloudrun.ps1` — responda aos prompts

Bash (script):
1. `gcloud auth login`
2. `chmod +x deploy_cloudrun.sh`
3. `./deploy_cloudrun.sh` — responda aos prompts

Testes pós-deploy
- **Verificar URL:** O script exibirá a URL do serviço no final.
- **Verificar Logs:** Acesse o Google Cloud Console -> Cloud Run -> patagonia -> Logs para ver os logs da aplicação em tempo real.
- **Monitoramento:** Use o Cloud Monitoring para criar dashboards e alertas para métricas como latência, contagem de requisições e erros 5xx.

Notas do repositório
- `wsgi.py` e `requirements.txt` já estão preparados (`gunicorn` presente).
- `Dockerfile` já executa o container como usuário não-root (`patagonia_user`) e usa `:${PORT:-8080}` no `gunicorn` CMD.
