import sys
import asyncio
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.bookings import router as booking_router
from app.api.cargos import router as cargo_router
from app.api.documents import router as document_router
from app.auth.routes import router as auth_router
from app.auth.security import get_optional_current_user
from app.config import settings
from app.models import User
from app.pages.admin import router as admin_page_router
from app.pages.cargos import router as cargo_page_router
from app.pages.documents import router as document_page_router
from app.pages.shipper import router as shipper_page_router
from app.services.errors import DomainError

app = FastAPI(title="Smart Freight API")
templates = Jinja2Templates(directory="templates")

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

app.include_router(booking_router)
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(cargo_router)
app.include_router(document_page_router)
app.include_router(admin_page_router)
app.include_router(shipper_page_router)
app.include_router(cargo_page_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """JSON for API routes, a redirect/403 page for HTML routes (SPEC-core §8)."""

    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": {"code": exc.code, "message": exc.message}
            },
        )

    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=303)

    if exc.status_code == 403:
        return templates.TemplateResponse(
            request=request,
            name="errors/403.html",
            context={
                "request": request,
                "current_user": None,
                "message": exc.message,
            },
            status_code=403,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"request": request, "current_user": current_user},
    )
