"""
Google and Microsoft sign-in via Authlib's Starlette OAuth client.

Both providers share one goal once the redirect dance is done:
resolve to a User row and hand back exactly the same kind of JWT the
email/password path issues (webapp/auth.py's create_access_token) -
the rest of the app never needs to know which of the three login
paths a request's token came from.

Registered lazily, and only if credentials are actually present
(GOOGLE_CLIENT_ID/SECRET, MICROSOFT_CLIENT_ID/SECRET) - the app still
starts, and email/password login still works, before either OAuth app
has been set up. See docs/oauth_setup.md for how to register them.
"""

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


def get_or_create_oauth_user(db: Session, provider: str, subject: str, email: str, name) -> User:
    """
    Looked up by (provider, subject) first - the provider's own
    stable identifier - never by email alone, since email addresses
    can be reassigned or changed on the provider's side in ways a
    subject id isn't. Falls back to linking onto an existing
    password account with the same email (so signing up with a
    password and later using Google with that same address doesn't
    silently create a second, separate account) before creating a
    brand new row.
    """
    user = db.query(User).filter(User.oauth_provider == provider, User.oauth_sub == subject).first()
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
