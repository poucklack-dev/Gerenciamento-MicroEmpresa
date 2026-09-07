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
backend/                aplicação Flask, módulos e serviços compartilhados
frontend/templates/     páginas Jinja
frontend/static/        CSS, JavaScript, imagens e design system
database/               schema e migrations incrementais
tests/                  testes automatizados
```

`backend/app.py` configura a aplicação e registra os blueprints. O projeto mantém SQL parametrizado e tipos `NUMERIC` para valores monetários. As migrations são incrementais: `001_empresa.sql` introduz a configuração central da empresa e `002_banco_horas.sql` adiciona setor, chefe direto e a consolidação mensal do banco de horas sem apagar registros existentes.

O Banco de Horas trabalha internamente em minutos, aceita carga mensal calculada ou direta, separa lançamentos detalhados de totais manuais, permite ajustes individuais, anulação auditável por período e exporta um `.xlsx` com resumo, detalhamento e configuração.

## Executar com Docker

1. Copie `.env.example` para `.env`.
2. Defina valores locais para `SECRET_KEY` e `DB_PASS`.
3. Inicie:

```powershell
docker compose up --build
```

Acesse `http://localhost:8080`.

Em banco já existente, aplique as migrations em ordem:

```powershell
Get-Content -Raw database/migrations/001_empresa.sql | docker compose exec -T db psql -U patagonia -d patagonia
Get-Content -Raw database/migrations/002_banco_horas.sql | docker compose exec -T db psql -U patagonia -d patagonia
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

## Licença

Distribuído sob a [Licença MIT](LICENSE).

## Desenvolvedor

**Emanuel Sousa Vasconcellos Lima**

Desenvolvedor com foco em aplicações web, análise de dados, automação e sistemas de gestão.
