from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os

from app.database import engine, get_db, Base
import app.models as models
import app.schemas as schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="BRCom ERP", version="4.1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(os.path.dirname(BASE_DIR), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Inicializa os 4 usuários com a matriz de permissões exata
def inicializar_usuarios_padrao():
    db = next(get_db())
    try:
        usuarios_para_criar = [
            {
                "nome": "Eduardo", "usuario_login": "eduardo", "senha_hash": "Eduardo12345",
                "pode_gerenciar_usuarios": True, "pode_alterar_custos": True,
                "pode_movimentar_estoque": True, "pode_gerenciar_clientes": True,
                "pode_acessar_agenda": True, "pode_acessar_docs": True, "pode_gerenciar_historico": True
            },
            {
                "nome": "Rogerio", "usuario_login": "rogerio", "senha_hash": "Rogerio12345",
                "pode_gerenciar_usuarios": False, "pode_alterar_custos": True,
                "pode_movimentar_estoque": True, "pode_gerenciar_clientes": True,
                "pode_acessar_agenda": True, "pode_acessar_docs": False, "pode_gerenciar_historico": True
            },
            {
                "nome": "Joao", "usuario_login": "joao", "senha_hash": "Joao12345",
                "pode_gerenciar_usuarios": False, "pode_alterar_custos": True,
                "pode_movimentar_estoque": True, "pode_gerenciar_clientes": True,
                "pode_acessar_agenda": True, "pode_acessar_docs": False, "pode_gerenciar_historico": True
            },
            {
                "nome": "Iara", "usuario_login": "iara", "senha_hash": "Iara12345",
                "pode_gerenciar_usuarios": False, "pode_alterar_custos": False,
                "pode_movimentar_estoque": True, "pode_gerenciar_clientes": False,
                "pode_acessar_agenda": False, "pode_acessar_docs": False, "pode_gerenciar_historico": False
            }
        ]

        for u_data in usuarios_para_criar:
            existe = db.query(models.Usuario).filter(models.Usuario.usuario_login == u_data["usuario_login"]).first()
            if not existe:
                novo_u = models.Usuario(**u_data)
                db.add(novo_u)
        db.commit()
    finally:
        db.close()

inicializar_usuarios_padrao()

@app.get("/", response_class=HTMLResponse)
def ler_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/login")
def login(dados: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.usuario_login == dados.usuario_login.lower()).first()
    if not usuario or usuario.senha_hash != dados.senha:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    return {
        "status": "success",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "usuario_login": usuario.usuario_login,
            "pode_gerenciar_usuarios": usuario.pode_gerenciar_usuarios,
            "pode_alterar_custos": usuario.pode_alterar_custos,
            "pode_movimentar_estoque": usuario.pode_movimentar_estoque,
            "pode_gerenciar_clientes": usuario.pode_gerenciar_clientes,
            "pode_acessar_agenda": usuario.pode_acessar_agenda,
            "pode_acessar_docs": usuario.pode_acessar_docs,
            "pode_gerenciar_historico": usuario.pode_gerenciar_historico
        }
    }

# PRODUTOS
@app.post("/produtos/", response_model=schemas.ProdutoResponse, status_code=201)
def criar_produto(produto: schemas.ProdutoCreate, usuario_resp: str = "Sistema", db: Session = Depends(get_db)):
    db_produto = db.query(models.Produto).filter(models.Produto.nome == produto.nome).first()
    if db_produto:
        raise HTTPException(status_code=400, detail="Este produto já está cadastrado")
    novo_produto = models.Produto(**produto.dict())
    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)
    hist = models.HistoricoEstoque(
        produto_nome=novo_produto.nome, tipo_movimentacao="CADASTRO",
        quantidade=novo_produto.quantidade_atual, saldo_apos=novo_produto.quantidade_atual,
        usuario_responsavel=usuario_resp
    )
    db.add(hist)
    db.commit()
    return novo_produto

