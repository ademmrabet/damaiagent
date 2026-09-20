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
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from webapp.db import Base

_UUID = UUID(as_uuid=True).with_variant(String(36), "sqlite")


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


class Conversation(Base):
    """
    A chat thread, persisted so it can be shared (see ConversationShare
    below) - previously this lived only in the browser's own
    localStorage (see webapp/frontend/src/hooks/useConversations.js),
    which works fine for one person on one device but can't be shown
    to anyone else, since there was never a copy of it anywhere the
    other person could reach.

    `messages` is the whole message list for this conversation, stored
    as one JSON array rather than a normalized child table - every
    read/write here is "the whole conversation," never one message in
    isolation, so a second table (and the joins/pagination that would
    come with it) would just add complexity for no real query this app
    ever needs to make. Each entry keeps the same shape the frontend
    already builds locally (role, text, meta) - see Chat.jsx's
    appendMessage calls - so the API layer can pass it straight through
    without reshaping it in either direction.
    """

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

    shares = relationship("ConversationShare", cascade="all, delete-orphan", backref="conversation")
    share_links = relationship("ConversationShareLink", cascade="all, delete-orphan", backref="conversation")
    owner = relationship("User", foreign_keys=[owner_id])


class ConversationShare(Base):
    """
    One row per (conversation, person it's been shared with) - a
    conversation can be shared with several colleagues, and the same
    person could in principle be re-shared without erroring (the
    unique constraint below makes that a no-op update path rather than
    a duplicate row) - see webapp/conversations.py's share_conversation
    for how that's handled. Sharing is deliberately view-only for now:
    only the owner can add new messages (see webapp/backend.py's
    add_message endpoint) - a shared-with user reading someone else's
    live, still-growing conversation and both of them appending to it
    at once opens real concurrency/attribution questions (whose
    follow-up does previous_node_id anchor to?) that a simple
    read-access share doesn't need to solve on day one.
    """

    __tablename__ = "conversation_shares"
    __table_args__ = (
        UniqueConstraint("conversation_id", "shared_with_user_id", name="uq_conversation_share"),
    )

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(_UUID, ForeignKey("conversations.id"), nullable=False, index=True)
    shared_with_user_id = Column(_UUID, ForeignKey("users.id"), nullable=False, index=True)
    shared_by_user_id = Column(_UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by_user = relationship("User", foreign_keys=[shared_by_user_id])


def _default_share_link_expiry():
    return datetime.now(timezone.utc) + timedelta(days=7)


class ConversationShareLink(Base):
    """
    A single "share via QR code / link" invite for a conversation -
    distinct from ConversationShare above, which is one specific
    colleague already granted access by email. This is an anonymous,
    scannable link: anyone who opens it (while logged in) is granted
    the same read-only access a colleague added by email would get,
    by way of webapp/conversations.py's claim_share_link creating an
    ordinary ConversationShare row for whoever visits it. That reuse
    is deliberate - it keeps exactly one place (ConversationShare)
    that decides who can view a conversation, rather than forking the
    authorization check in two directions.

    One active link per conversation (see get_or_create_share_link) -
    a second "Share via QR" click reuses the same link and the same
    QR image rather than minting a new token every time, so an
    already-printed or already-scanned code doesn't quietly stop
    working.
    """

    __tablename__ = "conversation_share_links"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(_UUID, ForeignKey("conversations.id"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    created_by_user_id = Column(_UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, default=_default_share_link_expiry, nullable=False)
