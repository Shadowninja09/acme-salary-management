from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_session, require_csrf_token
from app.db.session import get_db
from app.schemas.employee import EmployeeCreate, EmployeeList, EmployeeRead
from app.services.employee import (
    DuplicateEmployeeCodeError,
    create_employee,
    get_employee_by_id,
    list_employees,
)

router = APIRouter(
    prefix="/api/v1/employees",
    tags=["employees"],
    dependencies=[Depends(require_authenticated_session)],
)


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_employee_endpoint(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
) -> EmployeeRead:
    try:
        employee = create_employee(db, payload)
    except DuplicateEmployeeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code already exists",
        ) from exc
    return EmployeeRead.model_validate(employee)


@router.get("", response_model=EmployeeList)
def list_employees_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EmployeeList:
    items, total = list_employees(db, limit=limit, offset=offset)
    return EmployeeList(
        items=[EmployeeRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
) -> EmployeeRead:
    employee = get_employee_by_id(db, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return EmployeeRead.model_validate(employee)
