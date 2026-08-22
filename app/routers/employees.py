from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import confirm_critical_action, require_permission
from app.services import audit


router = APIRouter(prefix="/funcionarios", tags=["Funcionários"])
employee_access = require_permission("pode_gerenciar_funcionarios")


def _mask_cpf(value: str) -> str:
    return f"***.***.***-{value[-2:]}"


def _mask_email(value: str | None) -> str | None:
    if not value:
        return None
    local, domain = value.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _mask_phone(value: str | None) -> str | None:
    return f"*******{value[-4:]}" if value else None


def _audit_snapshot(employee: models.Funcionario) -> dict:
    return {
        "matricula": employee.matricula,
        "nome_completo": employee.nome_completo,
        "cpf": _mask_cpf(employee.cpf),
        "rg_final": f"***{employee.rg[-4:]}",
        "email_pessoal": _mask_email(employee.email_pessoal),
        "celular": _mask_phone(employee.celular),
        "departamento": employee.departamento,
        "cargo": employee.cargo,
        "tipo_contrato": employee.tipo_contrato,
        "data_admissao": employee.data_admissao,
        "status": employee.status,
        "data_desligamento": employee.data_desligamento,
        "usuario_id": employee.usuario_id,
    }


def _summary(employee: models.Funcionario) -> dict:
    user = employee.usuario
    return {
        "id": employee.id,
        "matricula": employee.matricula,
        "nome_completo": employee.nome_completo,
        "nome_social": employee.nome_social,
        "cpf_mascarado": _mask_cpf(employee.cpf),
        "celular": employee.celular,
        "email_corporativo": employee.email_corporativo,
        "departamento": employee.departamento,
        "cargo": employee.cargo,
        "tipo_contrato": employee.tipo_contrato,
        "status": employee.status,
        "data_admissao": employee.data_admissao,
        "data_desligamento": employee.data_desligamento,
        "usuario_id": employee.usuario_id,
        "usuario_login": user.usuario_login if user else None,
        "usuario_ativo": user.ativo if user else None,
        "atualizado_em": employee.atualizado_em,
    }


def _detail(employee: models.Funcionario) -> dict:
    data = {
        field: getattr(employee, field)
        for field in schemas.FuncionarioBase.model_fields
    }
    user = employee.usuario
    return {
        **data,
        "id": employee.id,
        "matricula": employee.matricula,
        "usuario_nome": user.nome if user else None,
        "usuario_login": user.usuario_login if user else None,
        "usuario_ativo": user.ativo if user else None,
        "criado_em": employee.criado_em,
        "atualizado_em": employee.atualizado_em,
        "criado_por_nome": employee.criado_por_nome,
        "atualizado_por_nome": employee.atualizado_por_nome,
    }


