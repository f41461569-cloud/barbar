"""Authenticated-user and role dependencies (docs/SPEC-core.md §4).

API routes get JSON errors; the shared exception handler in ``app.main`` turns
the same exceptions into a login redirect or the 403 page for HTML routes.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.security import get_optional_current_user
from app.database import get_db
from app.models import User
from app.services.errors import Forbidden, Unauthorized


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_optional_current_user(request, db)
    if user is None:
        raise Unauthorized()
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    """Return a dependency that admits only the given role values."""

    allowed = frozenset(roles)

    def dependency(
        request: Request, db: Session = Depends(get_db)
    ) -> User:
        user = get_optional_current_user(request, db)
        if user is None:
            raise Unauthorized()
        if user.role.value not in allowed:
            raise Forbidden()
        return user

    return dependency


require_driver = require_roles("driver")
require_shipper = require_roles("shipper")
require_admin = require_roles("admin")
require_authenticated = require_roles(
    "driver", "shipper", "carrier", "admin"
)
