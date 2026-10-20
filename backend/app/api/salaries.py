from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_session, require_csrf_token
from app.db.session import get_db
from app.schemas.salary import (
    SalaryCorrection,
    SalaryCorrectionAuditRead,
    SalaryCreate,
    SalaryCreateRequest,
    SalaryRead,
)
from app.services.salary import (
    DuplicateSalaryEffectiveDateError,
    EmployeeNotFoundError,
    InvalidPayFrequencyError,
    InvalidSalaryAmountError,
    InvalidSalaryCorrectionReasonError,
    InvalidSalaryCurrencyError,
    SalaryNotFoundError,
    correct_salary,
    create_salary,
    get_applicable_salary,
    list_employee_salaries,
    list_employee_salary_corrections,
)

router = APIRouter(
    prefix="/api/v1/employees",
    tags=["salaries"],
    dependencies=[Depends(require_authenticated_session)],
)

DUPLICATE_EFFECTIVE_DATE_DETAIL = "Salary already exists for this effective date"
INVALID_SALARY_AMOUNT_DETAIL = "Invalid salary amount"
INVALID_CORRECTION_REASON_DETAIL = "Invalid correction reason"


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


@router.get(
    "/{employee_id}/salary-corrections",
    response_model=list[SalaryCorrectionAuditRead],
)
def list_employee_salary_corrections_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
) -> list[SalaryCorrectionAuditRead]:
    try:
        records = list_employee_salary_corrections(db, employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    return [SalaryCorrectionAuditRead.model_validate(record) for record in records]


@router.get(
    "/{employee_id}/salaries/as-of",
    response_model=SalaryRead | None,
)
def get_applicable_salary_endpoint(
    employee_id: int,
    as_of: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> SalaryRead | None:
    try:
        record = get_applicable_salary(db, employee_id, as_of)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    if record is None:
        return None
    return SalaryRead.model_validate(record)


@router.patch(
    "/{employee_id}/salaries/{salary_id}",
    response_model=SalaryRead,
    dependencies=[Depends(require_csrf_token)],
)
def correct_salary_endpoint(
    employee_id: int,
    salary_id: int,
    payload: SalaryCorrection,
    db: Session = Depends(get_db),
) -> SalaryRead:
    try:
        record = correct_salary(db, employee_id, salary_id, payload)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        ) from exc
    except SalaryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary not found",
        ) from exc
    except DuplicateSalaryEffectiveDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_EFFECTIVE_DATE_DETAIL,
        ) from exc
    except InvalidSalaryCorrectionReasonError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=INVALID_CORRECTION_REASON_DETAIL,
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
