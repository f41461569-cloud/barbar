from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.bookings import router as booking_router
from app.auth.routes import router as auth_router

app = FastAPI(title="Smart Freight API")
templates = Jinja2Templates(directory="templates")

app.include_router(booking_router)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"request": request},
    )
