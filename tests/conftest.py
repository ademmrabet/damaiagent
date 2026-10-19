import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests_auth.db")

import pytest

from webapp.db import Base, engine
from webapp.models import Conversation, ConversationShare, User

_TABLES = (ConversationShare, Conversation, User)


@pytest.fixture(autouse=True)
def _clean_users_table():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(table.__table__.delete())
    yield
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(table.__table__.delete())
