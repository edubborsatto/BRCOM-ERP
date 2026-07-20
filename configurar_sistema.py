import os

# Certifica-se de que as pastas existem de forma modular
os.makedirs("app", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# 1. ATUALIZANDO APP/DATABASE.PY
database_content = """from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida no arquivo .env")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

# 2. ATUALIZANDO APP/MODELS.PY
models_content = """from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    usuario_login = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    pode_gerenciar_usuarios = Column(Boolean, default=False)
    pode_alterar_custos = Column(Boolean, default=False)
    pode_movimentar_estoque = Column(Boolean, default=False)
    pode_gerenciar_clientes = Column(Boolean, default=False)

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    unidade_medida = Column(String, nullable=False)
    quantidade_atual = Column(Float, default=0.0)
    estoque_minimo = Column(Float, default=0.0)
    preco_custo = Column(Float, nullable=False)
    preco_venda = Column(Float, nullable=False)

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    documento = Column(String, unique=True, index=True, nullable=True)
    telefone = Column(String, nullable=True)
    email = Column(String, nullable=True)

class HistoricoEstoque(Base):
    __tablename__ = "historico_estoque"

    id = Column(Integer, primary_key=True, index=True)
    produto_nome = Column(String, nullable=False)
    tipo_movimentacao = Column(String, nullable=False)
    quantidade = Column(Float, nullable=False)
    saldo_apos = Column(Float, nullable=False)
    usuario_responsavel = Column(String, nullable=False)
    data_hora = Column(DateTime, default=datetime.now)

class Compromisso(Base):
    __tablename__ = "agenda"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    data_hora = Column(DateTime, nullable=False)
    local = Column(String, nullable=True)

class PedidoFuturo(Base):
    __tablename__ = "pedidos_futuros"

    id = Column(Integer, primary_key=True, index=True)
    cliente_nome = Column(String, nullable=False)
    produto_nome = Column(String, nullable=False)
    quantidade = Column(Float, nullable=False)
    data_entrega = Column(DateTime, nullable=False)
    status = Column(String, default="Pendente")
"""

# 3. ATUALIZANDO APP/SCHEMAS.PY
schemas_content = """from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UsuarioBase(BaseModel):
    nome: str
    usuario_login: str
    pode_gerenciar_usuarios: bool = False
    pode_alterar_custos: bool = False
    pode_movimentar_estoque: bool = False
    pode_gerenciar_clientes: bool = False

class UsuarioCreate(UsuarioBase):
    senha: str

class UsuarioResponse(UsuarioBase):
    id: int
    class Config:
        from_attributes = True

class ProdutoBase(BaseModel):
    nome: str
    unidade_medida: str
    quantidade_atual: float
    estoque_minimo: float
    preco_custo: float
    preco_venda: float

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoResponse(ProdutoBase):
    id: int
    class Config:
        from_attributes = True

class ClienteBase(BaseModel):
    nome: str
    documento: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteResponse(ClienteBase):
    id: int
    class Config:
        from_attributes = True

class HistoricoResponse(BaseModel):
    id: int
    produto_nome: str
    tipo_movimentacao: str
    quantidade: float
    saldo_apos: float
    usuario_responsavel: str
    data_hora: datetime
    class Config:
        from_attributes = True

class CompromissoBase(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data_hora: datetime
    local: Optional[str] = None

class CompromissoCreate(CompromissoBase):
    pass

class CompromissoResponse(CompromissoBase):
    id: int
    class Config:
        from_attributes = True

class PedidoFuturoBase(BaseModel):
    cliente_nome: str
    produto_nome: str
    quantidade: float
    data_entrega: datetime
    status: str = "Pendente"

class PedidoFuturoCreate(PedidoFuturoBase):
    pass

class PedidoFuturoResponse(PedidoFuturoBase):
    id: int
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    usuario_login: str
    senha: str
"""

# 4. ATUALIZANDO APP/MAIN.PY
main_content = """from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
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

app = FastAPI(title="BRCom ERP", version="4.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(os.path.dirname(BASE_DIR), "templates")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
def ler_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/login")
def login(dados: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.usuario_login == dados.usuario_login).first()
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
            "pode_gerenciar_clientes": usuario.pode_gerenciar_clientes
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

# HISTÓRICO (SPRINT 4: REMOÇÃO INDIVIDUAL ADICIONADA)
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
        pode_movimentar_estoque=usuario.pode_movimentar_estoque, pode_gerenciar_clientes=usuario.pode_gerenciar_clientes
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario

@app.get("/usuarios/", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    if not usuarios:
        admin_padrao = models.Usuario(
            nome="Administrador", usuario_login="admin", senha_hash="admin123",
            pode_gerenciar_usuarios=True, pode_alterar_custos=True, pode_movimentar_estoque=True, pode_gerenciar_clientes=True
        )
        db.add(admin_padrao)
        db.commit()
        db.refresh(admin_padrao)
        return [admin_padrao]
    return usuarios

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
    novo_comp = models.Compromisso(**comp.dict())
    db.add(novo_comp)
    db.commit()
    db.refresh(novo_comp)
    return novo_comp

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
"""

# 5. ATUALIZANDO TEMPLATES/INDEX.HTML (INTERFACE INTEGRAL COM IFRAME DOCS E CRUDS COMPLETOS)
index_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BRCom ERP - Gestão e Performance</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
        .calendar-day-cell { min-height: 85px; }
    </style>
</head>
<body class="bg-gray-100 font-sans min-h-screen">

    <!-- LOGIN -->
    <div id="loginScreen" class="flex items-center justify-center min-h-screen px-4">
        <div class="bg-white p-8 rounded-lg shadow-xl border w-full max-w-md">
            <div class="text-center mb-6">
                <i class="fa-solid fa-boxes-stacked text-5xl text-emerald-500 mb-2"></i>
                <h1 class="text-2xl font-bold text-gray-800">BRCom ERP</h1>
                <p class="text-sm text-gray-500">Gestão corporativa integrada</p>
            </div>
            <form id="loginForm" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Usuário</label>
                    <input type="text" id="login_user" required class="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-emerald-500 outline-none">
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Senha</label>
                    <input type="password" id="login_pass" required class="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-emerald-500 outline-none">
                </div>
                <button type="submit" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md shadow transition">Entrar</button>
            </form>
        </div>
    </div>

    <!-- DASHBOARD -->
    <div id="mainDashboard" class="hidden min-h-screen flex">
        
        <!-- SIDEBAR ESQUERDO -->
        <aside class="w-64 bg-slate-800 text-slate-100 flex flex-col justify-between shadow-lg shrink-0">
            <div>
                <div class="p-6 border-b border-slate-700 flex items-center space-x-3">
                    <i class="fa-solid fa-boxes-stacked text-3xl text-emerald-400"></i>
                    <span class="text-lg font-bold tracking-wider text-emerald-400">BRCom <span class="text-white font-light">ERP</span></span>
                </div>
                <nav class="mt-6 px-4 space-y-2">
                    <button onclick="switchTab('dashboardTab')" id="btn-dashboardTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg bg-emerald-600 text-white font-bold transition">
                        <i class="fa-solid fa-chart-line text-lg"></i><span>Painel Geral</span>
                    </button>
                    <button onclick="switchTab('produtosTab')" id="btn-produtosTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-box text-lg"></i><span>Estoque de Produtos</span>
                    </button>
                    <button onclick="switchTab('historicoTab')" id="btn-historicoTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-clock-rotate-left text-lg"></i><span>Registro de Estoque</span>
                    </button>
                    <button onclick="switchTab('pedidosTab')" id="btn-pedidosTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-calendar-check text-lg"></i><span>Pedidos Futuros</span>
                    </button>
                    <button onclick="switchTab('agendaTab')" id="btn-agendaTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-calendar-days text-lg"></i><span>Agenda</span>
                    </button>
                    <button onclick="switchTab('clientesTab')" id="btn-clientesTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-user-group text-lg"></i><span>Clientes</span>
                    </button>
                    <button onclick="switchTab('usuariosTab')" id="btn-usuariosTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition hidden">
                        <i class="fa-solid fa-users-gear text-lg"></i><span>Controle de Usuários</span>
                    </button>
                    <!-- SPRINT 4: ABA DE INTEGRAÇÃO DA API SWAGGER -->
                    <button onclick="switchTab('docsTab')" id="btn-docsTab" class="w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 transition">
                        <i class="fa-solid fa-code text-lg"></i><span>Documentação API</span>
                    </button>
                </nav>
            </div>
            <div class="p-4 border-t border-slate-700 bg-slate-900 flex flex-col space-y-2">
                <span id="userNameDisplay" class="text-xs font-semibold text-emerald-400"></span>
                <button onclick="logout()" class="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-bold transition">Sair</button>
            </div>
        </aside>

        <!-- AREA DE CONTEÚDO -->
        <main class="flex-grow p-8 overflow-y-auto" style="max-height: 100vh;">
            
            <!-- PAINEL GERAL -->
            <div id="dashboardTab" class="tab-content space-y-8">
                <div class="bg-slate-800 p-6 rounded-lg text-white shadow-md">
                    <h1 class="text-2xl font-bold">Painel de Monitoramento Geral</h1>
                </div>
                <div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
                    <div class="bg-white p-6 rounded-lg shadow border xl:col-span-1">
                        <h2 class="text-lg font-bold text-red-600 mb-4"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Estoque Crítico</h2>
                        <table class="w-full text-left border-collapse">
                            <thead><tr class="bg-gray-50 border-b text-xs uppercase text-gray-500"><th class="p-2">Item</th><th class="p-2 text-center">Atual</th></tr></thead>
                            <tbody id="criticalStockTableBody" class="text-sm"></tbody>
                        </table>
                    </div>
                    <div class="bg-white p-6 rounded-lg shadow border xl:col-span-2">
                        <div class="flex justify-between items-center mb-4"><h2 class="text-lg font-bold text-gray-800">Calendário Mensal</h2><span id="calendarMonthLabel" class="font-bold text-emerald-600 uppercase"></span></div>
                        <div class="grid grid-cols-7 gap-1 text-center font-bold text-xs text-gray-500 border-b py-1"><div>Dom</div><div>Seg</div><div>Ter</div><div>Qua</div><div>Qui</div><div>Sex</div><div>Sáb</div></div>
                        <div id="calendarGrid" class="calendar-grid mt-2 bg-gray-200"></div>
                    </div>
                </div>
            </div>

            <!-- PRODUTOS -->
            <div id="produtosTab" class="tab-content hidden grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white p-6 rounded-lg shadow border h-fit">
                    <h2 id="productFormTitle" class="text-lg font-bold text-gray-800 mb-4">Cadastrar Produto</h2>
                    <form id="productForm" class="space-y-4">
                        <input type="hidden" id="edit_product_id">
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">NOME</label><input type="text" id="prod_nome" required class="w-full px-3 py-2 border rounded"></div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">UNID</label><select id="prod_unidade" class="w-full px-3 py-2 border rounded"><option value="unidade">Unidade</option><option value="metro">Metro</option></select></div>
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">MÍNIMO</label><input type="number" id="prod_minimo" required class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">QTD ATUAL</label><input type="number" id="prod_atual" required class="w-full px-3 py-2 border rounded"></div>
                            <div class="cost-field"><label class="block text-xs font-bold text-gray-500 mb-1">CUSTO (R$)</label><input type="number" step="0.01" id="prod_custo" required class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">VENDA (R$)</label><input type="number" step="0.01" id="prod_venda" required class="w-full px-3 py-2 border rounded"></div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded">Salvar Produto</button>
                    </form>
                </div>
                <div class="bg-white p-6 rounded-lg shadow border lg:col-span-2"><h2 class="text-lg font-bold text-gray-800 mb-4">Estoque de Produtos</h2><table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">ID</th><th class="p-3">Nome</th><th class="p-3">Qtd</th><th class="p-3 cost-field">Custo</th><th class="p-3">Venda</th><th class="p-3 text-right">Ações</th></tr></thead><tbody id="productTableBody" class="text-sm"></tbody></table></div>
            </div>

            <!-- REGISTRO DE ESTOQUE (HISTÓRICO) -->
            <div id="historicoTab" class="tab-content hidden">
                <div class="bg-white p-6 rounded-lg shadow border">
                    <div class="flex justify-between items-center mb-4"><h2 class="text-lg font-bold text-gray-800">Histórico de Movimentações</h2><button onclick="clearAllHistory()" class="bg-red-600 text-white text-xs px-3 py-1.5 rounded font-bold">Limpar Tudo</button></div>
                    <table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">Horário</th><th class="p-3">Produto</th><th class="p-3">Operação</th><th class="p-3">Qtd</th><th class="p-3">Saldo</th><th class="p-3">Responsável</th><th class="p-3 text-right">Excluir</th></tr></thead><tbody id="historyTableBody" class="text-sm"></tbody></table>
                </div>
            </div>

            <!-- PEDIDOS FUTUROS -->
            <div id="pedidosTab" class="tab-content hidden grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white p-6 rounded-lg shadow border h-fit">
                    <h2 id="orderFormTitle" class="text-lg font-bold text-gray-800 mb-4">Lançar Pedido Futuro</h2>
                    <form id="orderForm" class="space-y-4">
                        <input type="hidden" id="edit_order_id">
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">CLIENTE</label><input type="text" id="ord_cliente" required class="w-full px-3 py-2 border rounded"></div>
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">PRODUTO</label><input type="text" id="ord_produto" required class="w-full px-3 py-2 border rounded"></div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">QTD</label><input type="number" id="ord_qtd" required class="w-full px-3 py-2 border rounded"></div>
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">ENTREGA</label><input type="datetime-local" id="ord_data" required class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded">Salvar Pedido</button>
                    </form>
                </div>
                <div class="bg-white p-6 rounded-lg shadow border lg:col-span-2"><h2 class="text-lg font-bold text-gray-800 mb-4">Pedidos Agendados</h2><table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">Entrega</th><th class="p-3">Cliente</th><th class="p-3">Produto</th><th class="p-3">Qtd</th><th class="p-3">Status</th><th class="p-3 text-right">Ações</th></tr></thead><tbody id="orderTableBody" class="text-sm"></tbody></table></div>
            </div>

            <!-- AGENDA -->
            <div id="agendaTab" class="tab-content hidden grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white p-6 rounded-lg shadow border h-fit">
                    <h2 id="agendaFormTitle" class="text-lg font-bold text-gray-800 mb-4">Novo Compromisso</h2>
                    <form id="agendaForm" class="space-y-4">
                        <input type="hidden" id="edit_agenda_id">
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">COMPROMISSO</label><input type="text" id="ag_titulo" required class="w-full px-3 py-2 border rounded"></div>
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">DESCRIÇÃO</label><textarea id="ag_desc" class="w-full px-3 py-2 border rounded" rows="2"></textarea></div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">DATA/HORA</label><input type="datetime-local" id="ag_data" required class="w-full px-3 py-2 border rounded"></div>
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">LOCAL</label><input type="text" id="ag_local" class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded">Salvar na Agenda</button>
                    </form>
                </div>
                <div class="bg-white p-6 rounded-lg shadow border lg:col-span-2"><h2 class="text-lg font-bold text-gray-800 mb-4">Compromissos Cadastrados</h2><table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">Horário</th><th class="p-3">Compromisso</th><th class="p-3">Local</th><th class="p-3 text-right">Ações</th></tr></thead><tbody id="agendaTableBody" class="text-sm"></tbody></table></div>
            </div>

            <!-- CLIENTES -->
            <div id="clientesTab" class="tab-content hidden grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white p-6 rounded-lg shadow border h-fit">
                    <h2 id="clientFormTitle" class="text-lg font-bold text-gray-800 mb-4">Cadastrar Cliente</h2>
                    <form id="clientForm" class="space-y-4">
                        <input type="hidden" id="edit_client_id">
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">NOME DO CLIENTE</label><input type="text" id="cli_nome" required class="w-full px-3 py-2 border rounded"></div>
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">DOCUMENTO</label><input type="text" id="cli_doc" class="w-full px-3 py-2 border rounded"></div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">TELEFONE</label><input type="text" id="cli_tel" class="w-full px-3 py-2 border rounded"></div>
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">EMAIL</label><input type="email" id="cli_email" class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded">Salvar Cliente</button>
                    </form>
                </div>
                <div class="bg-white p-6 rounded-lg shadow border lg:col-span-2"><h2 class="text-lg font-bold text-gray-800 mb-4">Carteira de Clientes</h2><table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">Nome</th><th class="p-3">Documento</th><th class="p-3">Telefone</th><th class="p-3">Email</th><th class="p-3 text-right">Ações</th></tr></thead><tbody id="clientTableBody" class="text-sm"></tbody></table></div>
            </div>

            <!-- CONTROLE DE USUÁRIOS -->
            <div id="usuariosTab" class="tab-content hidden grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="bg-white p-6 rounded-lg shadow border h-fit">
                    <h2 id="userFormTitle" class="text-lg font-bold text-gray-800 mb-4">Adicionar Usuário</h2>
                    <form id="userForm" class="space-y-4">
                        <input type="hidden" id="edit_user_id">
                        <div><label class="block text-xs font-bold text-gray-500 mb-1">NOME</label><input type="text" id="u_nome" required class="w-full px-3 py-2 border rounded"></div>
                        <div class="grid grid-cols-2 gap-4">
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">LOGIN</label><input type="text" id="u_login" required class="w-full px-3 py-2 border rounded"></div>
                            <div><label class="block text-xs font-bold text-gray-500 mb-1">SENHA</label><input type="text" id="u_senha" required class="w-full px-3 py-2 border rounded"></div>
                        </div>
                        <div class="bg-gray-50 p-3 rounded border text-xs space-y-1">
                            <label class="flex items-center space-x-2"><input type="checkbox" id="perm_usuarios"><span>Admin</span></label>
                            <label class="flex items-center space-x-2"><input type="checkbox" id="perm_custos"><span>Ver Custos</span></label>
                            <label class="flex items-center space-x-2"><input type="checkbox" id="perm_estoque"><span>Mover Estoque</span></label>
                            <label class="flex items-center space-x-2"><input type="checkbox" id="perm_clientes"><span>Clientes</span></label>
                        </div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded">Salvar Usuário</button>
                    </form>
                </div>
                <div class="bg-white p-6 rounded-lg shadow border lg:col-span-2"><h2 class="text-lg font-bold text-gray-800 mb-4">Usuários do Sistema</h2><table class="w-full text-left border-collapse"><thead class="bg-gray-50 border-b text-xs uppercase"><tr><th class="p-3">Nome</th><th class="p-3">Login</th><th class="p-3">Senha</th><th class="p-3">Ações</th></tr></thead><tbody id="userTableBody" class="text-sm"></tbody></table></div>
            </div>

            <!-- SPRINT 4: TELA DA DOCUMENTAÇÃO API SWAGGER EM iframe INTEGRADO -->
            <div id="docsTab" class="tab-content hidden w-full h-full">
                <div class="bg-white rounded-lg shadow border w-full h-[82vh] overflow-hidden">
                    <iframe src="/docs" class="w-full h-full border-none"></iframe>
                </div>
            </div>

        </main>
    </div>

    <script>
        let USUARIO_LOGADO = null;
        let LISTA_COMPROMISSOS = [];

        document.getElementById("loginForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                usuario_login: document.getElementById("login_user").value,
                senha: document.getElementById("login_pass").value
            };
            const response = await fetch("/api/login", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
            });
            if (response.ok) {
                const data = await response.json();
                USUARIO_LOGADO = data.usuario;
                entrarNoPainel();
            } else { alert("Login inválido."); }
        });

        function entrarNoPainel() {
            document.getElementById("loginScreen").classList.add("hidden");
            document.getElementById("mainDashboard").classList.remove("hidden");
            document.getElementById("userNameDisplay").innerHTML = `<i class="fa-solid fa-circle-user mr-1 text-emerald-400"></i> ${USUARIO_LOGADO.nome}`;
            applyPermissions();
            loadAllData();
        }

        function logout() {
            USUARIO_LOGADO = null;
            document.getElementById("loginScreen").classList.remove("hidden");
            document.getElementById("mainDashboard").classList.add("hidden");
            document.getElementById("loginForm").reset();
        }

        function applyPermissions() {
            if (USUARIO_LOGADO.pode_gerenciar_usuarios) document.getElementById("btn-usuariosTab").classList.remove("hidden");
            else document.getElementById("btn-usuariosTab").classList.add("hidden");

            document.querySelectorAll(".cost-field").forEach(el => {
                if (USUARIO_LOGADO.pode_alterar_custos) el.classList.remove("hidden");
                else el.classList.add("hidden");
            });
        }

        function loadAllData() { loadProducts(); loadHistory(); loadOrders(); loadClients(); loadAgenda(); }

        function switchTab(tabId) {
            document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
            document.getElementById(tabId).classList.remove("hidden");
            document.querySelectorAll("[id^='btn-']").forEach(btn => {
                btn.className = "w-full flex items-center space-x-3 py-3 px-4 rounded-lg hover:bg-slate-700 hover:text-white transition";
            });
            document.getElementById("btn-" + tabId).className = "w-full flex items-center space-x-3 py-3 px-4 rounded-lg bg-emerald-600 text-white font-bold transition";
        }

        function formatDate(iso) { return iso ? new Date(iso).toLocaleString('pt-BR') : "-"; }

        // PRODUTOS
        async function loadProducts() {
            const res = await fetch("/produtos/");
            const products = await res.json();
            const tbody = document.getElementById("productTableBody");
            tbody.innerHTML = "";
            const critBody = document.getElementById("criticalStockTableBody");
            critBody.innerHTML = "";
            
            products.forEach(p => {
                tbody.innerHTML += `
                    <tr class="border-b hover:bg-gray-50 text-slate-700">
                        <td class="p-3 font-semibold text-gray-400">#${p.id}</td>
                        <td class="p-3 font-bold">${p.nome}</td>
                        <td class="p-3"><span class="px-2 py-0.5 rounded text-xs ${p.quantidade_atual <= p.estoque_minimo ? 'bg-red-100 text-red-700 font-bold' : 'bg-emerald-100 text-emerald-800'}">${p.quantidade_atual} ${p.unidade_medida}</span></td>
                        <td class="p-3 cost-field ${!USUARIO_LOGADO.pode_alterar_custos?'hidden':''}">R$ ${p.preco_custo.toFixed(2)}</td>
                        <td class="p-3 font-semibold text-emerald-600">R$ ${p.preco_venda.toFixed(2)}</td>
                        <td class="p-3 text-right space-x-2">
                            <button onclick="editProduct(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="text-blue-500"><i class="fa-solid fa-pen-to-square"></i></button>
                            <button onclick="deleteProduct(${p.id})" class="text-red-500"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    </tr>
                `;
                if(p.quantidade_atual <= p.estoque_minimo) {
                    critBody.innerHTML += `<tr class="border-b"><td class="p-2.5 font-bold">${p.nome}</td><td class="p-2.5 text-center text-red-600 font-bold">${p.quantidade_atual}</td></tr>`;
                }
            });
        }

        document.getElementById("productForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit_product_id").value;
            const payload = {
                nome: document.getElementById("prod_nome").value, unidade_medida: document.getElementById("prod_unidade").value,
                quantidade_atual: parseFloat(document.getElementById("prod_atual").value), estoque_minimo: parseFloat(document.getElementById("prod_minimo").value),
                preco_custo: parseFloat(document.getElementById("prod_custo").value || 0), preco_venda: parseFloat(document.getElementById("prod_venda").value)
            };
            const url = id ? `/produtos/${id}?usuario_resp=${USUARIO_LOGADO.nome}` : `/produtos/?usuario_resp=${USUARIO_LOGADO.nome}`;
            const res = await fetch(url, { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            if (res.ok) { resetProductForm(); loadProducts(); loadHistory(); }
        });

        function editProduct(p) {
            document.getElementById("edit_product_id").value = p.id;
            document.getElementById("prod_nome").value = p.nome;
            document.getElementById("prod_unidade").value = p.unidade_medida;
            document.getElementById("prod_minimo").value = p.estoque_minimo;
            document.getElementById("prod_atual").value = p.quantidade_atual;
            document.getElementById("prod_custo").value = p.preco_custo;
            document.getElementById("prod_venda").value = p.preco_venda;
            document.getElementById("productFormTitle").innerText = "Editar Produto";
        }
        
        function resetProductForm() { document.getElementById("productForm").reset(); document.getElementById("edit_product_id").value = ""; document.getElementById("productFormTitle").innerText = "Cadastrar Produto"; }
        async function deleteProduct(id) { if(confirm("Excluir item?")) { await fetch(`/produtos/${id}?usuario_resp=${USUARIO_LOGADO.nome}`, { method: "DELETE" }); loadProducts(); loadHistory(); } }

        // HISTÓRICO (SPRINT 4: REMOÇÃO INDIVIDUAL IMPLEMENTADA)
        async function loadHistory() {
            const res = await fetch("/historico/");
            const history = await res.json();
            const tbody = document.getElementById("historyTableBody");
            tbody.innerHTML = "";
            history.forEach(h => {
                tbody.innerHTML += `
                    <tr class="border-b text-slate-700 hover:bg-gray-50 transition">
                        <td class="p-3 text-gray-400">${formatDate(h.data_hora)}</td>
                        <td class="p-3 font-bold">${h.produto_nome}</td>
                        <td class="p-3"><span class="px-2 py-0.5 rounded text-xs bg-slate-100">${h.tipo_movimentacao}</span></td>
                        <td class="p-3 font-semibold">${h.quantidade}</td>
                        <td class="p-3 text-gray-400">${h.saldo_apos}</td>
                        <td class="p-3 text-slate-600">${h.usuario_responsavel}</td>
                        <td class="p-3 text-right"><button onclick="deleteHistoryRow(${h.id})" class="text-red-500"><i class="fa-solid fa-trash-can text-xs"></i></button></td>
                    </tr>
                `;
            });
        }
        async function deleteHistoryRow(id) { if(confirm("Excluir este registro da auditoria?")) { await fetch(`/historico/${id}`, { method: "DELETE" }); loadHistory(); } }
        async function clearAllHistory() { if(confirm("Limpar todo o histórico?")) { await fetch("/historico/", { method: "DELETE" }); loadHistory(); } }

        # CLIENTES (SPRINT 4: ATUALIZADO COM EDICÃO COMPLETA)
        async function loadClients() {
            const res = await fetch("/clientes/");
            const clients = await res.json();
            const tbody = document.getElementById("clientTableBody");
            tbody.innerHTML = "";
            clients.forEach(c => {
                tbody.innerHTML += `
                    <tr class="border-b text-slate-700 hover:bg-gray-50">
                        <td class="p-3 font-bold">${c.nome}</td>
                        <td class="p-3">${c.documento || '-'}</td>
                        <td class="p-3">${c.telefone || '-'}</td>
                        <td class="p-3">${c.email || '-'}</td>
                        <td class="p-3 text-right space-x-2">
                            <button onclick="editClient(${JSON.stringify(c).replace(/"/g, '&quot;')})" class="text-blue-500"><i class="fa-solid fa-pen-to-square"></i></button>
                            <button onclick="deleteClient(${c.id})" class="text-red-500"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    </tr>
                `;
            });
        }

        document.getElementById("clientForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit_client_id").value;
            const payload = { nome: document.getElementById("cli_nome").value, documento: document.getElementById("cli_doc").value || null, telefone: document.getElementById("cli_tel").value || null, email: document.getElementById("cli_email").value || null };
            const url = id ? `/clientes/${id}` : "/clientes/";
            const res = await fetch(url, { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            if (res.ok) { resetClientForm(); loadClients(); }
        });

        function editClient(c) {
            document.getElementById("edit_client_id").value = c.id;
            document.getElementById("cli_nome").value = c.nome;
            document.getElementById("cli_doc").value = c.documento || "";
            document.getElementById("cli_tel").value = c.telefone || "";
            document.getElementById("cli_email").value = c.email || "";
            document.getElementById("clientFormTitle").innerText = "Editar Cliente";
        }
        function resetClientForm() { document.getElementById("clientForm").reset(); document.getElementById("edit_client_id").value = ""; document.getElementById("clientFormTitle").innerText = "Cadastrar Cliente"; }
        async function deleteClient(id) { if(confirm("Excluir cliente?")) { await fetch(`/clientes/${id}`, { method: "DELETE" }); loadClients(); } }

        # PEDIDOS (SPRINT 4: ATUALIZADO COM EDICÃO COMPLETA)
        async function loadOrders() {
            const res = await fetch("/pedidos/");
            const orders = await res.json();
            const tbody = document.getElementById("orderTableBody");
            tbody.innerHTML = "";
            orders.forEach(o => {
                tbody.innerHTML += `
                    <tr class="border-b text-slate-700 hover:bg-gray-50">
                        <td class="p-3">${formatDate(o.data_entrega)}</td>
                        <td class="p-3 font-bold">${o.cliente_nome}</td>
                        <td class="p-3">${o.produto_nome}</td>
                        <td class="p-3 font-semibold">${o.quantidade}</td>
                        <td class="p-3"><span class="px-2 py-0.5 rounded text-xs bg-amber-100">${o.status}</span></td>
                        <td class="p-3 text-right space-x-1">
                            <button onclick="changeOrderStatus(${o.id}, 'Entregue')" class="text-xs bg-emerald-500 text-white px-1.5 py-0.5 rounded">OK</button>
                            <button onclick="editOrder(${JSON.stringify(o).replace(/"/g, '&quot;')})" class="text-blue-500 ml-2"><i class="fa-solid fa-pen-to-square"></i></button>
                            <button onclick="deleteOrder(${o.id})" class="text-red-500"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    </tr>
                `;
            });
        }

        document.getElementById("orderForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit_order_id").value;
            const payload = { cliente_nome: document.getElementById("ord_cliente").value, produto_nome: document.getElementById("ord_produto").value, quantidade: parseFloat(document.getElementById("ord_qtd").value), data_entrega: new Date(document.getElementById("ord_data").value).toISOString() };
            const url = id ? `/pedidos/${id}` : "/pedidos/";
            const res = await fetch(url, { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            if(res.ok) { resetOrderForm(); loadOrders(); }
        });

        function editOrder(o) {
            document.getElementById("edit_order_id").value = o.id;
            document.getElementById("ord_cliente").value = o.cliente_nome;
            document.getElementById("ord_produto").value = o.produto_nome;
            document.getElementById("ord_qtd").value = o.quantidade;
            document.getElementById("ord_data").value = new Date(o.data_entrega).toISOString().slice(0, 16);
            document.getElementById("orderFormTitle").innerText = "Editar Pedido";
        }
        function resetOrderForm() { document.getElementById("orderForm").reset(); document.getElementById("edit_order_id").value = ""; document.getElementById("orderFormTitle").innerText = "Lançar Pedido Futuro"; }
        async function changeOrderStatus(id, st) { await fetch(`/pedidos/${id}/status?status_novo=${st}`, { method: "PUT" }); loadOrders(); }
        async function deleteOrder(id) { if(confirm("Excluir pedido?")) { await fetch(`/pedidos/${id}`, { method: "DELETE" }); loadOrders(); } }

        # AGENDA
        async function loadAgenda() {
            const res = await fetch("/agenda/");
            LISTA_COMPROMISSOS = await res.json();
            const tbody = document.getElementById("agendaTableBody");
            tbody.innerHTML = "";
            LISTA_COMPROMISSOS.forEach(a => {
                tbody.innerHTML += `
                    <tr class="border-b text-slate-700">
                        <td class="p-3">${formatDate(a.data_hora)}</td>
                        <td class="p-3"><strong>${a.titulo}</strong><br><small class="text-gray-400">${a.descricao||""}</small></td>
                        <td class="p-3 text-gray-500">${a.local||"-"}</td>
                        <td class="p-3 text-right space-x-2">
                            <button onclick="editAgenda(${JSON.stringify(a).replace(/"/g, '&quot;')})" class="text-blue-500"><i class="fa-solid fa-pen-to-square"></i></button>
                            <button onclick="deleteAgenda(${a.id})" class="text-red-500"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    </tr>
                `;
            });
            renderCalendar();
        }

        document.getElementById("agendaForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit_agenda_id").value;
            const payload = { titulo: document.getElementById("ag_titulo").value, descricao: document.getElementById("ag_desc").value||null, data_hora: new Date(document.getElementById("ag_data").value).toISOString(), local: document.getElementById("ag_local").value||null };
            const res = await fetch(id ? `/agenda/${id}` : "/agenda/", { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            if(res.ok) { resetAgendaForm(); loadAgenda(); }
        });

        function editAgenda(a) {
            document.getElementById("edit_agenda_id").value = a.id;
            document.getElementById("ag_titulo").value = a.titulo;
            document.getElementById("ag_desc").value = a.descricao||"";
            document.getElementById("ag_local").value = a.local||"";
            document.getElementById("ag_data").value = new Date(a.data_hora).toISOString().slice(0, 16);
            document.getElementById("agendaFormTitle").innerText = "Editar Compromisso";
        }
        function resetAgendaForm() { document.getElementById("agendaForm").reset(); document.getElementById("edit_agenda_id").value = ""; document.getElementById("agendaFormTitle").innerText = "Novo Compromisso"; }
        async function deleteAgenda(id) { if(confirm("Excluir compromisso?")) { await fetch(`/agenda/${id}`, { method: "DELETE" }); loadAgenda(); } }

        function renderCalendar() {
            const grid = document.getElementById("calendarGrid");
            grid.innerHTML = "";
            const today = new Date();
            document.getElementById("calendarMonthLabel").innerText = today.toLocaleString('pt-BR', { month: 'long', year: 'numeric' });
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).getDay();
            const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();

            for (let i = 0; i < firstDay; i++) grid.innerHTML += `<div class="bg-gray-50/50 calendar-day-cell"></div>`;
            for (let d = 1; d <= daysInMonth; d++) {
                const dayComps = LISTA_COMPROMISSOS.filter(c => new Date(c.data_hora).getDate() === d && new Date(c.data_hora).getMonth() === today.getMonth());
                let txt = ""; dayComps.forEach(c => txt += `<div class="text-[9px] bg-emerald-100 text-emerald-800 p-0.5 rounded truncate mt-1">${c.titulo}</div>`);
                grid.innerHTML += `<div class="bg-white p-1 border flex flex-col justify-between calendar-day-cell"><span class="text-xs text-gray-400 font-bold">${d}</span><div class="overflow-y-auto">${txt}</div></div>`;
            }
        }

        # USUÁRIOS
        async function loadUsers() {
            const res = await fetch("/usuarios/");
            const users = await res.json();
            const tbody = document.getElementById("userTableBody");
            tbody.innerHTML = "";
            users.forEach(u => {
                tbody.innerHTML += `
                    <tr class="border-b text-slate-700">
                        <td class="p-3 font-bold">${u.nome}</td>
                        <td class="p-3 text-gray-500">${u.usuario_login}</td>
                        <td class="p-3 font-mono text-xs text-gray-400">${u.senha_hash}</td>
                        <td class="p-3 text-right space-x-2">
                            <button onclick="editUser(${JSON.stringify(u).replace(/"/g, '&quot;')})" class="text-blue-500"><i class="fa-solid fa-pen-to-square"></i></button>
                            <button onclick="deleteUser(${u.id})" class="text-red-500 ${u.usuario_login==='admin'?'hidden':''}"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    </tr>
                `;
            });
        }

        document.getElementById("userForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit_user_id").value;
            const payload = { nome: document.getElementById("u_nome").value, usuario_login: document.getElementById("u_login").value, senha: document.getElementById("u_senha").value, pode_gerenciar_usuarios: document.getElementById("perm_usuarios").checked, pode_alterar_custos: document.getElementById("perm_custos").checked, pode_movimentar_estoque: document.getElementById("perm_estoque").checked, pode_gerenciar_clientes: document.getElementById("perm_clientes").checked };
            const url = id ? `/usuarios/${id}` : "/usuarios/";
            const res = await fetch(url, { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            if(res.ok) { resetUserForm(); loadUsers(); }
        });

        function editUser(u) {
            document.getElementById("edit_user_id").value = u.id;
            document.getElementById("u_nome").value = u.nome;
            document.getElementById("u_login").value = u.usuario_login;
            document.getElementById("u_senha").value = u.senha_hash;
            document.getElementById("perm_usuarios").checked = u.pode_gerenciar_usuarios;
            document.getElementById("perm_custos").checked = u.pode_alterar_custos;
            document.getElementById("perm_estoque").checked = u.pode_movimentar_estoque;
            document.getElementById("perm_clientes").checked = u.pode_gerenciar_clientes;
            document.getElementById("userFormTitle").innerText = "Editar Usuário";
        }
        function resetUserForm() { document.getElementById("userForm").reset(); document.getElementById("edit_user_id").value = ""; document.getElementById("userFormTitle").innerText = "Adicionar Usuário"; }
        async function deleteUser(id) { if(confirm("Excluir usuário?")) { await fetch(`/usuarios/${id}`, { method: "DELETE" }); loadUsers(); } }
    </script>
</body>
</html>
"""

# Escrita dos arquivos modularizados no ambiente
with open("app/database.py", "w", encoding="utf-8") as f:
    f.write(database_content)
print("[✔] app/database.py reconfigurado!")

with open("app/models.py", "w", encoding="utf-8") as f:
    f.write(models_content)
print("[✔] app/models.py reconfigurado!")

with open("app/schemas.py", "w", encoding="utf-8") as f:
    f.write(schemas_content)
print("[✔] app/schemas.py reconfigurado!")

with open("app/main.py", "w", encoding="utf-8") as f:
    f.write(main_content)
print("[✔] app/main.py reconfigurado!")

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(index_content)
print("[✔] templates/index.html reconfigurado!")

print("\n🚀 SUCESSO DA SPRINT 4! Arquivos modulares criados, organizados e prontos para teste local e envio para nuvem!")