import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app import models
from app.database import Base, SessionLocal, engine
from app.dependencies import require_permission
from app.routers import agenda, auth, clients, history, orders, products, users
from app.security import validate_security_config
from app.services import bootstrap_security


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_config()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_security(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="BRCom ERP",
    version="4.2.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(BASE_DIR), "templates"))

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(history.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(agenda.router)
app.include_router(orders.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ler_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/docs", include_in_schema=False)
def docs_protegida(_: models.Usuario = Depends(require_permission("pode_acessar_docs"))):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="BRCom ERP - API")


@app.get("/openapi.json", include_in_schema=False)
def openapi_protegido(_: models.Usuario = Depends(require_permission("pode_acessar_docs"))):
    return JSONResponse(app.openapi())


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
