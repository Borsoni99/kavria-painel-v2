import asyncio

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.html import page
from app.config import get_settings
from app.security import constant_time_equals

router = APIRouter()


class NotAuthenticated(Exception):
    pass


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise NotAuthenticated()


def require_admin_api(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="login necessário")


@router.get("/admin/login", response_class=HTMLResponse)
async def login_form(error: str | None = None):
    msg = '<p class="err">Senha incorreta.</p>' if error else ""
    return page(
        "Entrar",
        f"""<form method="post" action="/admin/login" class="card narrow">
        <h1>Kavria · Admin</h1>{msg}
        <label>Senha <input type="password" name="password" autofocus required></label>
        <button type="submit">Entrar</button></form>""",
    )


@router.post("/admin/login")
async def login(request: Request, password: str = Form(...)):
    expected = get_settings().admin_password
    if not expected:
        return HTMLResponse(page("Configuração", "<p class='err'>ADMIN_PASSWORD não definido no .env</p>"),
                            status_code=500)
    if not constant_time_equals(password, expected):
        await asyncio.sleep(1.0)  # freia tentativa e erro
        return RedirectResponse("/admin/login?error=1", status_code=303)
    request.session.clear()
    request.session["admin"] = True
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
