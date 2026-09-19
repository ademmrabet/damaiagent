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

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from webapp.models import Conversation, ConversationShare, User

MAX_TITLE_LENGTH = 42


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


def share_conversation(db: Session, conversation: Conversation, shared_by: User, email: str) -> ConversationShare:
    target = db.query(User).filter(User.email == email.lower()).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found for {email!r} - they need to sign up first",
        )
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


def unshare_conversation(db: Session, conversation: Conversation, target_user_id: str) -> None:
    db.query(ConversationShare).filter(
        ConversationShare.conversation_id == conversation.id,
        ConversationShare.shared_with_user_id == target_user_id,
    ).delete()
    db.commit()


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