@app.get("/produtos/", response_model=List[schemas.ProdutoResponse])
def listar_produtos(db: Session = Depends(get_db)):
    return db.query(models.Produto).all()

@app.put("/produtos/{produto_id}", response_model=schemas.ProdutoResponse)
def atualizar_produto(produto_id: int, dados: schemas.ProdutoCreate, usuario_resp: str = "Sistema", db: Session = Depends(get_db)):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    qtd_anterior = produto.quantidade_atual
    for key, val in dados.dict().items():
        setattr(produto, key, val)
    db.commit()
    db.refresh(produto)
    if qtd_anterior != produto.quantidade_atual:
        dif = produto.quantidade_atual - qtd_anterior
        tipo = "ENTRADA" if dif > 0 else "SAÍDA"
        hist = models.HistoricoEstoque(
            produto_nome=produto.nome, tipo_movimentacao=tipo,
            quantidade=abs(dif), saldo_apos=produto.quantidade_atual,
            usuario_responsavel=usuario_resp
        )
        db.add(hist)
        db.commit()
    return produto

@app.delete("/produtos/{produto_id}")
def excluir_produto(produto_id: int, usuario_resp: str = "Sistema", db: Session = Depends(get_db)):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    hist = models.HistoricoEstoque(
        produto_nome=produto.nome, tipo_movimentacao="EXCLUSÃO",
        quantidade=produto.quantidade_atual, saldo_apos=0.0,
        usuario_responsavel=usuario_resp
    )
    db.add(hist)
    db.delete(produto)
    db.commit()
    return {"status": "success"}

# HISTÓRICO
@app.get("/historico/", response_model=List[schemas.HistoricoResponse])
def listar_historico(db: Session = Depends(get_db)):
    return db.query(models.HistoricoEstoque).order_by(models.HistoricoEstoque.data_hora.desc()).all()

