# google and microsoft sign-in

import os

from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session

from webapp.models import Role, User

oauth = OAuth()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")

GOOGLE_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
MICROSOFT_CONFIGURED = bool(MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET)

if GOOGLE_CONFIGURED:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if MICROSOFT_CONFIGURED:
    oauth.register(
        name="microsoft",
        client_id=MICROSOFT_CLIENT_ID,
        client_secret=MICROSOFT_CLIENT_SECRET,
        server_metadata_url=(
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )


# find the user by provider id, or create the account
def get_or_create_oauth_user(
    db: Session, provider: str, subject: str, email: str, name
) -> User:
    user = (
        db.query(User)
        .filter(User.oauth_provider == provider, User.oauth_sub == subject)
        .first()
    )
    if user:
        return user

    user = db.query(User).filter(User.email == email.lower()).first()
    if user:
        user.oauth_provider = provider
        user.oauth_sub = subject
        db.commit()
        db.refresh(user)
        return user

    is_first_user = db.query(User).count() == 0
    user = User(
        email=email.lower(),
        name=name,
        oauth_provider=provider,
        oauth_sub=subject,
        role=Role.administrator if is_first_user else Role.analyst,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
