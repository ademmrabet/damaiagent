# database tables: users, conversations, shares

import enum
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from webapp.db import Base

_UUID = UUID(as_uuid=True).with_variant(String(36), "sqlite")


# user roles: analyst or administrator
class Role(str, enum.Enum):
    analyst = "analyst"
    administrator = "administrator"


# user account (password or google/microsoft login)
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_sub", name="uq_oauth_identity"),
    )

    id = Column(
        UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)

    hashed_password = Column(String, nullable=True)

    oauth_provider = Column(String, nullable=True)
    oauth_sub = Column(String, nullable=True)

    role = Column(Enum(Role), nullable=False, default=Role.analyst)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# a saved chat thread that can be shared
class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(_UUID, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False, default="New chat")
    title_is_default = Column(Boolean, nullable=False, default=True)
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    shares = relationship(
        "ConversationShare", cascade="all, delete-orphan", backref="conversation"
    )
    share_links = relationship(
        "ConversationShareLink", cascade="all, delete-orphan", backref="conversation"
    )
    owner = relationship("User", foreign_keys=[owner_id])


# a conversation shared with a user (read-only)
class ConversationShare(Base):

    __tablename__ = "conversation_shares"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "shared_with_user_id", name="uq_conversation_share"
        ),
    )

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        _UUID, ForeignKey("conversations.id"), nullable=False, index=True
    )
    shared_with_user_id = Column(
        _UUID, ForeignKey("users.id"), nullable=False, index=True
    )
    shared_by_user_id = Column(_UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by_user = relationship("User", foreign_keys=[shared_by_user_id])


# share links expire after 7 days
def _default_share_link_expiry():
    return datetime.now(timezone.utc) + timedelta(days=7)


# anonymous link behind the qr code
class ConversationShareLink(Base):

    __tablename__ = "conversation_share_links"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        _UUID, ForeignKey("conversations.id"), nullable=False, index=True
    )
    token = Column(String, unique=True, nullable=False, index=True)
    created_by_user_id = Column(_UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, default=_default_share_link_expiry, nullable=False)
