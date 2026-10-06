"""Open demo mode: one shared user and one shared organization, no sign-in."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Membership, Organization, Role, User

DEMO_EMAIL = "demo@open.local"
DEMO_ORG_NAME = "Demo workspace"


def demo_user(db: Session) -> User:
    """The shared user, created on first use together with a workspace they own.

    Its password hash is not a valid hash, so nobody can sign in as it.
    """
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        return user

    user = User(email=DEMO_EMAIL, password_hash="!")
    org = Organization(name=DEMO_ORG_NAME)
    org.memberships.append(Membership(user=user, role=Role.owner))
    db.add_all([user, org])
    try:
        db.commit()
    except IntegrityError:
        # Two first requests raced. The other one won, so use theirs.
        db.rollback()
        return db.scalar(select(User).where(User.email == DEMO_EMAIL))
    return user
