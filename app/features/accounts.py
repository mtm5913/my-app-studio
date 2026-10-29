"""Olive's guarded account services and intent-preserving HTML navigation."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import security
from app.schemas import LoginInput, PublicUser, SignupInput

router = APIRouter()


def destination(value):
    """Accept exact known internal destinations, never arbitrary redirect URLs."""
    return value if value in {"/", "/dashboard", "/ask"} else "/"


def account_url(path, target):
    """Carry only the allowlisted intent between signup and login."""
    return path + ("?" + urlencode({"next": target}) if target != "/" else "")


def render(request, name, *, status=200, **context):
    """Render an escaped page and issue CSRF state without retaining credentials."""
    cookies = Response()
    token = security.csrf_token(request, cookies)
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context={**context, "csrf_token": token},
        status_code=status,
    )
    response.raw_headers.extend(
        header for header in cookies.raw_headers if header[0] == b"set-cookie"
    )
    return response


def api_csrf(request: Request):
    """Require the existing synchronizer token before any JSON mutation."""
    security.require_csrf(request, request.headers.get("X-CSRF-Token"))


@router.get("/api/csrf")
def csrf(request: Request, response: Response):
    """Provide a same-origin client with its session-bound CSRF token."""
    return {"csrf_token": security.csrf_token(request, response)}


@router.post(
    "/api/signup",
    status_code=201,
    response_model=PublicUser,
    dependencies=[Depends(api_csrf)],
)
def api_signup(request: Request, credentials: SignupInput):
    """Create members only, with bounded inputs and the prepared signup throttle."""
    security.limit_signup(request)
    return security.signup(
        request.app.state.settings, credentials.username, credentials.password
    )


@router.post("/api/login", response_model=PublicUser, dependencies=[Depends(api_csrf)])
def api_login(request: Request, response: Response, credentials: LoginInput):
    """Return public identity; the signed session stays in an HttpOnly cookie."""
    return security.login(request, response, credentials.username, credentials.password)


@router.get("/api/me", response_model=PublicUser)
def me(user=Depends(security.require_user)):
    """Expose only the authenticated user's public identity."""
    return user


@router.post("/api/logout", dependencies=[Depends(api_csrf)])
def api_logout(request: Request, response: Response):
    """Revoke server state as well as clearing the browser cookie."""
    security.require_user(request)
    security.logout(request, response)
    return {"status": "logged_out"}


@router.get("/preview", include_in_schema=False)
def preview(request: Request):
    """Show an explicitly public sample without accessing private member records."""
    return render(request, "preview.html")


@router.get("/signup", include_in_schema=False)
@router.get("/login", include_in_schema=False)
def account_page(request: Request):
    """Keep standalone login on home and explicitly requested intent intact."""
    target = destination(request.query_params.get("next"))
    if security.authenticate(request):
        return RedirectResponse(target, status_code=303)
    return render(
        request,
        "account.html",
        signup=request.url.path == "/signup",
        target=target,
        username="",
        error=None,
    )


@router.post("/signup", include_in_schema=False)
@router.post("/login", include_in_schema=False)
async def account_form(request: Request):
    """HTML and JSON use the same validation, CSRF, hashing and session services."""
    form = dict(await request.form(max_fields=5, max_files=0))
    signup = request.url.path == "/signup"
    target = destination(form.pop("next", None))
    token = form.pop("csrf_token", None)
    username = ""
    try:
        security.require_csrf(request, token)
        credentials = (SignupInput if signup else LoginInput).model_validate(form)
        username = credentials.username
        if signup:
            security.limit_signup(request)
            security.signup(request.app.state.settings, username, credentials.password)
            return RedirectResponse(account_url("/login", target), status_code=303)
        response = RedirectResponse(target, status_code=303)
        security.login(request, response, username, credentials.password)
        return response
    except ValidationError:
        return render(
            request,
            "account.html",
            status=422,
            signup=signup,
            target=target,
            username="",
            error="Check your username and password requirements.",
        )
    except HTTPException as error:
        response = render(
            request,
            "account.html",
            status=error.status_code,
            signup=signup,
            target=target,
            username=username,
            error=error.detail,
        )
        response.headers.update(error.headers or {})
        return response


@router.get("/dashboard", include_in_schema=False)
def dashboard(request: Request):
    """Keep the real member space private even when its URL is entered directly."""
    user = security.authenticate(request)
    if not user:
        return RedirectResponse(account_url("/login", "/dashboard"), status_code=303)
    return render(request, "dashboard.html", user=user)


@router.post("/logout", include_in_schema=False)
async def logout(request: Request):
    """A POST with CSRF revokes the current session; a GET never logs anyone out."""
    form = await request.form(max_fields=1, max_files=0)
    security.require_csrf(request, form.get("csrf_token"))
    security.require_user(request)
    response = RedirectResponse("/", status_code=303)
    security.logout(request, response)
    return response
