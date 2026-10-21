import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.salaries import router as salaries_router
from app.services.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME

_SWAGGER_PRESETS_MARKER = "    presets: ["

app = FastAPI(title="ACME Employee Salary Management System", docs_url=None)
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(salaries_router)
app.include_router(analytics_router)


def swagger_csrf_request_interceptor_js() -> str:
    cookie = CSRF_COOKIE_NAME
    header = CSRF_HEADER_NAME
    return f"""    requestInterceptor: function (req) {{
      var headers = req.headers || {{}};
      var existing;
      for (var name in headers) {{
        if (Object.prototype.hasOwnProperty.call(headers, name)
            && name.toLowerCase() === "{header.lower()}") {{
          existing = headers[name];
          break;
        }}
      }}
      if (existing === undefined || existing === null || existing === "") {{
        var prefix = "{cookie}=";
        var parts = document.cookie.split(";");
        for (var i = 0; i < parts.length; i++) {{
          var part = parts[i].trim();
          if (part.indexOf(prefix) === 0) {{
            var value = part.slice(prefix.length);
            if (value) {{
              try {{
                value = decodeURIComponent(value);
              }} catch (ignore) {{}}
              headers["{header}"] = value;
              req.headers = headers;
            }}
            break;
          }}
        }}
      }}
      return req;
    }},
"""


def inject_swagger_csrf_request_interceptor(html: str) -> str:
    if _SWAGGER_PRESETS_MARKER not in html:
        raise RuntimeError("Swagger UI HTML does not contain the expected presets marker")
    return html.replace(
        _SWAGGER_PRESETS_MARKER,
        swagger_csrf_request_interceptor_js() + _SWAGGER_PRESETS_MARKER,
        1,
    )


@app.get("/docs", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    html_response = get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
    )
    html = inject_swagger_csrf_request_interceptor(
        html_response.body.decode("utf-8")
    )
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def frontend_dist_dir() -> Path | None:
    configured = os.environ.get("FRONTEND_DIST", "").strip()
    path = Path(configured) if configured else _repository_root() / "frontend" / "dist"
    if not (path / "index.html").is_file():
        return None
    return path.resolve()


def _is_reserved_frontend_path(full_path: str) -> bool:
    normalized = full_path.lstrip("/")
    if normalized in {"health", "docs", "redoc", "openapi.json"}:
        return True
    return normalized == "api" or normalized.startswith("api/")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa(full_path: str) -> FileResponse:
    if _is_reserved_frontend_path(full_path):
        raise HTTPException(status_code=404, detail="Not Found")
    dist = frontend_dist_dir()
    if dist is None:
        raise HTTPException(status_code=404, detail="Not Found")
    if full_path in {"", "/"}:
        return FileResponse(dist / "index.html")
    candidate = (dist / full_path).resolve()
    try:
        candidate.relative_to(dist)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not Found") from None
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(dist / "index.html")
