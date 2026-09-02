#!/bin/bash
# ===================================================================================
#  PATAGONIA TOPOGRAFIA - SCRIPT DE DEPLOY AUTOMATIZADO PARA GOOGLE CLOUD RUN
# ===================================================================================
#
#  Este script realiza o deploy completo da aplicação no Google Cloud Run.
#  - Cria e gerencia segredos no Secret Manager.
#  - Cria uma Service Account dedicada com permissões mínimas.
#  - Faz o build da imagem do container via Cloud Build.
#  - Envia a imagem para o Artifact Registry.
#  - Realiza o deploy (ou atualização) do serviço no Cloud Run.
#
#  Uso:
#  1. Autentique-se no gcloud: gcloud auth login
#  2. Configure o projeto: gcloud config set project SEU_PROJECT_ID
#  3. Dê permissão de execução: chmod +x deploy_cloudrun.sh
#  4. Execute: ./deploy_cloudrun.sh
#
# ===================================================================================

# --- Configurações Iniciais (Altere se necessário) ---
# Project ID do Google Cloud
PROJECT_ID="patagonia-994314448036"
# Nome do serviço no Cloud Run
SERVICE_NAME="patagonia"
# Região do deploy
REGION="southamerica-east1"
# Nome do repositório no Artifact Registry
ARTIFACT_REPO_NAME="patagonia-repo"
# Nome da imagem do container
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO_NAME}/${SERVICE_NAME}:latest"
# Nome da Service Account que será criada para o Cloud Run
SERVICE_ACCOUNT_NAME="patagonia-run-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
# Nome do bucket no Google Cloud Storage para uploads
GCS_BUCKET_NAME="patagonia-uploads-prod-123456"
# Host do banco de dados (Supabase)
DB_HOST="db.tuygqepfmhxofsikghsm.supabase.co"

# --- Nomes dos Segredos no Secret Manager ---
SECRET_KEY_NAME="patagonia-secret-key"
DB_PASS_SECRET_NAME="patagonia-db-pass"
REDIS_URL_SECRET_NAME="patagonia-redis-url"

# --- Funções de Apoio ---
# Função para imprimir mensagens de log formatadas
log() {
    echo -e "\n[INFO] $1"
}

# Função para imprimir mensagens de erro e sair
error() {
    echo -e "\n[ERRO] $1" >&2
    exit 1
}

# Função para verificar se um comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Função para habilitar APIs do Google Cloud
enable_api() {
    local api_name=$1
    log "Verificando se a API ${api_name} está habilitada..."
    if ! gcloud services list --enabled --filter="name:${api_name}" --format="value(name)" | grep -q .; then
        log "Habilitando API ${api_name}..."
        gcloud services enable "${api_name}" || error "Falha ao habilitar a API ${api_name}. Verifique suas permissões."
    else
        log "API ${api_name} já está habilitada."
    fi
}

# Função para criar/atualizar um segredo no Secret Manager
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    log "Verificando segredo '${secret_name}'..."
    if gcloud secrets describe "${secret_name}" --project "${PROJECT_ID}" &>/dev/null; then
        log "Segredo '${secret_name}' já existe. Atualizando para a nova versão."
        echo -n "${secret_value}" | gcloud secrets versions add "${secret_name}" --data-file=- --project "${PROJECT_ID}"
    else
        log "Criando segredo '${secret_name}'..."
        echo -n "${secret_value}" | gcloud secrets create "${secret_name}" --data-file=- --replication-policy="automatic" --project "${PROJECT_ID}"
    fi
    log "Segredo '${secret_name}' configurado com sucesso."
}

# --- Início da Execução do Script ---

# 1. Verificação de pré-requisitos
log "Verificando pré-requisitos..."
command_exists gcloud || error "O 'gcloud' CLI não foi encontrado. Por favor, instale e configure o Google Cloud SDK."
gcloud auth print-identity-token &>/dev/null || error "Você não está autenticado no gcloud. Execute 'gcloud auth login' e 'gcloud auth application-default login'."

log "Configurando projeto para '${PROJECT_ID}'..."
gcloud config set project "${PROJECT_ID}"

# 2. Habilitar APIs necessárias
enable_api "run.googleapis.com"
enable_api "cloudbuild.googleapis.com"
enable_api "artifactregistry.googleapis.com"
enable_api "secretmanager.googleapis.com"

# 3. Gerenciamento de Segredos
log "Gerenciando segredos no Secret Manager..."

# -- Chave Secreta da Aplicação (SECRET_KEY) --
# Gera uma chave segura se ela ainda não existir
log "Verificando a chave secreta da aplicação ('${SECRET_KEY_NAME}')..."
if ! gcloud secrets describe "${SECRET_KEY_NAME}" --project "${PROJECT_ID}" &>/dev/null; then
    log "Nenhuma SECRET_KEY encontrada. Gerando uma nova chave segura..."
    # Gera 32 bytes de dados aleatórios e codifica em base64
    new_secret_key=$(head -c 32 /dev/urandom | base64)
    create_or_update_secret "${SECRET_KEY_NAME}" "${new_secret_key}"
else
    log "Chave secreta da aplicação já existe no Secret Manager."
fi

