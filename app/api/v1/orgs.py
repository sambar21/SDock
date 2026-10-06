from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, errors
from app.core.permissions import current_user, require_role
from app.db import get_db
from app.models import Membership, Organization, Role, User
from app.schemas import MemberAdd, MemberOut, MemberUpdate, OrgCreate, OrgOut, OrgSummary

router = APIRouter(prefix="/orgs", tags=["orgs"], responses=errors(401, 403, 404, 409))


def _org_out(org: Organization, your_role: Role) -> OrgOut:
    members = [MemberOut(user_id=m.user_id, email=m.user.email, role=m.role) for m in org.memberships]
    return OrgOut(id=org.id, name=org.name, your_role=your_role, members=members)


def _owner_count(db: Session, org_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == org_id, Membership.role == Role.owner
        )
    )


def _target(db: Session, org_id: str, user_id: str) -> Membership:
    member = db.scalar(
        select(Membership).where(Membership.organization_id == org_id, Membership.user_id == user_id)
    )
    if member is None:
        raise ApiError(404, "not_found", "That user is not a member of this organization.")
    return member


@router.post("", response_model=OrgOut, status_code=201)
def create_org(body: OrgCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = Organization(name=body.name)
    org.memberships.append(Membership(user_id=user.id, role=Role.owner))
    db.add(org)
    db.commit()
    return _org_out(org, Role.owner)


@router.get("", response_model=list[OrgSummary])
def my_orgs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    ).all()
    return [OrgSummary(id=org.id, name=org.name, your_role=role) for org, role in rows]


@router.get("/{org_id}", response_model=OrgOut)
def get_org(org_id: str, member: Membership = Depends(require_role(Role.viewer)), db: Session = Depends(get_db)):
    return _org_out(db.get(Organization, org_id), member.role)


@router.post("/{org_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    org_id: str, body: MemberAdd, _: Membership = Depends(require_role(Role.owner)), db: Session = Depends(get_db)
):
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if target is None:
        raise ApiError(404, "user_not_found", "No registered user has that email.")
    if db.scalar(select(Membership).where(Membership.organization_id == org_id, Membership.user_id == target.id)):
        raise ApiError(409, "already_member", "That user is already in this organization.")
    db.add(Membership(user_id=target.id, organization_id=org_id, role=body.role))
    db.commit()
    return MemberOut(user_id=target.id, email=target.email, role=body.role)


@router.patch("/{org_id}/members/{user_id}", response_model=MemberOut)
def change_role(
    org_id: str,
    user_id: str,
    body: MemberUpdate,
    _: Membership = Depends(require_role(Role.owner)),
    db: Session = Depends(get_db),
):
    member = _target(db, org_id, user_id)
    if member.role == Role.owner and body.role != Role.owner and _owner_count(db, org_id) == 1:
        raise ApiError(409, "last_owner", "An organization needs at least one owner.")
    member.role = body.role
    db.commit()
    return MemberOut(user_id=user_id, email=member.user.email, role=member.role)


@router.delete("/{org_id}/members/{user_id}", status_code=204)
def remove_member(
    org_id: str, user_id: str, _: Membership = Depends(require_role(Role.owner)), db: Session = Depends(get_db)
):
    member = _target(db, org_id, user_id)
    if member.role == Role.owner and _owner_count(db, org_id) == 1:
        raise ApiError(409, "last_owner", "An organization needs at least one owner.")
    db.delete(member)
    db.commit()
    return Response(status_code=204)
