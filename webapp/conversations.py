"""
Conversation storage and sharing - the pieces webapp/backend.py's
/api/conversations* routes share. Kept separate from backend.py for
the same reason webapp/auth.py and webapp/oauth.py already are: the
routes stay thin (auth/lookup/response), the actual rules live here
where they can be unit-tested without spinning up the whole app.

Sharing is deliberately view-only (see models.py's ConversationShare
docstring) - a shared-with user can call get_conversation_for_viewing
but never append_message on a conversation they don't own.
"""

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from webapp.models import Conversation, ConversationShare, ConversationShareLink, User

MAX_TITLE_LENGTH = 42
SHARE_LINK_TOKEN_BYTES = 24


def _derive_title(text: str) -> str:
    """
    Mirrors the frontend's own deriveTitle (see useConversations.js) -
    kept in sync deliberately so a conversation's title looks the same
    whether it was derived client-side (before this feature) or here.
    """
    trimmed = text.strip()
    if len(trimmed) > MAX_TITLE_LENGTH:
        return trimmed[: MAX_TITLE_LENGTH - 2] + "…"
    return trimmed


def create_conversation(db: Session, owner: User) -> Conversation:
    conversation = Conversation(owner_id=owner.id, title="New chat", title_is_default=True, messages=[])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_own_conversations(db: Session, owner: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.owner_id == owner.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def list_shared_with_me(db: Session, user: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .join(ConversationShare, ConversationShare.conversation_id == Conversation.id)
        .filter(ConversationShare.shared_with_user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def _get_conversation_or_404(db: Session, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def get_owned_conversation(db: Session, conversation_id: str, user: User) -> Conversation:
    """For routes only the owner may use (renaming, deleting, posting messages, sharing)."""
    conversation = _get_conversation_or_404(db, conversation_id)
    if conversation.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't own this conversation")
    return conversation


def get_conversation_for_viewing(db: Session, conversation_id: str, user: User) -> Conversation:
    """For read access - the owner, or anyone it's been shared with."""
    conversation = _get_conversation_or_404(db, conversation_id)
    if conversation.owner_id == user.id:
        return conversation

    shared = (
        db.query(ConversationShare)
        .filter(
            ConversationShare.conversation_id == conversation.id,
            ConversationShare.shared_with_user_id == user.id,
        )
        .first()
    )
    if shared is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This conversation hasn't been shared with you",
        )
    return conversation


def append_message(db: Session, conversation: Conversation, message: dict) -> Conversation:
    is_first_user_message = conversation.title_is_default and message.get("role") == "user"

    conversation.messages = [*conversation.messages, message]
    if is_first_user_message:
        conversation.title = _derive_title(message.get("text", ""))
        conversation.title_is_default = False

    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()


def _grant_share(db: Session, conversation: Conversation, shared_by: User, target: User) -> ConversationShare:
    """
    Shared by both the email-invite path (share_conversation) and the
    QR/link-invite path (claim_share_link) - whichever way someone
    ends up with access, it's the same ConversationShare row, so
    there's exactly one place that decides who can view a
    conversation (see models.py's ConversationShareLink docstring).
    """
    if target.id == conversation.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this conversation")

    existing = (
        db.query(ConversationShare)
        .filter(
            ConversationShare.conversation_id == conversation.id,
            ConversationShare.shared_with_user_id == target.id,
        )
        .first()
    )
    if existing is not None:
        return existing

    share = ConversationShare(
        conversation_id=conversation.id,
        shared_with_user_id=target.id,
        shared_by_user_id=shared_by.id,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def share_conversation(db: Session, conversation: Conversation, shared_by: User, email: str) -> ConversationShare:
    target = db.query(User).filter(User.email == email.lower()).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found for {email!r} - they need to sign up first",
        )
    return _grant_share(db, conversation, shared_by, target)


def unshare_conversation(db: Session, conversation: Conversation, target_user_id: str) -> None:
    db.query(ConversationShare).filter(
        ConversationShare.conversation_id == conversation.id,
        ConversationShare.shared_with_user_id == target_user_id,
    ).delete()
    db.commit()


def get_or_create_share_link(db: Session, conversation: Conversation, created_by: User) -> ConversationShareLink:
    """
    Reuses an existing, still-valid link rather than minting a new
    token every time the owner reopens the "Share via QR code" panel -
    otherwise a link someone already scanned (or a QR code someone
    already printed) would silently stop working the next time the
    owner looked at it.
    """
    now = datetime.now(timezone.utc)
    existing = (
        db.query(ConversationShareLink)
        .filter(ConversationShareLink.conversation_id == conversation.id)
        .order_by(ConversationShareLink.created_at.desc())
        .first()
    )
    if existing is not None and _as_aware(existing.expires_at) > now:
        return existing
    if existing is not None:
        db.delete(existing)

    link = ConversationShareLink(
        conversation_id=conversation.id,
        token=secrets.token_urlsafe(SHARE_LINK_TOKEN_BYTES),
        created_by_user_id=created_by.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def revoke_share_link(db: Session, conversation: Conversation) -> None:
    db.query(ConversationShareLink).filter(
        ConversationShareLink.conversation_id == conversation.id,
    ).delete()
    db.commit()


def _as_aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; Postgres keeps it - normalize to UTC-aware either way."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def claim_share_link(db: Session, token: str, user: User) -> Conversation:
    """
    Called when a logged-in user opens a "Share via QR code" link -
    grants them the same read-only access share_conversation would,
    via the same _grant_share path, keyed by whoever is holding the
    token rather than a specific email the owner typed in. An expired
    link is deleted on the way out rather than left to accumulate.
    """
    link = db.query(ConversationShareLink).filter(ConversationShareLink.token == token).first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This share link doesn't exist")

    if _as_aware(link.expires_at) <= datetime.now(timezone.utc):
        db.delete(link)
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This share link has expired")

    conversation = _get_conversation_or_404(db, link.conversation_id)
    if conversation.owner_id != user.id:
        _grant_share(db, conversation, conversation.owner, user)
    return conversation


def serialize_share_link(link: ConversationShareLink, url: str, qr_svg_data_uri: str) -> dict:
    return {
        "token": link.token,
        "url": url,
        "qr_svg_data_uri": qr_svg_data_uri,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


def conversation_has_attachment(conversation: Conversation, key: str) -> bool:
    """
    Attachment downloads (see webapp/backend.py's get_attachment_url)
    are gated on this rather than a separate ownership check on the
    file itself - anyone who can view the conversation can view what
    was actually attached to a message in it, and nothing else. This
    also stops one conversation's viewer from using a guessed or
    leaked key to pull a file that was only ever posted somewhere they
    don't have access to.
    """
    for message in conversation.messages:
        attachment = (message.get("meta") or {}).get("attachment")
        if attachment and attachment.get("key") == key:
            return True
    return False


def serialize_conversation(conversation: Conversation, is_owner: bool) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "title_is_default": conversation.title_is_default,
        "messages": conversation.messages,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "is_owner": is_owner,
        "owner_email": conversation.owner.email if conversation.owner else None,
        "shared_with": [
            {"user_id": share.shared_with_user_id, "email": share.shared_with_user.email}
            for share in conversation.shares
        ] if is_owner else [],
    }
