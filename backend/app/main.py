from fastapi import FastAPI

app = FastAPI(title="ACME Employee Salary Management System")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
