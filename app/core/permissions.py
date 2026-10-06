from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.demo import demo_user
from app.core.errors import ApiError
from app.core.security import read_token
from app.db import get_db
from app.models import ROLE_RANK, Membership, Role, Scan, User


# auto_error is off so a missing token gets our own error shape. The scheme is what
# makes the docs page show an Authorize button.
bearer = HTTPBearer(auto_error=False, description="Token from /auth/login or /auth/register.")


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if settings.auth_disabled:
        return demo_user(db)
    user_id = read_token(credentials.credentials) if credentials else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "not_authenticated", "Log in and send a Bearer token.")
    return user


def membership_for(db: Session, user: User, org_id: str) -> Membership | None:
    return db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org_id)
    )


def require_role(minimum: Role):
    """Build a dependency for routes with an {org_id} in the path.

    Non-members get 404 so the API does not reveal which orgs exist.
    Members with too low a role get 403. Every org route goes through here.
    """

    def check(org_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Membership:
        member = membership_for(db, user, org_id)
        if member is None:
            raise ApiError(404, "not_found", "Organization not found.")
        if ROLE_RANK[member.role] < ROLE_RANK[minimum]:
            raise ApiError(403, "forbidden", f"This needs the {minimum.value} role.")
        return member

    return check


def require_scan_role(minimum: Role):
    """Like require_role, for routes with a {scan_id}. The org comes from the scan itself."""

    def check(scan_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Scan:
        scan = db.get(Scan, scan_id)
        member = membership_for(db, user, scan.organization_id) if scan else None
        if scan is None or member is None:
            raise ApiError(404, "not_found", "Scan not found.")
        if ROLE_RANK[member.role] < ROLE_RANK[minimum]:
            raise ApiError(403, "forbidden", f"This needs the {minimum.value} role.")
        return scan

    return check
