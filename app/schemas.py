from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role, ScanStatus


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: Role


class OrgOut(BaseModel):
    id: str
    name: str
    your_role: Role
    members: list[MemberOut]


class OrgSummary(BaseModel):
    id: str
    name: str
    your_role: Role


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role


class MemberUpdate(BaseModel):
    role: Role


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    original_filename: str
    status: ScanStatus
    original_size: int
    preview_size: int | None
    reduction_pct: float | None
    error_message: str | None
    created_at: datetime
