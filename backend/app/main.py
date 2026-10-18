from fastapi import FastAPI

from app.api.employees import router as employees_router

app = FastAPI(title="ACME Employee Salary Management System")
app.include_router(employees_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
