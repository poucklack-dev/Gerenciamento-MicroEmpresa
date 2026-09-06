# Patagonia Topografia — Gestão Empresarial

Sistema web para centralizar rotinas administrativas, operacionais e financeiras de uma empresa de topografia. O projeto demonstra desenvolvimento full stack com Flask, PostgreSQL, interface responsiva, controle de acesso, uploads e testes automatizados.

## Screenshots

As imagens do projeto devem ser adicionadas em `docs/images/`, sempre sem dados pessoais ou empresariais reais.

| Tela | Arquivo sugerido |
| --- | --- |
| Login | `docs/images/login.png` |
| Dashboard | `docs/images/dashboard.png` |
| Cadastros | `docs/images/cadastros.png` |
| Relatórios | `docs/images/relatorios.png` |

## Sobre

A aplicação organiza clientes, colaboradores, documentos, contratos, equipes externas, jornada de trabalho e movimentações financeiras. O código foi estruturado por domínios em blueprints Flask e utiliza PostgreSQL com consultas parametrizadas.

## Funcionalidades

- autenticação por usuário e senha;
- administração de usuários com controle de permissão no backend;
- dashboard com indicadores operacionais e financeiros;
- gestão de clientes, contatos e serviços;
- cadastro de colaboradores, NRs, EPIs e habilidades;
- registro de ponto, geolocalização e banco de horas;
- reconhecimento facial para o fluxo de ponto;
- controle de equipes e veículos em campo;
- contratos, contas a pagar e contas a receber;
- documentos, comprovantes e anexos;
- fornecedores, quilometragem e custos de veículos.

## Tecnologias

- Python 3.11 e Flask;
- PostgreSQL e psycopg2;
- Jinja, HTML, CSS e JavaScript;
- Flask-Login, Flask-Limiter e Flask-Talisman;
- OpenCV para o recurso de reconhecimento facial;
- Waitress como servidor HTTP no container;
- Docker e Docker Compose;
- Pytest e GitHub Actions.

## Arquitetura

`app.py` cria a aplicação, configura extensões e registra os blueprints. `backend/` agrupa rotas e regras por domínio. `core/` concentra autenticação, banco, rate limiting e armazenamento. A interface usa templates Jinja em `templates/` e ativos em `static/`.

O projeto mantém SQL direto por refletir sua arquitetura atual. `schema_patagonia.sql` é a única fonte versionada da estrutura do banco e não possui dados reais.

## Estrutura do projeto

```text
backend/                rotas e regras dos módulos
core/                   serviços compartilhados
docs/images/            screenshots sem dados reais
static/                 imagens e ativos públicos
templates/              telas Jinja
tests/                  testes automatizados
.github/workflows/      integração contínua
app.py                  configuração da aplicação
run_dev.py              inicialização local
schema_patagonia.sql    schema oficial do PostgreSQL
```

## Segurança

- senhas armazenadas com hash PBKDF2;
- cookies `HttpOnly` e `SameSite=Lax`, com `Secure` em produção;
- `SECRET_KEY` obrigatória em produção;
- consultas SQL parametrizadas nos fluxos principais;
- rate limiting na autenticação;
- autorização administrativa centralizada no backend;
- bloqueio de escrita com origem externa;
- limites de requisição e proteção contra traversal em arquivos;
- uploads, fotos, `.env`, logs e dumps locais ignorados pelo Git.

Nunca utilize dados, imagens ou credenciais reais para demonstrar este projeto.

## Instalação local

Requisitos: Python 3.11 e PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run_dev.py
```

Antes de iniciar, ajuste o `.env` e aplique `schema_patagonia.sql` em um banco vazio. Em Linux ou macOS, utilize o comando de ativação correspondente ao seu shell.

## Docker

1. Copie `.env.example` para `.env`.
2. Substitua `SECRET_KEY` e `DB_PASS` por valores locais seguros.
3. Execute:

```powershell
docker compose up --build
```

A aplicação ficará disponível em `http://localhost:8080`. Na primeira criação do volume, o PostgreSQL aplica automaticamente o schema oficial. O projeto não cria conta administrativa com senha padrão.

## Configuração

As variáveis documentadas estão em `.env.example`. As principais são `ENV`, `SECRET_KEY`, `DATABASE_URL` ou `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASS`. O armazenamento local usa `LOCAL_STORAGE_PATH`; GCS continua disponível opcionalmente por `STORAGE_DRIVER=gcs` e `GCS_BUCKET`.

`TRUST_PROXY` deve permanecer desligada, exceto quando a aplicação estiver atrás de um proxy reverso confiável. As rotas diagnósticas permanecem desabilitadas por padrão.

## Testes

```powershell
python -m pytest -q
```

O workflow em `.github/workflows/tests.yml` executa a suíte em pushes para `main` e pull requests.

## Roadmap

- introduzir migrations incrementais para futuras alterações do banco;
- ampliar testes de integração com PostgreSQL;
- adicionar screenshots anonimizados das telas principais;
- evoluir gradualmente a validação de uploads por conteúdo.

## Licença

Distribuído sob a Licença MIT. Consulte [LICENSE](LICENSE).

## Autor

**Emanuel Sousa Vasconcellos Lima**

Desenvolvedor com foco em aplicações web, análise de dados, automação e sistemas de gestão.
