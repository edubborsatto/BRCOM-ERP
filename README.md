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

## Importação mensal de notas fiscais e recibos

A área **Importar planilhas** recebe arquivos `.xlsx` de até 15 MB e trabalha em duas etapas: prévia e confirmação. Nenhuma linha entra nos relatórios antes da confirmação.

- Notas fiscais: o sistema lê exclusivamente a aba `GERAL`.
- Recibos: o sistema lê exclusivamente a aba `PRINCIPAL`.
- Ao reenviar um arquivo atualizado — inclusive o mesmo arquivo — todas as possíveis cópias aparecem na prévia para decisão.
- Registros novos são aceitos automaticamente e não exigem revisão.
- Somente possíveis cópias exigem decisão: `IGNORAR` ou `IMPORTAR`.
- Possíveis cópias ainda não revisadas ficam automaticamente no topo da prévia.
- A prévia pode ser filtrada entre cópias não revisadas, cópias revisadas,
  todas as cópias, registros novos ou todos.
- A prévia pode ser ordenada por data, valor, cliente, produto, linha ou
  situação, sem retirar as cópias pendentes do topo.
- A base consolidada mostra apenas registros já aceitos e não cria tarefas de revisão para produtos corretos.
- A base consolidada pode ser ordenada por data, valor, cliente, produto,
  origem ou situação e filtrada entre registros novos e cópias importadas.
- O botão **Ignorar todas as cópias** permite concluir rapidamente uma atualização mensal.
- Descrições semelhantes a produtos cadastrados são sugeridas automaticamente.
- Padronizações corrigidas pelo gestor são reaproveitadas nas próximas importações da mesma descrição.
- A base consolidada pode ser pesquisada e filtrada por notas, recibos, ano e mês.
- O painel mostra faturamento mensal e anual, separando notas, recibos e o total consolidado.
- O CSV exportado respeita os filtros de origem, ano e mês.
- Os dados financeiros, clientes e documentos não são enviados para serviços de IA; a leitura e a padronização ocorrem dentro do ERP.

Cabeçalhos equivalentes são reconhecidos, incluindo os formatos históricos `CLIENTE / NUM. N.F. / DATA / QTD. / PRODUTO / VALOR IND. / VALOR TOTAL` e `data / recibo / cliente / responsável da compra / quantidade / produto / valor / $ prod. c/ desc. / valor und. c/ desc.`.

## Planilhas de Vendas

A versão 4.4.2 inclui uma planilha editável dentro do ERP, separada entre
**Notas fiscais** e **Recibos**. Ela usa a cópia interna das linhas já
confirmadas na importação; o arquivo Excel original nunca é alterado.

Na importação, a coluna **Documento** recebe sempre o número presente na
coluna B: **NOTA** nos arquivos de notas e **RECIBO** nos arquivos de recibos.

- Edição direta das células, com salvamento automático ao sair da célula.
- Inclusão de novas linhas pelo site.
- Pesquisa e filtros por ano e mês.
- Ordenação por data, última alteração, valor, cliente, produto ou documento.
- Histórico de todas as alterações com usuário, data e hora.
- Restauração de versões anteriores.
- Exclusão recuperável por meio da lixeira.
- Exportação de um novo `.xlsx`, com aba `GERAL` para notas e `PRINCIPAL`
  para recibos.
- O Excel exportado contém fórmulas automáticas para valor unitário bruto,
  percentual de desconto, valor total bruto e valor unitário líquido. Ao
  alterar quantidade, valor total ou desconto, o Excel recalcula essas colunas.
- As células calculadas aparecem em azul-claro e as linhas são exportadas como
  tabela, facilitando filtros e a continuidade das fórmulas em novas linhas.
- Alterações nos valores, quantidades, clientes e produtos atualizam
  imediatamente os relatórios do ERP.

## Perfis oficiais e compatibilidade da versão 4.5.0

O acesso é organizado em três perfis visíveis: **Desenvolvedor**, **Dono** e
**Funcionário**. O perfil oferece um conjunto simples de permissões padrão e a
área de permissões avançadas permite os ajustes autorizados pelo gestor.

