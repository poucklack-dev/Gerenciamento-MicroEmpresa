# Aurora Gestão

Plataforma web de gestão empresarial desenvolvida para centralizar processos administrativos e financeiros de micro e pequenas empresas.

O projeto funciona como um ERP/backoffice leve: ajuda proprietários e gestores a acompanhar receitas, despesas, resultado, contas pendentes, clientes, fornecedores, contratos, colaboradores e documentos sem tentar substituir um sistema contábil, fiscal, CRM ou RH completo.

## Visão do produto

- dashboard executivo orientado a dinheiro e pendências;
- visão financeira, contas a pagar e contas a receber;
- cadastros relacionais de clientes, fornecedores e contratos;
- administração de colaboradores e banco de horas;
- central de documentos e vencimentos;
- frota e deslocamentos como recurso complementar;
- configuração da identidade da empresa;
- interface compacta e responsiva para rotinas administrativas.

Funcionalidades herdadas do projeto original foram reposicionadas: quilometragem está em **Frota e deslocamentos**, certificações fazem parte de **Colaboradores/Documentos** e atividades externas deixaram de competir com o núcleo administrativo.

## Stack

- Python 3.11, Flask e Jinja;
- PostgreSQL e psycopg2;
- HTML, CSS e JavaScript;
- Flask-Login, Flask-Limiter e Flask-Talisman;
- armazenamento local protegido para anexos;
- Docker Compose;
- Pytest e GitHub Actions.

## Arquitetura

```text
backend/                blueprints e regras por domínio
core/                   autenticação, banco, storage e serviços compartilhados
infra/migrations/       evoluções incrementais e não destrutivas do banco
static/css/             design system e estilos por tela
static/js/              comportamento reutilizável da interface
templates/              páginas Jinja
tests/                  testes automatizados
schema.sql              schema completo para um banco novo
```

`app.py` configura a aplicação e registra os blueprints. O projeto mantém SQL parametrizado e tipos `NUMERIC` para valores monetários. A migration `001_empresa.sql` introduz a configuração central da empresa sem apagar registros existentes.

## Executar com Docker

1. Copie `.env.example` para `.env`.
2. Defina valores locais para `SECRET_KEY` e `DB_PASS`.
3. Inicie:

```powershell
docker compose up --build
```

Acesse `http://localhost:8080`.

Em banco já existente, aplique as migrations em ordem. Para a migration atual:

```powershell
Get-Content -Raw infra/migrations/001_empresa.sql | docker compose exec -T db psql -U patagonia -d patagonia
```

## Demonstração opcional

O seed é idempotente, exige ativação explícita e usa somente pessoas e empresas fictícias. Ele cria a empresa **Aurora Serviços Empresariais**, usuário administrativo, clientes, fornecedores, colaboradores, contratos, documentos e movimentações financeiras demonstrativas.

```powershell
docker compose exec -e DEMO_SEED=1 -e DEMO_ADMIN_PASSWORD="escolha-uma-senha-segura" web python seed_demo.py
```

O usuário padrão do seed é `admin_demo`. Nenhuma senha é versionada.

## Desenvolvimento sem Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run_dev.py
```

## Segurança

- hash de senha PBKDF2 e rate limiting no login;
- autorização administrativa validada no backend;
- consultas parametrizadas;
- cookies `HttpOnly` e `SameSite=Lax`;
- limite de requisição e validação de upload;
- proteção contra path traversal e extensões executáveis;
- segredos, uploads e dados locais ignorados pelo Git.

Use apenas dados fictícios ao demonstrar este repositório.

## Testes

```powershell
python -m pytest -q
```

O workflow em `.github/workflows/tests.yml` executa a suíte em pushes e pull requests.

## Screenshots

Screenshots anonimizados podem ser adicionados em `docs/images/` para demonstrar login, dashboard, financeiro e cadastros.

## Licença

Distribuído sob a [Licença MIT](LICENSE).

## Desenvolvedor

**Emanuel Sousa Vasconcellos Lima**

Desenvolvedor com foco em aplicações web, análise de dados, automação e sistemas de gestão.