def _employee_or_404(db: Session, employee_id: int) -> models.Funcionario:
    employee = db.get(models.Funcionario, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")
    return employee


def _validate_link(
    db: Session,
    user_id: int | None,
    employee_id: int | None = None,
) -> models.Usuario | None:
    if not user_id:
        return None
    user = db.get(models.Usuario, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Conta de acesso não encontrada")
    linked = db.query(models.Funcionario).filter(
        models.Funcionario.usuario_id == user_id,
        models.Funcionario.id != employee_id if employee_id else True,
    ).first()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"Esta conta já está vinculada ao funcionário {linked.nome_completo}",
        )
    return user


def _validate_uniques(
    db: Session,
    data: dict,
    employee_id: int | None = None,
) -> None:
    checks = (
        ("cpf", data.get("cpf"), "CPF"),
        ("matricula", data.get("matricula"), "matrícula"),
        ("pis_pasep", data.get("pis_pasep"), "PIS/PASEP"),
    )
    for field, value, label in checks:
        if not value:
            continue
        query = db.query(models.Funcionario).filter(getattr(models.Funcionario, field) == value)
        if employee_id:
            query = query.filter(models.Funcionario.id != employee_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"Já existe um funcionário com este {label}")


def _sync_access(employee: models.Funcionario, user: models.Usuario | None) -> None:
    if not user:
        return
    user.nome = employee.nome_completo
    user.email = employee.email_corporativo or employee.email_pessoal
    user.telefone = employee.celular
    if employee.status == "DESLIGADO":
        user.ativo = False
        user.tentativas_login = 0
        user.bloqueado_ate = None


def _require_permanent_delete(
    user: models.Usuario = Depends(employee_access),
) -> models.Usuario:
    if user.tipo_usuario not in {"DONO", "DESENVOLVEDOR"}:
        raise HTTPException(
            status_code=403,
            detail="Exclusão definitiva permitida somente para Dono ou Desenvolvedor",
        )
    return user


@router.get("/resumo")
def employee_overview(
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(employee_access),
):
    active = db.query(models.Funcionario).filter(models.Funcionario.status == "ATIVO").count()
    terminated = db.query(models.Funcionario).filter(models.Funcionario.status == "DESLIGADO").count()
    departments = [
        item[0]
        for item in db.query(models.Funcionario.departamento)
        .distinct()
        .order_by(models.Funcionario.departamento)
        .all()
    ]
    return {
        "total": active + terminated,
        "ativos": active,
        "desligados": terminated,
        "departamentos": departments,
    }


@router.get("/usuarios-disponiveis", response_model=List[schemas.UsuarioVinculavelResponse])
def linkable_users(
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(employee_access),
):
    linked = {
        item.usuario_id: item.id
        for item in db.query(models.Funcionario).filter(models.Funcionario.usuario_id.is_not(None)).all()
    }
    return [
        {
            "id": user.id,
            "nome": user.nome,
            "usuario_login": user.usuario_login,
            "ativo": user.ativo,
            "funcionario_id": linked.get(user.id),
        }
        for user in db.query(models.Usuario).order_by(models.Usuario.nome).all()
    ]


@router.get("/", response_model=List[schemas.FuncionarioResumo])
def list_employees(
    busca: str | None = Query(default=None, max_length=160),
    status: str | None = Query(default=None, pattern="^(ATIVO|DESLIGADO)$"),
    departamento: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(employee_access),
):
    query = db.query(models.Funcionario)
    if busca and busca.strip():
        term = busca.strip()
        like = f"%{term}%"
        digits = "".join(character for character in term if character.isdigit())
        conditions = [
            models.Funcionario.nome_completo.ilike(like),
            models.Funcionario.nome_social.ilike(like),
            models.Funcionario.matricula.ilike(like),
            models.Funcionario.email_pessoal.ilike(like),
            models.Funcionario.email_corporativo.ilike(like),
            models.Funcionario.cargo.ilike(like),
            models.Funcionario.departamento.ilike(like),
        ]
        if digits:
            conditions.append(models.Funcionario.cpf.ilike(f"%{digits}%"))
        query = query.filter(or_(*conditions))
    if status:
        query = query.filter(models.Funcionario.status == status)
    if departamento:
        query = query.filter(models.Funcionario.departamento == departamento.strip())
    employees = query.order_by(models.Funcionario.nome_completo).limit(1000).all()
    return [_summary(employee) for employee in employees]


@router.get("/{employee_id}", response_model=schemas.FuncionarioResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(employee_access),
):
    return _detail(_employee_or_404(db, employee_id))


@router.post("/", response_model=schemas.FuncionarioResponse, status_code=201)
def create_employee(
    data: schemas.FuncionarioCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(employee_access),
):
    values = data.model_dump()
    _validate_uniques(db, values)
    linked_user = _validate_link(db, values.get("usuario_id"))
    if data.status == "DESLIGADO" and data.usuario_id == actor.id:
        raise HTTPException(status_code=400, detail="Você não pode desligar o próprio acesso")
    employee = models.Funcionario(
        **values,
        criado_por_id=actor.id,
        criado_por_nome=actor.nome,
        atualizado_por_id=actor.id,
        atualizado_por_nome=actor.nome,
    )
    db.add(employee)
    try:
        db.flush()
        if not employee.matricula:
            employee.matricula = f"FUNC-{employee.id:05d}"
        _sync_access(employee, linked_user)
        audit(
            db, actor, "FUNCIONARIOS", "CRIADO", "funcionarios", employee.id,
            after=_audit_snapshot(employee),
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="CPF, matrícula, PIS/PASEP ou conta já cadastrados") from error
    db.refresh(employee)
    return _detail(employee)


@router.put("/{employee_id}", response_model=schemas.FuncionarioResponse)
def update_employee(
    employee_id: int,
    data: schemas.FuncionarioUpdate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(employee_access),
):
    employee = _employee_or_404(db, employee_id)
    values = data.model_dump()
    _validate_uniques(db, values, employee_id)
    linked_user = _validate_link(db, values.get("usuario_id"), employee_id)
    if data.status == "DESLIGADO" and data.usuario_id == actor.id:
        raise HTTPException(status_code=400, detail="Você não pode desligar o próprio acesso")
    before = _audit_snapshot(employee)
    previous_status = employee.status
    for field, value in values.items():
        setattr(employee, field, value)
    employee.atualizado_em = datetime.now()
    employee.atualizado_por_id = actor.id
    employee.atualizado_por_nome = actor.nome
    _sync_access(employee, linked_user)
    action = "ATUALIZADO"
    if previous_status != employee.status:
        action = "DESLIGADO" if employee.status == "DESLIGADO" else "REATIVADO"
    audit(
        db, actor, "FUNCIONARIOS", action, "funcionarios", employee.id,
        before=before, after=_audit_snapshot(employee),
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="CPF, matrícula, PIS/PASEP ou conta já cadastrados") from error
    db.refresh(employee)
    return _detail(employee)


@router.post("/{employee_id}/status", response_model=schemas.FuncionarioResponse)
def change_employee_status(
    employee_id: int,
    data: schemas.FuncionarioStatusUpdate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(employee_access),
):
    employee = _employee_or_404(db, employee_id)
    if data.status == "DESLIGADO" and employee.usuario_id == actor.id:
        raise HTTPException(status_code=400, detail="Você não pode desligar o próprio acesso")
    before = _audit_snapshot(employee)
    if data.status == "DESLIGADO":
        termination_date = data.data_desligamento or date.today()
        if termination_date < employee.data_admissao:
            raise HTTPException(status_code=400, detail="Desligamento não pode ser anterior à admissão")
        if termination_date > date.today():
            raise HTTPException(status_code=400, detail="Desligamento não pode ter data futura")
        employee.status = "DESLIGADO"
        employee.data_desligamento = termination_date
        employee.motivo_desligamento = data.motivo.strip()
        action = "DESLIGADO"
    else:
        employee.status = "ATIVO"
        employee.data_desligamento = None
        employee.motivo_desligamento = None
        action = "REATIVADO"
    employee.atualizado_em = datetime.now()
    employee.atualizado_por_id = actor.id
    employee.atualizado_por_nome = actor.nome
    _sync_access(employee, employee.usuario)
    audit(
        db, actor, "FUNCIONARIOS", action, "funcionarios", employee.id,
        before=before, after=_audit_snapshot(employee),
    )
    db.commit()
    db.refresh(employee)
    return _detail(employee)


@router.post("/{employee_id}/excluir-definitivamente")
def permanently_delete_employee(
    employee_id: int,
    data: schemas.ConfirmacaoCritica,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(_require_permanent_delete),
):
    confirm_critical_action(actor, data.senha)
    employee = _employee_or_404(db, employee_id)
    if employee.status != "DESLIGADO":
        raise HTTPException(
            status_code=409,
            detail="Desligue o funcionário antes da exclusão definitiva",
        )
    before = _audit_snapshot(employee)
    audit(
        db, actor, "FUNCIONARIOS", "EXCLUIDO_DEFINITIVAMENTE", "funcionarios",
        employee.id, before=before, after={"motivo": data.motivo.strip()},
    )
    db.delete(employee)
    db.commit()
    return {"status": "success"}
