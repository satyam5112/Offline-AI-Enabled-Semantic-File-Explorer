"""
backend/vault/vault_routes.py
==============================
FastAPI routes for the Hidden Vault feature.
Register in main.py with:
    from backend.vault.vault_routes import router as vault_router
    app.include_router(vault_router)
"""

import os
import subprocess
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import quote

from backend.vault.vault import (
    verify_password, change_password, is_default_password,
    create_session, validate_session, destroy_session,
    add_to_vault, remove_from_vault, open_vault_file,
    get_vault_files, get_vault_stats, ensure_vault_table
)

router = APIRouter()

# Use the same templates directory as main.py
# Works regardless of where vault_routes.py lives
_THIS_DIR = os.path.abspath(__file__)                          # .../backend/vault/vault_routes.py
_VAULT_DIR = os.path.dirname(_THIS_DIR)                       # .../backend/vault
_BACKEND_DIR = os.path.dirname(_VAULT_DIR)                    # .../backend
TEMPLATES_DIR = os.path.join(_BACKEND_DIR, "api", "templates") # .../backend/api/templates

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ── helpers ───────────────────────────────────────────────────────────────────

def _token_from_request(request: Request) -> str | None:
    return request.cookies.get("vault_token")

def _is_unlocked(request: Request) -> bool:
    token = _token_from_request(request)
    return token is not None and validate_session(token)


# ═══════════════════════════════════════════════════════════════════════════════
#  VAULT PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/vault")
def vault_page(request: Request):
    """Main vault page — shows lock screen or vault contents."""
    ensure_vault_table()
    unlocked = _is_unlocked(request)

    # Extract query params for template (Jinja2 can't call request.query_params.get())
    from urllib.parse import unquote
    error = unquote(request.query_params.get("error", ""))
    msg   = unquote(request.query_params.get("msg", ""))

    return templates.TemplateResponse(
        request=request,
        name="vault.html",
        context={
            "unlocked": unlocked,
            "files": get_vault_files() if unlocked else [],
            "stats": get_vault_stats(),
            "is_default_password": is_default_password(),
            "error": error,
            "msg": msg,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/vault/unlock")
def vault_unlock(password: str = Form(...)):
    if verify_password(password):
        token = create_session()
        response = RedirectResponse(url="/vault", status_code=303)
        # Session cookie — expires when browser closes (no max_age)
        response.set_cookie("vault_token", token, httponly=True, samesite="strict")
        return response
    return RedirectResponse(
        url=f"/vault?error={quote('Incorrect password. Try again.')}",
        status_code=303
    )


@router.post("/vault/lock")
def vault_lock():
    destroy_session()
    response = RedirectResponse(url="/vault", status_code=303)
    response.delete_cookie("vault_token")
    return response


@router.post("/vault/change-password")
def vault_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    if new_password != confirm_password:
        return JSONResponse(
            {"success": False, "error": "New passwords do not match"},
            status_code=400
        )

    if len(new_password.strip()) < 1:
        return JSONResponse(
            {"success": False, "error": "New password cannot be empty"},
            status_code=400
        )

    result = change_password(current_password, new_password)

    if result["success"]:
        return JSONResponse({"success": True, "message": "Password changed successfully"})

    return JSONResponse({"success": False, "error": result["error"]}, status_code=400)


# ═══════════════════════════════════════════════════════════════════════════════
#  VAULT FILE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/vault/add")
def vault_add_file(
    request: Request,
    file_path: str = Form(...),
    password: str = Form(...)
):
    """Add a file to the vault (encrypt + remove from normal index)."""
    if not _is_unlocked(request):
        return JSONResponse({"success": False, "error": "Vault is locked"}, status_code=401)

    if not verify_password(password):
        return JSONResponse({"success": False, "error": "Incorrect password"}, status_code=403)

    result = add_to_vault(file_path, password)
    return JSONResponse(result)


@router.post("/vault/remove/{vault_id}")
def vault_remove_file(
    request: Request,
    vault_id: int,
    password: str = Form(...)
):
    """Remove a file from vault and restore it."""
    if not _is_unlocked(request):
        return JSONResponse({"success": False, "error": "Vault is locked"}, status_code=401)

    if not verify_password(password):
        return JSONResponse({"success": False, "error": "Incorrect password"}, status_code=403)

    result = remove_from_vault(vault_id, password)
    if result["success"]:
        return RedirectResponse(
            url=f"/vault?msg=success:{quote(result['message'])}",
            status_code=303
        )
    return RedirectResponse(
        url=f"/vault?msg=error:{quote(result['error'])}",
        status_code=303
    )


@router.get("/vault/open/{vault_id}")
def vault_open_file(request: Request, vault_id: int, password: str):
    """Decrypt to temp file and open natively. Temp file auto-deletes after 60s."""
    if not _is_unlocked(request):
        return JSONResponse({"success": False, "error": "Vault is locked"}, status_code=401)

    result = open_vault_file(vault_id, password)

    if not result["success"]:
        return JSONResponse(result, status_code=400)

    try:
        subprocess.Popen(f'start "" "{result["temp_path"]}"', shell=True)
        return JSONResponse({"success": True, "message": f"Opened {result['name']} (auto-closes in 60s)"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/vault/status")
def vault_status(request: Request):
    """Check if vault is currently unlocked."""
    return JSONResponse({
        "unlocked": _is_unlocked(request),
        "is_default_password": is_default_password()
    })