# -- Senha do Banco de Dados (DB_PASS) --
log "Verificando a senha do banco de dados ('${DB_PASS_SECRET_NAME}')..."
if ! gcloud secrets describe "${DB_PASS_SECRET_NAME}" --project "${PROJECT_ID}" &>/dev/null; then
    log "A senha do banco de dados não foi encontrada no Secret Manager."
    echo -n "Por favor, insira a senha do banco de dados (PostgreSQL): "
    read -rsp db_password
    echo
    if [ -z "$db_password" ]; then
        error "A senha do banco de dados não pode ser vazia."
    fi
    create_or_update_secret "${DB_PASS_SECRET_NAME}" "${db_password}"
else
    log "Senha do banco de dados já existe no Secret Manager."
fi

# -- URL do Redis (Opcional) --
log "Verificando a URL do Redis ('${REDIS_URL_SECRET_NAME}')..."
if ! gcloud secrets describe "${REDIS_URL_SECRET_NAME}" --project "${PROJECT_ID}" &>/dev/null; then
    log "A URL do Redis não foi encontrada no Secret Manager."
    read -rp "Insira a URL de conexão do Redis (opcional, pressione Enter para pular): " redis_url
    if [ -n "$redis_url" ]; then
        create_or_update_secret "${REDIS_URL_SECRET_NAME}" "${redis_url}"
    else
        log "Nenhuma URL do Redis fornecida. A aplicação usará sessões in-memory."
        # Cria um segredo com valor vazio para evitar erros no deploy
        create_or_update_secret "${REDIS_URL_SECRET_NAME}" " "
    fi
else
    log "URL do Redis já existe no Secret Manager."
fi


# 4. Configurar Artifact Registry
log "Configurando o repositório do Artifact Registry..."
if ! gcloud artifacts repositories describe "${ARTIFACT_REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    log "Criando repositório Docker no Artifact Registry: '${ARTIFACT_REPO_NAME}'"
    gcloud artifacts repositories create "${ARTIFACT_REPO_NAME}" \
        --repository-format="docker" \
        --location="${REGION}" \
        --description="Repositório para imagens da aplicação Patagonia" \
        --project="${PROJECT_ID}"
else
    log "Repositório '${ARTIFACT_REPO_NAME}' já existe."
fi

# 5. Criar Service Account e Atribuir Permissões
log "Configurando a Service Account '${SERVICE_ACCOUNT_NAME}'..."
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
    log "Criando Service Account..."
    gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --display-name="Service Account para Patagonia Cloud Run" \
        --project="${PROJECT_ID}"
else
    log "Service Account já existe."
fi

log "Atribuindo permissões à Service Account..."
# Permissão para acessar os segredos
gcloud secrets add-iam-policy-binding "${SECRET_KEY_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"

gcloud secrets add-iam-policy-binding "${DB_PASS_SECRET_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"

gcloud secrets add-iam-policy-binding "${REDIS_URL_SECRET_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"

# Permissão para ler/escrever no bucket do GCS
gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.objectUser"


# 6. Build da Imagem com Cloud Build
log "Iniciando o build da imagem do container com Cloud Build..."
gcloud builds submit . \
    --tag="${IMAGE_NAME}" \
    --project="${PROJECT_ID}" || error "Falha no build da imagem com Cloud Build."
log "Build da imagem concluído com sucesso."

# 7. Deploy no Cloud Run
log "Iniciando o deploy do serviço '${SERVICE_NAME}' no Cloud Run..."

# Constrói a lista de variáveis de ambiente e segredos
env_vars=(
    "ENV=production"
    "STORAGE_DRIVER=gcs"
    "GCS_BUCKET=${GCS_BUCKET_NAME}"
    "DB_HOST=${DB_HOST}"
    "DB_PORT=5432"
    "DB_NAME=postgres"
    "DB_USER=postgres"
    "DB_SSLMODE=require"
    "PYTHONUNBUFFERED=1"
)

secrets_vars=(
    "SECRET_KEY=${SECRET_KEY_NAME}:latest"
    "DB_PASS=${DB_PASS_SECRET_NAME}:latest"
    "REDIS_URL=${REDIS_URL_SECRET_NAME}:latest"
)

# Converte os arrays para o formato que o gcloud espera
env_vars_str=$(IFS=,; echo "${env_vars[*]}")
secrets_vars_str=$(IFS=,; echo "${secrets_vars[*]}")

gcloud run deploy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${IMAGE_NAME}" \
    --service-account="${SERVICE_ACCOUNT_EMAIL}" \
    --allow-unauthenticated \ # Permite que a internet acesse o serviço. A segurança é gerenciada DENTRO da aplicação Flask (com @require_admin, login, etc.).
                              # Para uma camada extra de segurança, troque por --no-allow-unauthenticated e configure um Load Balancer com IAP (Identity-Aware Proxy).
    --port=8080 \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=80 \
    --cpu=1 \
    --memory=512Mi \
    --set-env-vars="${env_vars_str}" \
    --set-secrets="${secrets_vars_str}" \
    --platform="managed"

if [ $? -eq 0 ]; then
    log "Deploy concluído com sucesso!"
    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform="managed" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
    log "A aplicação está disponível em: ${SERVICE_URL}"
else
    error "Ocorreu um erro durante o deploy. Verifique os logs acima."
fi

log "Limpeza: Por segurança, considere remover a senha do banco de dados do seu histórico de shell se você a digitou."
log "Lembre-se que a senha já está segura no Secret Manager para os próximos deploys."

exit 0
