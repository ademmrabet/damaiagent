import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from webapp.models import Conversation, ConversationShare, ConversationShareLink, User

MAX_TITLE_LENGTH = 42
SHARE_LINK_TOKEN_BYTES = 24


# chat title from the first question, same rule as the frontend
def _derive_title(text: str) -> str:
    trimmed = text.strip()
    if len(trimmed) > MAX_TITLE_LENGTH:
        return trimmed[: MAX_TITLE_LENGTH - 2] + "…"
    return trimmed


# new empty conversation for this user
def create_conversation(db: Session, owner: User) -> Conversation:
    conversation = Conversation(
        owner_id=owner.id, title="New chat", title_is_default=True, messages=[]
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


# conversations the user owns, newest first
def list_own_conversations(db: Session, owner: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.owner_id == owner.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


# conversations other people shared with the user
def list_shared_with_me(db: Session, user: User) -> list[Conversation]:
    return (
        db.query(Conversation)
        .join(ConversationShare, ConversationShare.conversation_id == Conversation.id)
        .filter(ConversationShare.shared_with_user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


# load a conversation or fail with 404
def _get_conversation_or_404(db: Session, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


# conversation that must belong to the user
def get_owned_conversation(
    db: Session, conversation_id: str, user: User
) -> Conversation:
    conversation = _get_conversation_or_404(db, conversation_id)
    if conversation.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this conversation",
        )
    return conversation


# owner or someone it was shared with can read it
def get_conversation_for_viewing(
    db: Session, conversation_id: str, user: User
) -> Conversation:
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


# add a message and name the chat after the first question
def append_message(
    db: Session, conversation: Conversation, message: dict
) -> Conversation:
    is_first_user_message = (
        conversation.title_is_default and message.get("role") == "user"
    )

    conversation.messages = [*conversation.messages, message]
    if is_first_user_message:
        conversation.title = _derive_title(message.get("text", ""))
        conversation.title_is_default = False

    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


# delete a conversation
def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()


# give a user read access (used by email and qr sharing)
def _grant_share(
    db: Session, conversation: Conversation, shared_by: User, target: User
) -> ConversationShare:
    if target.id == conversation.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already own this conversation",
        )

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


# share with another user by email
def share_conversation(
    db: Session, conversation: Conversation, shared_by: User, email: str
) -> ConversationShare:
    target = db.query(User).filter(User.email == email.lower()).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found for {email!r} - they need to sign up first",
        )
    return _grant_share(db, conversation, shared_by, target)


# remove a share
def unshare_conversation(
    db: Session, conversation: Conversation, target_user_id: str
) -> None:
    db.query(ConversationShare).filter(
        ConversationShare.conversation_id == conversation.id,
        ConversationShare.shared_with_user_id == target_user_id,
    ).delete()
    db.commit()


# reuse the current share link or make a new one with an expiry
def get_or_create_share_link(
    db: Session, conversation: Conversation, created_by: User
) -> ConversationShareLink:
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


# delete the share link so the qr code stops working
def revoke_share_link(db: Session, conversation: Conversation) -> None:
    db.query(ConversationShareLink).filter(
        ConversationShareLink.conversation_id == conversation.id,
    ).delete()
    db.commit()


# make datetimes timezone-aware (sqlite drops the timezone)
def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# use a qr token, expired links are deleted
def claim_share_link(db: Session, token: str, user: User) -> Conversation:
    link = (
        db.query(ConversationShareLink)
        .filter(ConversationShareLink.token == token)
        .first()
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This share link doesn't exist",
        )

    if _as_aware(link.expires_at) <= datetime.now(timezone.utc):
        db.delete(link)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This share link has expired"
        )

    conversation = _get_conversation_or_404(db, link.conversation_id)
    if conversation.owner_id != user.id:
        _grant_share(db, conversation, conversation.owner, user)
    return conversation


# share link as json
def serialize_share_link(
    link: ConversationShareLink, url: str, qr_svg_data_uri: str
) -> dict:
    return {
        "token": link.token,
        "url": url,
        "qr_svg_data_uri": qr_svg_data_uri,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


# check an attachment key really belongs to this conversation
def conversation_has_attachment(conversation: Conversation, key: str) -> bool:
    for message in conversation.messages:
        attachment = (message.get("meta") or {}).get("attachment")
        if attachment and attachment.get("key") == key:
            return True
    return False


# conversation as json for the frontend
def serialize_conversation(conversation: Conversation, is_owner: bool) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "title_is_default": conversation.title_is_default,
        "messages": conversation.messages,
        "created_at": (
            conversation.created_at.isoformat() if conversation.created_at else None
        ),
        "updated_at": (
            conversation.updated_at.isoformat() if conversation.updated_at else None
        ),
        "is_owner": is_owner,
        "owner_email": conversation.owner.email if conversation.owner else None,
        "shared_with": (
            [
                {
                    "user_id": share.shared_with_user_id,
                    "email": share.shared_with_user.email,
                }
                for share in conversation.shares
            ]
            if is_owner
            else []
        ),
    }
