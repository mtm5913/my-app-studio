"""Olive administration uses current server-side permissions on every request."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import database, security
from app.features.accounts import render

router = APIRouter()


def account_list(request):
    """Select only the two agreed account fields, never credentials or sessions."""
    with database.connect(request.app.state.settings) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT username, role FROM users ORDER BY username"
            )
        ]


@router.get("/api/admin", dependencies=[Depends(security.require_admin)])
def admin_api(request: Request):
    """A direct API request must pass the same trusted role check as the page."""
    return {"users": account_list(request)}


@router.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    """Redirect guests and deny members before querying any account list."""
    if not security.authenticate(request):
        return RedirectResponse("/login", status_code=303)
    try:
        security.require_admin(request)
    except HTTPException as error:
        if error.status_code != 403:
            raise
        return render(request, "forbidden.html", status=403)
    return render(request, "admin.html", users=account_list(request))