- Desenvolvedor: acesso técnico e empresarial completo.
- Dono: gestão empresarial completa, sem configurações técnicas da API.
- Funcionário: clientes, produtos, estoque, produção, orçamentos em rascunho,
  vendas operacionais e agenda; sem custos, margens, faturamento ou aprovação.
- Desenvolvedor e Dono podem criar, editar e desativar usuários.
- A criação de Desenvolvedor por um Dono exige confirmação especial.
- Ninguém pode aumentar o próprio perfil ou as próprias permissões.
- Desativar preserva o usuário e todo o histórico; não há exclusão física.
- Criações, alterações e desativações de usuários ficam em auditoria própria.

A migração `20260804_05` é aditiva. Ela não apaga nem recria dados empresariais,
mantém as colunas antigas de permissão e converte usuários legados de modo
conservador: administradores que já acessavam a documentação técnica tornam-se
Desenvolvedores, os demais administradores tornam-se Donos e os demais usuários
tornam-se Funcionários. O usuário definido pelas variáveis
`BOOTSTRAP_ADMIN_*` também se torna Desenvolvedor, garantindo continuidade do
acesso técnico.

## Operação simplificada da versão 4.6.1

A versão 4.6.1 mantém a arquitetura e os dados das versões anteriores, mas
reduz as telas para o fluxo utilizado pela Brasil Comercial.

- Produto: código, nome, categoria, tipo, família, custo, venda, unidade,
  quantidade inicial, estoque mínimo, localização e especificações.
- Localização é um campo de texto livre e pode receber qualquer descrição.
- A lista de produtos não exibe custo nem preço de venda; esses campos aparecem
  na edição somente para Desenvolvedor e Dono.
- A API também oculta custo e venda de Funcionários.
- Movimentação de estoque permite digitar código, nome ou localização e filtrar
  por família e tipo.
- Pedidos futuros substituem Orçamentos no menu. Nota fiscal ou recibo e o
  respectivo número são obrigatórios somente na confirmação da venda.
- Fórmulas e custos e Orçamentos deixam de aparecer no menu; suas tabelas e
  rotas são mantidas por compatibilidade.
- A auditoria permite pesquisa e filtros por período, produto, operação e
  responsável. Seus registros são permanentes e não podem ser apagados.
- Cadastro, edição e exclusão de produtos também entram na auditoria.
- A tabela separa corretamente Localização e Quantidade atual.
- Quantidades abaixo do estoque mínimo aparecem em vermelho na própria tabela.
- A edição abre o formulário preenchido e leva a tela até ele.
- Os arquivos visuais usam identificação de versão para evitar JavaScript antigo
  armazenado no cache do navegador.

A migração `20260811_06` adiciona apenas os novos campos de produto e de
confirmação dos pedidos. Ela foi validada em banco vazio e sobre a revisão
`20260804_05`, preservando os registros existentes.

## Fila e reservas de pedidos da versão 4.7.0

A versão 4.7.0 amplia Pedidos Futuros sem reativar as telas antigas de
Orçamentos e Fórmulas.

- Um pedido pode conter vários produtos prontos.
- Cada item separa quantidade total, quantidade retirada do estoque pronto e
  quantidade que precisa ser fabricada.
- Quando houver fabricação, o usuário informa as matérias-primas e o consumo
  total de cada uma.
- Produtos prontos e matérias-primas são reservados ao salvar, evitando que o
  mesmo saldo seja prometido para pedidos diferentes.
- Ao editar, as reservas anteriores são devolvidas dentro da mesma transação e
  os novos valores são aplicados somente se todos os saldos forem suficientes.
- Ao cancelar, todas as reservas são devolvidas e o pedido permanece no
  histórico como Cancelado.
- A fila é compartilhada e pode ser reorganizada por arrastar, por setas ou por
  marcação visual de prioridade.
- Toda reserva e devolução aparece na auditoria com a referência do pedido e o
  usuário responsável.
- Nota fiscal ou recibo continuam obrigatórios somente na confirmação da venda.

A migração `20260811_07` adiciona campos de fila e cancelamento, além das tabelas
de itens e matérias-primas reservadas. Ela foi validada em banco novo e em uma
base criada pelo pacote original da v4.6.1, preservando os registros existentes.
