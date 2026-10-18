from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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


def list_employees(
    db: Session, *, limit: int, offset: int
) -> tuple[list[Employee], int]:
    total = db.scalar(select(func.count()).select_from(Employee)) or 0
    items = list(
        db.scalars(
            select(Employee)
            .order_by(Employee.employee_code.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total
