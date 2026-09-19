"""
The users table backing all three login paths (email/password, Google,
Microsoft). One table, one User type - an OAuth login and a form
signup both end up as the same kind of row, distinguished only by
which columns are populated:

  - Email/password account: hashed_password is set, oauth_provider
    and oauth_sub are NULL.
  - OAuth account (Google or Microsoft): oauth_provider + oauth_sub
    identify the account on that provider's side, hashed_password is
    NULL - there is no password to steal for an account that never
    had one.

A user could in principle have both (sign up with a password, later
also link Google) - the schema allows it, nothing in this first pass
builds that linking flow yet.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from webapp.db import Base


class Role(str, enum.Enum):
    analyst = "analyst"
    administrator = "administrator"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_sub", name="uq_oauth_identity"),
    )

    id = Column(UUID(as_uuid=True).with_variant(String(36), "sqlite"), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)

    hashed_password = Column(String, nullable=True)

    oauth_provider = Column(String, nullable=True)
    oauth_sub = Column(String, nullable=True)

    role = Column(Enum(Role), nullable=False, default=Role.analyst)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
