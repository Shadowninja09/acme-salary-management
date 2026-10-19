from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_session, require_csrf_token
from app.db.session import get_db
from app.schemas.salary import SalaryCreate, SalaryCreateRequest, SalaryRead
from app.services.salary import (
    DuplicateSalaryEffectiveDateError,
    EmployeeNotFoundError,
    InvalidPayFrequencyError,
    InvalidSalaryAmountError,
    InvalidSalaryCurrencyError,
    create_salary,
    list_employee_salaries,
)

router = APIRouter(
    prefix="/api/v1/employees",
    tags=["salaries"],
    dependencies=[Depends(require_authenticated_session)],
)

DUPLICATE_EFFECTIVE_DATE_DETAIL = "Salary already exists for this effective date"
INVALID_SALARY_AMOUNT_DETAIL = "Invalid salary amount"


@router.post(
    "/{employee_id}/salaries",
    response_model=SalaryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_salary_endpoint(
    employee_id: int,
    payload: SalaryCreateRequest,
    db: Session = Depends(get_db),
) -> SalaryRead:
    try:
        record = create_salary(
            db,
            SalaryCreate(
                employee_id=employee_id,
                amount=payload.amount,
                currency=payload.currency,
                pay_frequency=payload.pay_frequency,
                effective_from=payload.effective_from,
            ),
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    except DuplicateSalaryEffectiveDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EFFECTIVE_DATE_DETAIL,
        ) from exc
    except (
        InvalidSalaryAmountError,
        InvalidSalaryCurrencyError,
        InvalidPayFrequencyError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=INVALID_SALARY_AMOUNT_DETAIL,
        ) from exc
    return SalaryRead.model_validate(record)


@router.get(
    "/{employee_id}/salaries",
    response_model=list[SalaryRead],
)
def list_employee_salaries_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
) -> list[SalaryRead]:
    try:
        records = list_employee_salaries(db, employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    return [SalaryRead.model_validate(record) for record in records]
