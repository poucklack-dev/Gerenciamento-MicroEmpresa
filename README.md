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

Python 3.11, Flask, Jinja, PostgreSQL, JavaScript, HTML e CSS. A aplicação usa Flask-Login, Flask-Limiter e Flask-Talisman; uploads podem usar o filesystem local ou Google Cloud Storage. Redis é opcional para sessões no servidor e Docker facilita a execução do projeto em um ambiente isolado.

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
5. Inicialize o PostgreSQL com o arquivo `schema_patagonia.sql`. Ao usar Docker Compose, isso acontece automaticamente na primeira criação do volume do banco.

## Configuração

As opções principais são `ENV`, `SECRET_KEY`, `DATABASE_URL` ou as variáveis `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASS`. Para arquivos, configure `STORAGE_DRIVER=local` e `LOCAL_STORAGE_PATH`, ou `STORAGE_DRIVER=gcs`, `GCS_BUCKET` e `UPLOADS_PREFIX`. `REDIS_URL` habilita sessões no servidor. Rotas diagnósticas só devem ser habilitadas temporariamente com `ENABLE_DEBUG_ROUTES=1`.

Nunca publique o arquivo `.env`, dumps com dados reais, uploads, fotos ou credenciais de serviço.

## Banco de dados

`schema_patagonia.sql` é a fonte oficial da estrutura do banco e não contém dados reais. O Docker Compose aplica esse arquivo somente quando cria um volume novo do PostgreSQL. O projeto ainda não utiliza uma ferramenta formal de migrations.

## Execução

Desenvolvimento:

```powershell
python run_dev.py
```

Com Docker, configure as variáveis necessárias e execute:

```powershell
docker compose up --build
```

## Testes

```powershell
python -m pytest -q
```

Os testes de rotas que dependem do PostgreSQL exigem um banco compatível ou mocks explícitos.

## Screenshots

Adicione imagens sem dados pessoais em `docs/screenshots/` e referencie-as aqui antes da publicação.

## Desenvolvedor

Emanuel Sousa Vasconcellos Lima

## Licença

Este projeto é distribuído sob a Licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