@app.delete("/historico/{hist_id}")
def excluir_registro_historico(hist_id: int, db: Session = Depends(get_db)):
    registro = db.query(models.HistoricoEstoque).filter(models.HistoricoEstoque.id == hist_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    db.delete(registro)
    db.commit()
    return {"status": "success"}

@app.delete("/historico/")
def limpar_historico_completo(db: Session = Depends(get_db)):
    db.query(models.HistoricoEstoque).delete()
    db.commit()
    return {"status": "success"}

# USUÁRIOS
@app.post("/usuarios/", response_model=schemas.UsuarioResponse, status_code=201)
def criar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    db_usuario = db.query(models.Usuario).filter(models.Usuario.usuario_login == usuario.usuario_login).first()
    if db_usuario:
        raise HTTPException(status_code=400, detail="Este login já existe")
    novo_usuario = models.Usuario(
        nome=usuario.nome, usuario_login=usuario.usuario_login, senha_hash=usuario.senha,
        pode_gerenciar_usuarios=usuario.pode_gerenciar_usuarios, pode_alterar_custos=usuario.pode_alterar_custos,
        pode_movimentar_estoque=usuario.pode_movimentar_estoque, pode_gerenciar_clientes=usuario.pode_gerenciar_clientes,
        pode_acessar_agenda=usuario.pode_acessar_agenda, pode_acessar_docs=usuario.pode_acessar_docs,
        pode_gerenciar_historico=usuario.pode_gerenciar_historico
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario

@app.get("/usuarios/", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

@app.put("/usuarios/{usuario_id}", response_model=schemas.UsuarioResponse)
def atualizar_usuario(usuario_id: int, dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    usr = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usr:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    usr.nome = dados.nome
    usr.usuario_login = dados.usuario_login
    usr.senha_hash = dados.senha
    usr.pode_gerenciar_usuarios = dados.pode_gerenciar_usuarios
    usr.pode_alterar_custos = dados.pode_alterar_custos
    usr.pode_movimentar_estoque = dados.pode_movimentar_estoque
    usr.pode_gerenciar_clientes = dados.pode_gerenciar_clientes
    usr.pode_acessar_agenda = dados.pode_acessar_agenda
    usr.pode_acessar_docs = dados.pode_acessar_docs
    usr.pode_gerenciar_historico = dados.pode_gerenciar_historico
    db.commit()
    db.refresh(usr)
    return usr

@app.delete("/usuarios/{usuario_id}")
def excluir_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.delete(usuario)
    db.commit()
    return {"status": "success"}

# CLIENTES
@app.post("/clientes/", response_model=schemas.ClienteResponse, status_code=201)
def criar_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    db_cli = db.query(models.Cliente).filter(models.Cliente.documento == cliente.documento).first() if cliente.documento else None
    if db_cli:
        raise HTTPException(status_code=400, detail="Documento já cadastrado")
    novo_cli = models.Cliente(**cliente.dict())
    db.add(novo_cli)
    db.commit()
    db.refresh(novo_cli)
    return novo_cli

@app.get("/clientes/", response_model=List[schemas.ClienteResponse])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).all()

@app.put("/clientes/{cliente_id}", response_model=schemas.ClienteResponse)
def atualizar_cliente(cliente_id: int, dados: schemas.ClienteCreate, db: Session = Depends(get_db)):
    cli = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for key, val in dados.dict().items():
        setattr(cli, key, val)
    db.commit()
    db.refresh(cli)
    return cli

@app.delete("/clientes/{cliente_id}")
def excluir_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cli = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    db.delete(cli)
    db.commit()
    return {"status": "success"}

# AGENDA
@app.post("/agenda/", response_model=schemas.CompromissoResponse, status_code=201)
def criar_compromisso(comp: schemas.CompromissoCreate, db: Session = Depends(get_db)):
    novo_compromisso = models.Compromisso(**comp.dict())
    db.add(novo_compromisso)
    db.commit()
    db.refresh(novo_compromisso)
    return novo_compromisso

@app.get("/agenda/", response_model=List[schemas.CompromissoResponse])
def listar_compromissos(db: Session = Depends(get_db)):
    return db.query(models.Compromisso).order_by(models.Compromisso.data_hora.asc()).all()

@app.put("/agenda/{comp_id}", response_model=schemas.CompromissoResponse)
def atualizar_compromisso(comp_id: int, dados: schemas.CompromissoCreate, db: Session = Depends(get_db)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    for key, val in dados.dict().items():
        setattr(comp, key, val)
    db.commit()
    db.refresh(comp)
    return comp

@app.delete("/agenda/{comp_id}")
def excluir_compromisso(comp_id: int, db: Session = Depends(get_db)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    db.delete(comp)
    db.commit()
    return {"status": "success"}

# PEDIDOS FUTUROS
@app.post("/pedidos/", response_model=schemas.PedidoFuturoResponse, status_code=201)
def criar_pedido(pedido: schemas.PedidoFuturoCreate, db: Session = Depends(get_db)):
    novo_pedido = models.PedidoFuturo(**pedido.dict())
    db.add(novo_pedido)
    db.commit()
    db.refresh(novo_pedido)
    return novo_pedido

@app.get("/pedidos/", response_model=List[schemas.PedidoFuturoResponse])
def listar_pedidos(db: Session = Depends(get_db)):
    return db.query(models.PedidoFuturo).order_by(models.PedidoFuturo.data_entrega.asc()).all()

@app.put("/pedidos/{pedido_id}", response_model=schemas.PedidoFuturoResponse)
def atualizar_pedido(pedido_id: int, dados: schemas.PedidoFuturoCreate, db: Session = Depends(get_db)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    for key, val in dados.dict().items():
        setattr(pedido, key, val)
    db.commit()
    db.refresh(pedido)
    return pedido

@app.put("/pedidos/{pedido_id}/status")
def atualizar_status_pedido(pedido_id: int, status_novo: str, db: Session = Depends(get_db)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pedido.status = status_novo
    db.commit()
    return {"status": "success"}

@app.delete("/pedidos/{pedido_id}")
def excluir_pedido(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    db.delete(pedido)
    db.commit()
    return {"status": "success"}