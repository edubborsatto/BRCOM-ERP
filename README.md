# BRCom ERP

ERP interno da Brasil Comercial, desenvolvido com FastAPI, SQLAlchemy, PostgreSQL/Neon e HTML/Tailwind/JavaScript.

## Segurança antes do primeiro deploy desta versão

Esta versão invalida senhas antigas que estavam salvas em texto puro. Antes de mesclar o Pull Request no GitHub, cadastre no Render as variáveis abaixo. Caso contrário, ninguém conseguirá entrar no sistema.

1. Entre no serviço `brcom-erp` no Render.
2. Abra **Environment**.
3. Clique em **Add Environment Variable**.
4. Adicione `SESSION_SECRET` e informe uma sequência aleatória com pelo menos 32 caracteres.
5. Adicione `BOOTSTRAP_ADMIN_LOGIN` com o login do administrador, por exemplo `eduardo`.
6. Adicione `BOOTSTRAP_ADMIN_NAME` com o nome do administrador.
7. Adicione `BOOTSTRAP_ADMIN_PASSWORD` com uma senha nova, forte e com pelo menos 12 caracteres.
8. Confirme que `DATABASE_URL` continua com a conexão do Neon.
9. Salve. Não publique os valores dessas variáveis no GitHub.

No Render, mantenha também:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Executar no computador

No PowerShell, dentro da pasta do projeto:

```powershell
py -m venv venv
venv\Scripts\activate
py -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Abra o arquivo `.env`, substitua os exemplos pelos seus valores e execute:

```powershell
py -m uvicorn app.main:app --reload
```

Depois acesse `http://127.0.0.1:8000`. Para uso local, defina `COOKIE_SECURE=false` no `.env`; no Render, mantenha `COOKIE_SECURE=true`.

## Verificações de qualidade

```powershell
py -m flake8 app tests
py -m pytest -q
py -m compileall -q app
```

Os mesmos comandos são executados automaticamente no GitHub para cada Pull Request.
