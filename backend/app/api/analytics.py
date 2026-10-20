from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_session
from app.db.session import get_db
from app.schemas.analytics import CompensationAnalyticsRead
from app.services.analytics import compensation_analytics

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_authenticated_session)],
)


@router.get(
    "/compensation",
    response_model=CompensationAnalyticsRead,
    summary="Compensation analytics as of a reporting date",
)
def get_compensation_analytics(
    reporting_date: date = Query(
        ...,
        alias="date",
        description="Reporting date (YYYY-MM-DD). Selects the latest salary on or before this date.",
    ),
    db: Session = Depends(get_db),
) -> CompensationAnalyticsRead:
    return compensation_analytics(db, reporting_date)
