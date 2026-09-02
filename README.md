# Patagonia Topografia — Gestão Empresarial

## Sobre

Aplicação web interna para centralizar rotinas administrativas e operacionais da Patagonia Topografia. O sistema reúne cadastros, documentos, contratos, equipes externas, jornada de trabalho e informações financeiras em uma interface única.

## Funcionalidades

- autenticação por usuário e senha, sessão e perfis administrativos;
- dashboard com indicadores, gráficos, alertas e vencimentos;
- clientes, contatos e serviços vinculados;
- colaboradores, NRs, EPIs, habilidades e dependências cadastrais;
- ponto por CPF/reconhecimento facial, geolocalização e banco de horas;
- saídas e retornos de equipes em campo, veículos, clientes e anexos;
- contratos, valores, histórico e arquivos;
- contas a pagar e a receber, categorias, comprovantes e baixas;
- visão financeira consolidada, custos de veículos e despesas;
- documentos, categorias, vencimentos e uploads;
- fornecedores e vínculos com contratos;
- perfil e administração de usuários.

## Tecnologias

Python 3.11, Flask, Jinja, PostgreSQL, JavaScript, HTML e CSS. A aplicação usa Flask-Login, Flask-Limiter e Flask-Talisman; uploads podem usar o filesystem local ou Google Cloud Storage. Redis é opcional para sessões no servidor. Gunicorn e Docker suportam a execução em produção. O procedimento específico para Google Cloud Run está em `README_DEPLOY_UPDATED.md`.

## Arquitetura

`app.py` configura a aplicação Flask e registra os blueprints. `backend/` contém páginas e APIs por domínio, `core/` reúne banco, autenticação, limites e armazenamento, `templates/` contém as telas Jinja e `static/` os ativos públicos. O acesso a dados usa SQL PostgreSQL diretamente via `psycopg2`.

## Estrutura de pastas

```text
backend/       blueprints e regras dos módulos
core/          serviços compartilhados
templates/     layout global e telas Jinja
static/        imagens, manifesto e service worker
tests/         testes automatizados
infra/         configuração de implantação
uploads/       arquivos locais (não versionados)
```

## Instalação

1. Instale Python 3.11 e PostgreSQL.
2. Crie e ative um ambiente virtual.
3. Execute `pip install -r requirements.txt`.
4. Copie `.env.example` para `.env` e ajuste os valores.
5. Inicialize um banco compatível com o schema utilizado pela aplicação. O arquivo `patagonia_dump.sql` representa o conjunto mais completo de tabelas legado; revise-o antes de importar em um ambiente com dados.

## Configuração

As opções principais são `ENV`, `SECRET_KEY`, `DATABASE_URL` ou as variáveis `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASS`. Para arquivos, configure `STORAGE_DRIVER=local` e `LOCAL_STORAGE_PATH`, ou `STORAGE_DRIVER=gcs`, `GCS_BUCKET` e `UPLOADS_PREFIX`. `REDIS_URL` habilita sessões no servidor. Rotas diagnósticas só devem ser habilitadas temporariamente com `ENABLE_DEBUG_ROUTES=1`.

Nunca publique o arquivo `.env`, dumps com dados reais, uploads, fotos ou credenciais de serviço.

## Banco de dados

O projeto não possui uma ferramenta formal de migrations. Os SQLs existentes não são equivalentes: `01_schema.sql` é uma base reduzida e `patagonia_dump.sql` contém entidades adicionais usadas pelo código. Faça backup e valide o destino antes de qualquer importação; não aplique os arquivos indiscriminadamente sobre produção.

## Execução

Desenvolvimento:

```powershell
python run_dev.py
```

Produção local:

```powershell
gunicorn -c gunicorn.conf.py wsgi:app
```

Com Docker, configure as variáveis necessárias e execute `docker compose up --build`.

## Testes

```powershell
python -m pytest -q
```

Os testes de rotas que dependem do PostgreSQL exigem um banco compatível ou mocks explícitos.

## Screenshots

Adicione imagens sem dados pessoais em `docs/screenshots/` e referencie-as aqui antes da publicação.
