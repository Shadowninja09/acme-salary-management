from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate

EMPLOYEE_CODE_UNIQUE_CONSTRAINT = "uq_employees_employee_code"


class DuplicateEmployeeCodeError(Exception):
    pass


def _is_employee_code_unique_violation(exc: IntegrityError) -> bool:
    orig = exc.orig
    if orig is None:
        return False
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None) if diag is not None else None
    return constraint_name == EMPLOYEE_CODE_UNIQUE_CONSTRAINT


def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    employee = Employee(
        employee_code=data.employee_code,
        full_name=data.full_name,
        country=data.country,
        department=data.department,
        job_title=data.job_title,
        employment_status=data.employment_status.value,
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        if _is_employee_code_unique_violation(exc):
            raise DuplicateEmployeeCodeError from exc
        raise
    db.refresh(employee)
    return employee


def get_employee_by_id(db: Session, employee_id: int) -> Employee | None:
    return db.get(Employee, employee_id)


def _ilike_contains(query: str) -> str:
    escaped = (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _employee_text_match(query: str) -> ColumnElement[bool]:
    pattern = _ilike_contains(query)
    return or_(
        Employee.employee_code.ilike(pattern, escape="\\"),
        Employee.full_name.ilike(pattern, escape="\\"),
        Employee.country.ilike(pattern, escape="\\"),
        Employee.department.ilike(pattern, escape="\\"),
        Employee.job_title.ilike(pattern, escape="\\"),
    )


def list_employees(
    db: Session,
    *,
    limit: int,
    offset: int,
    q: str | None = None,
    employment_status: str | None = None,
) -> tuple[list[Employee], int]:
    search = (q or "").strip()
    count_stmt = select(func.count()).select_from(Employee)
    list_stmt = select(Employee)
    if search:
        match = _employee_text_match(search)
        count_stmt = count_stmt.where(match)
        list_stmt = list_stmt.where(match)
    if employment_status:
        status_match = Employee.employment_status == employment_status
        count_stmt = count_stmt.where(status_match)
        list_stmt = list_stmt.where(status_match)
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            list_stmt.order_by(Employee.employee_code.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total
